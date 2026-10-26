"""Edit slot metadata through the printer's exact palette; no loading/unloading."""

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory

from .const import CONF_SERIAL
from .control import Creator5Control
from .creator5py.palette import COLORS, MATERIALS


async def async_setup_entry(hass, entry, async_add_entities):
    if entry.runtime_data.options["material_controls"]:
        async_add_entities(
            [
                Creator5SlotSelect(entry.runtime_data, entry.data[CONF_SERIAL], slot, kind)
                for slot in range(1, 5)
                for kind in ("material", "color")
            ]
        )


class Creator5SlotSelect(Creator5Control, SelectEntity):
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, serial, slot, kind):
        super().__init__(
            coordinator,
            serial,
            f"slot_{slot}_{kind}_control",
            f"Slot {slot} {kind} setting",
            "material_controls",
            ("ready",),
        )
        self._slot, self._kind = slot, kind
        self._attr_options = list(MATERIALS if kind == "material" else COLORS)

    @property
    def current_option(self):
        slot = self.coordinator.data.material_slot(self._slot)
        if slot is None:
            return None
        if self._kind == "material":
            return slot["material"] if slot["material"] in MATERIALS else None
        return next((name for name, rgb in COLORS.items() if rgb == slot["color"]), None)

    async def async_select_option(self, option):
        if option not in self.options:
            from homeassistant.exceptions import HomeAssistantError

            raise HomeAssistantError("Choose an available printer palette option")
        value = option if self._kind == "material" else COLORS[option]
        await self._run("set_slot", self._slot, **{self._kind: value})
