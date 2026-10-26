"""Opt-in auto-shutdown configuration; never powers off the printer directly."""

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory

from .const import CONF_SERIAL
from .control import Creator5Control


async def async_setup_entry(hass, entry, async_add_entities):
    if entry.runtime_data.options["printer_controls"]:
        async_add_entities([Creator5Shutdown(entry.runtime_data, entry.data[CONF_SERIAL])])


class Creator5Shutdown(Creator5Control, SwitchEntity):
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, serial):
        super().__init__(
            coordinator,
            serial,
            "auto_shutdown_control",
            "Auto shutdown",
            "printer_controls",
            ("ready",),
        )

    @property
    def is_on(self):
        return self.coordinator.data.open_state("autoShutdown")

    async def async_turn_on(self, **kwargs):
        await self._run("set_auto_shutdown", enabled=True)

    async def async_turn_off(self, **kwargs):
        await self._run("set_auto_shutdown", enabled=False)
