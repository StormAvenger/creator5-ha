"""Optional automatic acknowledgement of the printer's "print complete" screen.

Off by default. When enabled, a completed print is acknowledged once after the
configured delay, unless someone acknowledges it first or a new job starts. The
acknowledgement tells the printer the bed is clear; nothing checks that it is.
"""

import logging

from homeassistant.core import callback
from homeassistant.helpers.event import async_call_later

from .creator5py import PrinterError

_LOGGER = logging.getLogger(__name__)


class AutoDismiss:
    def __init__(self, coordinator):
        self.c = coordinator
        self.timer = None
        # Set once a command has been sent for the current completed screen, so
        # a failure is never retried; cleared when the printer leaves it.
        self.attempted = False

    @property
    def enabled(self):
        return self.c.options["auto_dismiss_completion"]

    def cancel(self):
        if self.timer:
            self.timer()
            self.timer = None

    def observe(self, status):
        """Start the countdown on the completed screen; stop it when that ends."""
        if status.state != "completed":
            self.attempted = False
        if not self.enabled or status.state != "completed":
            self.cancel()
            return
        if self.timer or self.attempted:
            return
        self.timer = async_call_later(
            self.c.hass, self.c.options["auto_dismiss_minutes"] * 60, self._due
        )

    @callback
    def _due(self, _now):
        self.timer = None
        # Offline or already dismissed: send nothing. If the screen is still up
        # when the printer is next seen, a new countdown starts.
        if self.c.last_update_success and self.c.data.state == "completed":
            self.attempted = True
            self.c.entry.async_create_background_task(
                self.c.hass, self._dismiss(), "Creator 5 auto-dismiss completion"
            )

    async def _dismiss(self):
        # One command; the client re-checks "completed" and verifies by readback.
        # Never retried: if it fails, the screen simply stays until pressed.
        try:
            await self.c.async_dismiss_completion()
        except PrinterError as err:
            _LOGGER.warning("Could not automatically dismiss the print-complete screen: %s", err)
        else:
            _LOGGER.info("Print-complete screen dismissed automatically")
