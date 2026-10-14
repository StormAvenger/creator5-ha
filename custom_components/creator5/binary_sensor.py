"""Read-only Pro door/lid and material-presence signals."""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity

from .const import CONF_SERIAL
from .entity import Creator5Entity


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    entities = [
        Creator5Filament(coordinator, entry.data[CONF_SERIAL], slot) for slot in range(1, 5)
    ]
    if coordinator.data.is_pro:
        entities.append(Creator5Door(coordinator, entry.data[CONF_SERIAL]))
    async_add_entities(entities)


class Creator5Door(Creator5Entity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.DOOR

    def __init__(self, coordinator, serial):
        super().__init__(coordinator, serial, "door", "Door or lid")

    @property
    def is_on(self):
        status = self.coordinator.data
        return status.open_state("doorStatus") if status.is_pro else None


class Creator5Filament(Creator5Entity, BinarySensorEntity):
    def __init__(self, coordinator, serial, slot):
        super().__init__(
            coordinator, serial, f"slot_{slot}_filament", f"Slot {slot} filament present"
        )
        self._slot = slot

    @property
    def is_on(self):
        slot = self.coordinator.data.material_slot(self._slot)
        return slot["has_filament"] if slot is not None else None
