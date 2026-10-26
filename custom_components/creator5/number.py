"""Bounded speed, delay and Celsius heater targets, enabled explicitly in options."""

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import EntityCategory

from .const import CONF_SERIAL
from .control import Creator5Control


async def async_setup_entry(hass, entry, async_add_entities):
    c = entry.runtime_data
    specs = []
    if c.options["printer_controls"]:
        specs += [
            ("speed", "Speed override", "printer_controls", ("printing",), 50, 150, "%"),
            ("delay", "Auto shutdown delay", "printer_controls", ("ready",), 1, 120, "min"),
        ]
    if c.options["temperature_controls"]:
        states = ("ready", "printing", "paused", "pause")
        specs += [("bed", "Bed temperature target", "temperature_controls", states, 0, 120, "°C")]
        if c.data.is_pro:
            specs += [
                (
                    "chamber",
                    "Chamber temperature target",
                    "temperature_controls",
                    states,
                    0,
                    65,
                    "°C",
                )
            ]
        specs += [
            (
                f"tool_{i}",
                f"Tool {i} temperature target",
                "temperature_controls",
                states,
                0,
                320,
                "°C",
            )
            for i in range(1, 5)
        ]
    async_add_entities([Creator5Number(c, entry.data[CONF_SERIAL], spec) for spec in specs])


class Creator5Number(Creator5Control, NumberEntity):
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator, serial, spec):
        key, name, group, states, low, high, unit = spec
        super().__init__(coordinator, serial, f"control_{key}", name, group, states)
        self._key = key
        self._attr_native_min_value, self._attr_native_max_value = low, high
        self._attr_native_unit_of_measurement = unit
        # Deliberately no temperature device class: NumberEntity otherwise
        # converts targets to the host's Fahrenheit default. Units remain °C.
        if key == "delay":
            self._attr_entity_category = EntityCategory.CONFIG

    @property
    def native_value(self):
        status = self.coordinator.data
        if self._key.startswith("tool_"):
            return status.nozzle_temperature(int(self._key[-1]) - 1, target=True)
        field = {
            "speed": "printSpeedAdjust",
            "delay": "autoShutdownTime",
            "bed": "platTargetTemp",
            "chamber": "chamberTargetTemp",
        }[self._key]
        return status.nonnegative(field)

    async def async_set_native_value(self, value):
        if self._key == "speed":
            await self._run("set_speed", value)
        elif self._key == "delay":
            await self._run("set_auto_shutdown", minutes=value)
        else:
            await self._run("set_temperature", self._key, value)
