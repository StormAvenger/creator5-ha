"""Experimental Creator 5 monitoring and chamber-light control."""

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import CONF_CHECK_CODE, CONF_SERIAL
from .creator5py import AuthenticationError, Creator5Client, PrinterError, PrinterStatus
from .creator5py.client import ControlError
from .settings import validated_options

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


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    client = Creator5Client(
        async_get_clientsession(hass),
        entry.data[CONF_HOST],
        entry.data[CONF_SERIAL],
        entry.data[CONF_CHECK_CODE],
    )

    coordinator = Creator5Coordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_options))
    return True


async def async_reload_options(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


class Creator5Coordinator(DataUpdateCoordinator[PrinterStatus]):
    def __init__(self, hass, entry, client):
        self.entry = entry
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
            self._update_completion(status)
            return status
        except AuthenticationError as err:
            self.estimated_completion = None
            raise ConfigEntryAuthFailed(str(err)) from err
        except PrinterError as err:
            self.estimated_completion = None
            raise UpdateFailed(str(err)) from err

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
        self._update_completion(status)
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
        self._update_completion(status)
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
