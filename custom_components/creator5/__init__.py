"""Experimental, read-only Creator 5 integration."""

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_CHECK_CODE, CONF_SERIAL
from .creator5py import AuthenticationError, Creator5Client, PrinterError

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    client = Creator5Client(
        async_get_clientsession(hass),
        entry.data[CONF_HOST],
        entry.data[CONF_SERIAL],
        entry.data[CONF_CHECK_CODE],
    )

    async def update():
        try:
            return await client.get_status()
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except PrinterError as err:
            raise UpdateFailed(str(err)) from err

    coordinator = DataUpdateCoordinator(
        hass,
        logging.getLogger(__name__),
        name="Creator 5",
        update_method=update,
        update_interval=timedelta(seconds=30),
        config_entry=entry,
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
