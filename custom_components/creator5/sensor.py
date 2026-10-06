"""A small set of provisional status sensors; no printer controls."""

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import PERCENTAGE, UnitOfTemperature, UnitOfTime
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_SERIAL, DOMAIN

# Unknown or absent fields return None, not a fabricated zero.
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
)


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(
        Creator5Sensor(entry.runtime_data, entry.data[CONF_SERIAL], spec) for spec in SENSORS
    )


class Creator5Sensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, serial, spec):
        super().__init__(coordinator)
        (
            self._key,
            self._attr_name,
            self._attr_native_unit_of_measurement,
            self._attr_device_class,
        ) = spec
        self._attr_unique_id = f"{serial}_{self._key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
            manufacturer="FlashForge",
            name="Creator 5",
        )

    @property
    def native_value(self):
        status = self.coordinator.data
        if self._key == "status":
            return status.state
        if self._key == "printProgress":
            return status.progress_percent
        return status.number(self._key)
