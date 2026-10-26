"""Shared opt-in and service errors for explicitly requested printer controls."""

from homeassistant.exceptions import HomeAssistantError

from .creator5py import PrinterError
from .entity import Creator5Entity


class Creator5Control(Creator5Entity):
    def __init__(self, coordinator, serial, key, name, group, states):
        super().__init__(coordinator, serial, key, name)
        self._group = group
        self._states = states

    @property
    def available(self):
        return (
            super().available
            and self.coordinator.entry.options.get(self._group, False)
            and self.coordinator.data.state in self._states
        )

    async def _run(self, action, *args, **kwargs):
        try:
            await self.coordinator.async_control(self._group, action, *args, **kwargs)
        except (PrinterError, ValueError) as err:
            raise HomeAssistantError(str(err)) from err
