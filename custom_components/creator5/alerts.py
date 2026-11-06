"""Alert events: completion, cooling, errors, pauses, outages, maintenance, pictures.

The coordinator owns polling and printer state; this module only decides when to
announce something and fires `creator5_event` for automations to deliver.
"""

import asyncio
import logging

from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.event import async_call_later

from .const import ACTIVE_STATES, CONF_SERIAL, DOMAIN
from .creator5py import PrinterError
from .error_info import explanation
from .history import MAINTENANCE
from .snapshots import SNAPSHOT_KINDS, async_save_snapshot

_LOGGER = logging.getLogger(__name__)
EVENT = "creator5_event"


async def _light_warmup(seconds):
    """Let the chamber light and camera exposure settle before the picture."""
    await asyncio.sleep(seconds)


class Creator5Alerts:
    def __init__(self, coordinator):
        self.c = coordinator
        self.observed_once = False  # never replay alerts for the first status seen
        self._last_error = None
        self._maintenance_due = {}
        self.pause_timer = None
        self.offline_timer = None
        self._pause_notified = False
        self._offline_notified = False
        self._snapshot_lock = asyncio.Lock()

    @property
    def options(self):
        return self.c.options

    # Lifecycle

    def cancel_timers(self):
        for name in ("pause_timer", "offline_timer"):
            if timer := getattr(self, name):
                timer()
                setattr(self, name, None)

    # Inputs from the coordinator

    def connection_failed(self):
        """Arm the lost-connection alert; only an outage during a job is alert-worthy."""
        data = self.c.data
        if (
            not self.observed_once
            or self.offline_timer
            or self._offline_notified
            or data is None
            or data.state not in ACTIVE_STATES
        ):
            return

        @callback
        def offline(_now):
            self.offline_timer = None
            if not self.c.last_update_success:
                self._offline_notified = True
                self.emit(
                    "offline", "Printer connection was lost during a print and has not recovered."
                )

        self.offline_timer = async_call_later(
            self.c.hass, self.options["offline_alert_minutes"] * 60, offline
        )

    def observe(self, status, history_events):
        """Announce changes in one fresh status reading."""
        if self.offline_timer:
            self.offline_timer()
            self.offline_timer = None
        self._offline_notified = False
        for kind in history_events:
            self.emit(
                kind,
                {
                    "completed": "Printer reports the print completed.",
                    "bed_cooled": (
                        f"Print bed is below {self.options['bed_cooled_c']} °C with its target off."
                    ),
                }[kind],
            )
        self._observe_error(status)
        self._observe_pause(status)
        self._observe_maintenance(status)
        self.observed_once = True

    def service_recorded(self, key):
        self._maintenance_due[key] = False

    def _observe_error(self, status):
        error = (status.error_code, status.state == "error")
        if error != self._last_error and (status.error_code not in (None, "none") or error[1]):
            title, hint, _known = explanation(status)
            code = status.error_code if status.error_code not in (None, "none") else "Printer error"
            self.emit("error", f"{code}: {title or 'Check the printer screen'}. {hint or ''}")
        if status.error_code is not None or error[1]:
            self._last_error = error

    def _observe_pause(self, status):
        if status.state not in ("paused", "pause"):
            if self.pause_timer:
                self.pause_timer()
                self.pause_timer = None
            self._pause_notified = False
            return
        if self.pause_timer or self._pause_notified:
            return

        @callback
        def paused(_now):
            self.pause_timer = None
            if self.c.last_update_success and self.c.data.state in ("paused", "pause"):
                self._pause_notified = True
                self.emit(
                    "prolonged_pause", "Printer has remained paused for the configured interval."
                )

        self.pause_timer = async_call_later(
            self.c.hass, self.options["pause_alert_minutes"] * 60, paused
        )

    def _observe_maintenance(self, status):
        for key, label in MAINTENANCE.items():
            remaining = self.c.history.remaining(key, status.lifetime_print_hours, self.options)
            if remaining is None:
                continue
            due = remaining <= 0
            if due and self._maintenance_due.get(key) is False:
                self.emit(
                    "maintenance",
                    f"{label} reminder is due based on your configured printing hours.",
                )
            self._maintenance_due[key] = due

    # Delivery

    def emit(self, kind, message):
        if not self.observed_once:
            return
        if kind in SNAPSHOT_KINDS and self.options["alert_snapshots"] and self.c.camera is not None:
            # The alert is sent once the picture is saved, typically 10–20 s later.
            self.c.entry.async_create_background_task(
                self.c.hass, self._emit_with_snapshot(kind, message), "Creator 5 alert snapshot"
            )
            return
        self._fire(kind, message, None)

    def _fire(self, kind, message, image):
        entry = self.c.entry
        device = dr.async_get(self.c.hass).async_get_device_by_identifier(
            (DOMAIN, entry.data[CONF_SERIAL]), entry.entry_id
        )
        self.c.hass.bus.async_fire(
            EVENT,
            {
                "entry_id": entry.entry_id,
                "device_id": device.id if device else None,
                "kind": kind,
                "message": message,
                "image": image,
            },
        )

    async def _emit_with_snapshot(self, kind, message):
        """Light on (if it was off), wait, capture, alert, then restore the light."""
        async with self._snapshot_lock:
            delay = self.options["snapshot_light_seconds"]
            # Only toggle a light reported off, so its previous state is known and
            # restorable. A light already on, or of unknown state, is left alone.
            switch_light = delay > 0 and self.c.data.open_state("lightStatus") is False
            light_confirmed = False
            if switch_light:
                try:
                    await self.c.async_set_light(True)
                    light_confirmed = True
                except PrinterError as err:
                    # E.g. a network timeout: take the picture regardless.
                    _LOGGER.debug("Snapshot light could not be confirmed on: %s", err)
                if light_confirmed:
                    await _light_warmup(delay)
            image = None
            try:
                frame = await self.c.camera.async_camera_image()
                if frame:
                    image = await async_save_snapshot(
                        self.c.hass, self.c.entry.entry_id, kind, frame
                    )
            except (OSError, PrinterError) as err:
                _LOGGER.warning("Could not save the alert snapshot: %s", err)
            self._fire(kind, message, image)
            if switch_light:
                await self._restore_light_off(light_confirmed)

    async def _restore_light_off(self, confirmed_on):
        """Send one off command, and only when the light is (or may be) on."""
        if not confirmed_on:
            # The on command's outcome was unconfirmed; check before writing.
            try:
                status = await self.c.client.get_status()
            except PrinterError:
                return
            if status.open_state("lightStatus") is not True:
                return
        try:
            await self.c.async_set_light(False)
        except PrinterError as err:
            _LOGGER.warning("Chamber light may still be on after the alert snapshot: %s", err)
