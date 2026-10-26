"""A small set of provisional status sensors; no printer controls."""

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfInformation,
    UnitOfLength,
    UnitOfTemperature,
    UnitOfTime,
)

from .const import CONF_SERIAL
from .entity import Creator5Entity

# Unknown or absent fields return None, not a fabricated zero.
PRO_ONLY_SENSORS = {"chamberTemp", "chamberTargetTemp", "chamberFanSpeed"}
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
        [
            Creator5Sensor(entry.runtime_data, entry.data[CONF_SERIAL], spec)
            for spec in SENSORS
            if spec[0] not in PRO_ONLY_SENSORS or entry.runtime_data.data.is_pro
        ]
        + [
            Creator5Material(entry.runtime_data, entry.data[CONF_SERIAL], slot)
            for slot in range(1, 5)
        ]
        + [
            Creator5SlotColor(entry.runtime_data, entry.data[CONF_SERIAL], slot)
            for slot in range(1, 5)
        ]
        + [Creator5Nozzle(entry.runtime_data, entry.data[CONF_SERIAL], index) for index in range(4)]
        + [
            Creator5ToolMaterial(entry.runtime_data, entry.data[CONF_SERIAL], tool)
            for tool in range(1, 5)
        ]
        + [
            Creator5Info(entry.runtime_data, entry.data[CONF_SERIAL], key, name)
            for key, name in (
                ("model", "Model"),
                ("firmware_version", "Firmware version"),
                ("error_code", "Error code"),
            )
        ]
        + [Creator5LastUpdate(entry.runtime_data, entry.data[CONF_SERIAL])]
        + [
            Creator5JobSensor(entry.runtime_data, entry.data[CONF_SERIAL], key)
            for key in ("filename", "completion", "lifetime", "storage")
        ]
        + [
            Creator5Telemetry(entry.runtime_data, entry.data[CONF_SERIAL], key)
            for key in (
                "filament",
                "speed",
                "offset",
                "shutdown_delay",
                "station_slot",
                "loading_slot",
            )
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
        if self._key in ("printProgress", "printLayer", "targetPrintLayer"):
            # HA's Activity filters continuous sensors by state class as well as
            # units. Recorder history remains available; no host YAML or purge.
            self._attr_state_class = SensorStateClass.MEASUREMENT
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
        if self._key == "estimatedTime" and status.state not in ("printing", "paused", "pause"):
            return None
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


class Creator5SlotColor(Creator5Entity, SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, serial, slot):
        super().__init__(coordinator, serial, f"slot_{slot}_color", f"Slot {slot} color")
        self._slot = slot

    @property
    def native_value(self):
        slot = self.coordinator.data.material_slot(self._slot)
        return slot["color"] if slot else None


class Creator5Nozzle(Creator5Entity, SensorEntity):
    _attr_native_unit_of_measurement = UnitOfLength.MILLIMETERS
    _attr_suggested_unit_of_measurement = UnitOfLength.MILLIMETERS
    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_suggested_display_precision = 2

    def __init__(self, coordinator, serial, index):
        super().__init__(
            coordinator, serial, f"tool_{index + 1}_diameter", f"Tool {index + 1} nozzle diameter"
        )
        self._index = index

    @property
    def native_value(self):
        return self.coordinator.data.nozzle_diameter(self._index)


class Creator5ToolMaterial(Creator5Entity, SensorEntity):
    def __init__(self, coordinator, serial, tool):
        super().__init__(
            coordinator,
            serial,
            f"tool_{tool}_material",
            f"Tool {tool} material (configured mapping)",
        )
        self._tool = tool

    def _slot(self):
        return self.coordinator.options[f"tool_{self._tool}_slot"]

    @property
    def native_value(self):
        slot = self._slot()
        material = self.coordinator.data.material_slot(slot) if slot else None
        return material["material"] if material else None

    @property
    def extra_state_attributes(self):
        slot_id = self._slot()
        material = self.coordinator.data.material_slot(slot_id) if slot_id else None
        return {
            "configured_slot": slot_id or None,
            "mapping_source": "user_configured" if slot_id else "unassigned",
            "color": material["color"] if material else None,
            "user_note": self.coordinator.options[f"tool_{self._tool}_note"],
        }


class Creator5Info(Creator5Entity, SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, serial, key, name):
        super().__init__(coordinator, serial, key, name)
        self._key = key

    @property
    def native_value(self):
        return getattr(self.coordinator.data, self._key)


class Creator5LastUpdate(Creator5Entity, SensorEntity):
    _attr_entity_registry_enabled_default = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator, serial):
        super().__init__(
            coordinator, serial, "last_successful_update", "Last successful status update"
        )

    @property
    def available(self):
        return True

    @property
    def native_value(self):
        return self.coordinator.last_successful_update


class Creator5JobSensor(Creator5Entity, SensorEntity):
    def __init__(self, coordinator, serial, key):
        names = {
            "filename": "Current print filename",
            "completion": "Estimated finish time",
            "lifetime": "Reported lifetime printing time",
            "storage": "Reported free storage",
        }
        super().__init__(coordinator, serial, f"job_{key}", names[key])
        self._key = key
        if key == "completion":
            self._attr_device_class = SensorDeviceClass.TIMESTAMP
        elif key == "lifetime":
            self._attr_device_class = SensorDeviceClass.DURATION
            self._attr_native_unit_of_measurement = UnitOfTime.HOURS
            self._attr_suggested_display_precision = 1
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        elif key == "storage":
            self._attr_device_class = SensorDeviceClass.DATA_SIZE
            self._attr_native_unit_of_measurement = UnitOfInformation.GIGABYTES
            self._attr_suggested_display_precision = 2
            self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self):
        status = self.coordinator.data
        if self._key == "filename":
            return status.current_filename
        if self._key == "completion":
            return self.coordinator.estimated_completion
        if self._key == "lifetime":
            return status.lifetime_print_hours
        return status.free_storage_gb


class Creator5Telemetry(Creator5Entity, SensorEntity):
    """Validate reported values without guessing undocumented station actions."""

    def __init__(self, coordinator, serial, key):
        names = {
            "filament": "Reported lifetime filament",
            "speed": "Print speed multiplier",
            "offset": "Z offset",
            "shutdown_delay": "Reported auto shutdown delay",
            "station_slot": "Reported material station slot",
            "loading_slot": "Reported material loading slot",
        }
        super().__init__(coordinator, serial, f"telemetry_{key}", names[key])
        self._key = key
        self._attr_native_unit_of_measurement = {
            "filament": "m",
            "speed": "%",
            "offset": "mm",
            "shutdown_delay": "min",
            "station_slot": "slot",
            "loading_slot": "slot",
        }[key]
        if key not in ("station_slot", "loading_slot"):
            self._attr_state_class = (
                SensorStateClass.TOTAL_INCREASING
                if key == "filament"
                else SensorStateClass.MEASUREMENT
            )
        self._attr_suggested_display_precision = 2 if key in ("filament", "offset") else 0
        if key in ("filament", "shutdown_delay"):
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        if key == "shutdown_delay":
            self._attr_device_class = SensorDeviceClass.DURATION

    @property
    def native_value(self):
        status = self.coordinator.data
        if self._key == "filament":
            return status.lifetime_filament_m
        if self._key == "speed":
            return status.nonnegative("printSpeedAdjust", maximum=500)
        if self._key == "offset":
            value = status.number("zAxisCompensation")
            return value if value is not None and -5 <= value <= 5 else None
        if self._key == "shutdown_delay":
            return status.nonnegative("autoShutdownTime", maximum=1440)
        return status.station_number(
            "currentSlot" if self._key == "station_slot" else "currentLoadSlot"
        )

    @property
    def extra_state_attributes(self):
        if self._key not in ("station_slot", "loading_slot"):
            return None
        status = self.coordinator.data
        return {
            "zero_means": "no_reported_slot",
            "action_code": status.station_number("stateAction"),
            "step_code": status.station_number("stateStep"),
        }
