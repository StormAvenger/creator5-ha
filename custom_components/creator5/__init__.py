"""Experimental Creator 5 monitoring and chamber-light control."""

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import CONF_CHECK_CODE, CONF_SERIAL, DOMAIN
from .creator5py import AuthenticationError, Creator5Client, PrinterError, PrinterStatus
from .creator5py.client import ControlError
from .error_info import explanation
from .history import MAINTENANCE, PrintHistory
from .settings import validated_options

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.LIGHT,
    Platform.CAMERA,
    Platform.IMAGE,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SWITCH,
]


async def async_setup(hass, config):
    from .setup_panel import async_setup_panel

    await async_setup_panel(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    client = Creator5Client(
        async_get_clientsession(hass),
        entry.data[CONF_HOST],
        entry.data[CONF_SERIAL],
        entry.data[CONF_CHECK_CODE],
    )

    coordinator = Creator5Coordinator(hass, entry, client)
    await coordinator.history.async_load()
    entry.async_on_unload(coordinator.cancel_event_timers)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_options))
    return True


async def async_reload_options(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        entry.runtime_data.cancel_event_timers()
        await entry.runtime_data.history.async_close()
    return unloaded


async def async_remove_entry(hass, entry):
    await PrintHistory(hass, entry.entry_id).store.async_remove()


class Creator5Coordinator(DataUpdateCoordinator[PrinterStatus]):
    def __init__(self, hass, entry, client):
        self.entry = entry
        self.history = PrintHistory(hass, entry.entry_id)
        self._observed_once = False
        self._last_error = None
        self._maintenance_due = {}
        self._pause_timer = None
        self._offline_timer = None
        self._pause_notified = False
        self._offline_notified = False
        self.last_control_failure_stage = None
        self.options = validated_options(entry.options, entry.data[CONF_HOST])
        self.last_successful_update = None
        self.estimated_completion = None
        self._eta_job = None
        self._eta_marker = None
        super().__init__(
            hass,
            logging.getLogger(__name__),
            name="Creator 5",
            update_interval=timedelta(seconds=self.options["poll_seconds"]),
            config_entry=entry,
        )
        self.client = client

    async def _async_update_data(self):
        try:
            status = await self.client.get_status()
            self.last_successful_update = dt_util.utcnow()
            self._process_status(status)
            return status
        except AuthenticationError as err:
            self.estimated_completion = None
            self._connection_failed()
            raise ConfigEntryAuthFailed(str(err)) from err
        except PrinterError as err:
            self.estimated_completion = None
            self._connection_failed()
            raise UpdateFailed(str(err)) from err

    def _emit(self, kind, message):
        if not self._observed_once:
            return
        device = dr.async_get(self.hass).async_get_device_by_identifier(
            (DOMAIN, self.entry.data[CONF_SERIAL]), self.entry.entry_id
        )
        self.hass.bus.async_fire(
            "creator5_event",
            {
                "entry_id": self.entry.entry_id,
                "device_id": device.id if device else None,
                "kind": kind,
                "message": message,
            },
        )

    def cancel_event_timers(self):
        for name in ("_pause_timer", "_offline_timer"):
            if timer := getattr(self, name):
                timer()
                setattr(self, name, None)

    def _connection_failed(self):
        self.history.missed_update()
        if not self._observed_once or self._offline_timer or self._offline_notified:
            return

        @callback
        def offline(_now):
            self._offline_timer = None
            if not self.last_update_success:
                self._offline_notified = True
                self._emit(
                    "offline", "Printer connection has been lost for the configured interval."
                )

        self._offline_timer = async_call_later(
            self.hass,
            self.options["offline_alert_minutes"] * 60,
            offline,
        )

    def _process_status(self, status):
        self._update_completion(status)
        if self._offline_timer:
            self._offline_timer()
            self._offline_timer = None
        self._offline_notified = False
        for kind in self.history.observe(status, self.last_successful_update, self.options):
            self._emit(
                kind,
                {
                    "completed": "Printer reports the print completed.",
                    "bed_cooled": (
                        f"Print bed is below {self.options['bed_cooled_c']} °C with its target off."
                    ),
                }[kind],
            )
        error = (status.error_code, status.state == "error")
        if error != self._last_error and (status.error_code not in (None, "none") or error[1]):
            title, hint, _known = explanation(status)
            code = status.error_code if status.error_code not in (None, "none") else "Printer error"
            self._emit(
                "error",
                f"{code}: {title or 'Check the printer screen'}. {hint or ''}",
            )
        if status.error_code is not None or error[1]:
            self._last_error = error
        if status.state in ("paused", "pause"):
            if not self._pause_timer and not self._pause_notified:

                @callback
                def paused(_now):
                    self._pause_timer = None
                    if self.last_update_success and self.data.state in ("paused", "pause"):
                        self._pause_notified = True
                        self._emit(
                            "prolonged_pause",
                            "Printer has remained paused for the configured interval.",
                        )

                self._pause_timer = async_call_later(
                    self.hass,
                    self.options["pause_alert_minutes"] * 60,
                    paused,
                )
        else:
            if self._pause_timer:
                self._pause_timer()
                self._pause_timer = None
            self._pause_notified = False
        for key, label in MAINTENANCE.items():
            remaining = self.history.remaining(key, status.lifetime_print_hours, self.options)
            if remaining is None:
                continue
            due = remaining <= 0
            if due and self._maintenance_due.get(key) is False:
                self._emit(
                    "maintenance",
                    f"{label} reminder is due based on your configured printing hours.",
                )
            self._maintenance_due[key] = due
        self._observed_once = True

    def record_service(self, key):
        self.history.record_service(key, self.data.lifetime_print_hours, dt_util.utcnow())
        self._maintenance_due[key] = False
        self.async_update_listeners()

    def _update_completion(self, status):
        remaining = status.nonnegative("estimatedTime", maximum=366 * 86400)
        job = status.current_filename
        marker = (remaining, status.progress_percent, status.nonnegative("printLayer"))
        if status.state != "printing" or job is None or remaining is None:
            self.estimated_completion = None
        elif (
            self.estimated_completion is None or job != self._eta_job or marker != self._eta_marker
        ):
            self.estimated_completion = self.last_successful_update + timedelta(seconds=remaining)
        # Frozen printer estimates do not slide forward on every identical poll.
        self._eta_job, self._eta_marker = job, marker

    async def async_set_light(self, on):
        # The client verifies the light state before publishing the shared snapshot.
        try:
            status = await self.client.set_light(on)
        except ControlError as err:
            self.last_control_failure_stage = err.stage
            raise
        self.last_control_failure_stage = None
        self.last_successful_update = dt_util.utcnow()
        self._process_status(status)
        self.async_set_updated_data(status)

    async def async_control(self, group, action, *args, **kwargs):
        """Only named controls; permission is checked again at service time."""
        actions = {
            "job_controls": {"pause", "resume", "dismiss_completion"},
            "material_controls": {"set_slot"},
            "printer_controls": {"set_speed", "set_auto_shutdown"},
            "temperature_controls": {"set_temperature"},
        }
        if action not in actions.get(group, set()) or not self.entry.options.get(group, False):
            raise PrinterError("Enable this control group in the integration's configuration first")
        try:
            status = await getattr(self.client, action)(*args, **kwargs)
        except ControlError as err:
            self.last_control_failure_stage = err.stage
            raise
        self.last_control_failure_stage = None
        self.last_successful_update = dt_util.utcnow()
        self._process_status(status)
        self.async_set_updated_data(status)


async def async_migrate_entry(hass, entry):
    """Use Celsius for old automatic units, preserving explicit entity overrides."""
    if entry.version != 1:
        return False
    if entry.minor_version < 2:
        from .sensor import SENSORS

        temperature_ids = {
            f"{entry.data[CONF_SERIAL]}_{key}"
            for key, _name, _unit, device_class in SENSORS
            if device_class == "temperature"
        }
        registry = er.async_get(hass)
        for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
            if (
                entity.domain != "sensor"
                or entity.platform != "creator5"
                or entity.unique_id not in temperature_ids
            ):
                continue
            options = dict(entity.options.get("sensor", {}))
            if "unit_of_measurement" not in options:
                options["unit_of_measurement"] = UnitOfTemperature.CELSIUS
                registry.async_update_entity_options(entity.entity_id, "sensor", options)
        hass.config_entries.async_update_entry(entry, minor_version=2)
    return True
