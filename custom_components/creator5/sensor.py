"""A small set of provisional status sensors; no printer controls."""

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import PERCENTAGE, UnitOfTemperature, UnitOfTime

from .const import CONF_SERIAL
from .entity import Creator5Entity

# Unknown or absent fields return None, not a fabricated zero.
TOOL_SENSORS = {
    f"tool_{index + 1}_{kind}": (index, target)
    for index in range(4)
    for kind, target in (("temperature", False), ("target_temperature", True))
}
SENSORS = (
    ("status", "State", None, None),
    ("printProgress", "Print progress", PERCENTAGE, None),
    ("platTemp", "Bed temperature", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE),
    (
        "chamberTemp",
        "Chamber temperature",
        UnitOfTemperature.CELSIUS,
        SensorDeviceClass.TEMPERATURE,
    ),
    ("estimatedTime", "Remaining time", UnitOfTime.SECONDS, SensorDeviceClass.DURATION),
    (
        "platTargetTemp",
        "Bed target temperature",
        UnitOfTemperature.CELSIUS,
        SensorDeviceClass.TEMPERATURE,
    ),
    (
        "chamberTargetTemp",
        "Chamber target temperature",
        UnitOfTemperature.CELSIUS,
        SensorDeviceClass.TEMPERATURE,
    ),
    ("printDuration", "Elapsed time", UnitOfTime.SECONDS, SensorDeviceClass.DURATION),
    ("printLayer", "Current layer", None, None),
    ("targetPrintLayer", "Total layers", None, None),
    ("chamberFanSpeed", "Reported chamber fan", PERCENTAGE, None),
    ("coolingFanSpeed", "Reported cooling fan", PERCENTAGE, None),
) + tuple(
    (
        key,
        f"Tool {index + 1} {'target temperature' if target else 'temperature'}",
        UnitOfTemperature.CELSIUS,
        SensorDeviceClass.TEMPERATURE,
    )
    for key, (index, target) in TOOL_SENSORS.items()
)


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(
        [Creator5Sensor(entry.runtime_data, entry.data[CONF_SERIAL], spec) for spec in SENSORS]
        + [
            Creator5Material(entry.runtime_data, entry.data[CONF_SERIAL], slot)
            for slot in range(1, 5)
        ]
    )


class Creator5Sensor(Creator5Entity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, serial, spec):
        (
            self._key,
            self._attr_name,
            self._attr_native_unit_of_measurement,
            self._attr_device_class,
        ) = spec
        super().__init__(coordinator, serial, self._key, self._attr_name)
        if self._attr_device_class == SensorDeviceClass.TEMPERATURE:
            self._attr_suggested_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_suggested_display_precision = (
            None
            if self._key == "status"
            else (
                1
                if self._key == "printProgress"
                or self._attr_device_class == SensorDeviceClass.TEMPERATURE
                else 0
            )
        )

    @property
    def native_value(self):
        status = self.coordinator.data
        if self._key == "status":
            return status.state
        if self._key == "printProgress":
            return status.progress_percent
        if self._key in TOOL_SENSORS:
            index, target = TOOL_SENSORS[self._key]
            return status.nozzle_temperature(index, target=target)
        maximum = 100 if self._key in ("chamberFanSpeed", "coolingFanSpeed") else None
        value = status.nonnegative(self._key, maximum=maximum)
        if (
            self._key in ("printLayer", "targetPrintLayer")
            and value is not None
            and not value.is_integer()
        ):
            return None
        return value


class Creator5Material(Creator5Entity, SensorEntity):
    def __init__(self, coordinator, serial, slot):
        super().__init__(coordinator, serial, f"slot_{slot}_material", f"Slot {slot} material")
        self._slot = slot

    @property
    def native_value(self):
        slot = self.coordinator.data.material_slot(self._slot)
        return slot["material"] if slot is not None else None

    @property
    def extra_state_attributes(self):
        slot = self.coordinator.data.material_slot(self._slot)
        return {"color": slot["color"]} if slot is not None and slot["color"] is not None else {}
