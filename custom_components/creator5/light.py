"""Chamber LED only: no brightness, fan, heater or print controls."""

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.exceptions import HomeAssistantError

from .const import CONF_SERIAL
from .creator5py import PrinterError
from .entity import Creator5Entity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([Creator5Light(entry.runtime_data, entry.data[CONF_SERIAL])])


class Creator5Light(Creator5Entity, LightEntity):
    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_color_mode = ColorMode.ONOFF

    def __init__(self, coordinator, serial):
        super().__init__(coordinator, serial, "chamber_light", "Chamber light")

    @property
    def is_on(self):
        return self.coordinator.data.open_state("lightStatus")

    async def _set_light(self, on):
        try:
            await self.coordinator.async_set_light(on)
        except PrinterError as err:
            raise HomeAssistantError(str(err)) from err

    async def async_turn_on(self, **kwargs):
        await self._set_light(True)

    async def async_turn_off(self, **kwargs):
        await self._set_light(False)
