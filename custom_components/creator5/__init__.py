"""Experimental Creator 5 monitoring and chamber-light control."""

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_CHECK_CODE, CONF_SERIAL
from .creator5py import AuthenticationError, Creator5Client, PrinterError, PrinterStatus

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.LIGHT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    client = Creator5Client(
        async_get_clientsession(hass),
        entry.data[CONF_HOST],
        entry.data[CONF_SERIAL],
        entry.data[CONF_CHECK_CODE],
    )

    coordinator = Creator5Coordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


class Creator5Coordinator(DataUpdateCoordinator[PrinterStatus]):
    def __init__(self, hass, entry, client):
        super().__init__(
            hass,
            logging.getLogger(__name__),
            name="Creator 5",
            update_interval=timedelta(seconds=30),
            config_entry=entry,
        )
        self.client = client

    async def _async_update_data(self):
        try:
            return await self.client.get_status()
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except PrinterError as err:
            raise UpdateFailed(str(err)) from err

    async def async_set_light(self, on):
        # The client verifies the light state before publishing the shared snapshot.
        status = await self.client.set_light(on)
        self.async_set_updated_data(status)


async def async_migrate_entry(hass, entry):
    """Use Celsius for old automatic units, preserving explicit entity overrides."""
    if entry.version != 1:
        return False
    if entry.minor_version < 2:
        from .sensor import SENSORS

        temperature_ids = {
            f"{entry.data[CONF_SERIAL]}_{key}"
            for key, _name, _unit, device_class in SENSORS
            if device_class == "temperature"
        }
        registry = er.async_get(hass)
        for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
            if (
                entity.domain != "sensor"
                or entity.platform != "creator5"
                or entity.unique_id not in temperature_ids
            ):
                continue
            options = dict(entity.options.get("sensor", {}))
            if "unit_of_measurement" not in options:
                options["unit_of_measurement"] = UnitOfTemperature.CELSIUS
                registry.async_update_entity_options(entity.entity_id, "sensor", options)
        hass.config_entries.async_update_entry(entry, minor_version=2)
    return True
