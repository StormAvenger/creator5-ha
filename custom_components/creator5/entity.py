"""Shared identity for entities using the same cached status response."""

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


class Creator5Entity(CoordinatorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, serial, key, name):
        super().__init__(coordinator)
        self._attr_name = name
        self._attr_unique_id = f"{serial}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)}, manufacturer="FlashForge", name="Creator 5"
        )
