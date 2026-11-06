"""Brief-glitch grace, offline polling back-off and recovery."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntryState
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.creator5 import OFFLINE_POLL_SECONDS, STALE_POLLS
from custom_components.creator5.const import DOMAIN
from custom_components.creator5.creator5py import (
    AuthenticationError,
    PrinterError,
    PrinterStatus,
)
from custom_components.creator5.diagnostics import async_get_config_entry_diagnostics

DATA = {"host": "10.0.0.42", "serial_number": "SYNTHETIC-SN", "check_code": "synthetic-code"}
BASE = {
    "status": "printing",
    "model": "Creator 5 Pro",
    "printFileName": "a.3mf",
    "printDuration": 100,
    "platTemp": 60,
    "lightStatus": "close",
}
BED = "sensor.creator_5_bed_temperature"
CONNECTION = "binary_sensor.creator_5_status_connection"
READ = "custom_components.creator5.Creator5Client.get_status"


async def setup(hass):
    entry = MockConfigEntry(domain=DOMAIN, data=DATA, minor_version=2)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def poll(hass, entry):
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()


async def test_brief_glitch_keeps_last_reading_then_goes_unavailable(hass):
    with patch(READ, new=AsyncMock(return_value=PrinterStatus(BASE))) as read:
        entry = await setup(hass)
        coordinator = entry.runtime_data
        read.side_effect = PrinterError("Timeout")
        for failures in range(1, STALE_POLLS + 1):
            await poll(hass, entry)
            assert hass.states.get(BED).state == "60.0"
            assert hass.states.get(CONNECTION).state == "on"
            assert coordinator.consecutive_failures == failures
            assert coordinator.update_interval == timedelta(seconds=10)
        # A glitch is still an observation gap for the print record.
        assert coordinator.history.active["incomplete"] is True
        await poll(hass, entry)
        assert hass.states.get(BED).state == "unavailable"
        assert hass.states.get(CONNECTION).state == "off"
        report = await async_get_config_entry_diagnostics(hass, entry)
        assert report["consecutive_failures"] == STALE_POLLS + 1
        assert report["poll_seconds"] == 10
        assert report["current_poll_seconds"] == OFFLINE_POLL_SECONDS
        assert await hass.config_entries.async_unload(entry.entry_id)


async def test_offline_backoff_and_immediate_return_to_normal_polling(hass):
    with patch(READ, new=AsyncMock(return_value=PrinterStatus(BASE))) as read:
        entry = await setup(hass)
        coordinator = entry.runtime_data
        read.side_effect = PrinterError("Off")
        for _ in range(STALE_POLLS + 3):
            await poll(hass, entry)
        assert coordinator.update_interval == timedelta(seconds=OFFLINE_POLL_SECONDS)
        read.side_effect = None
        await poll(hass, entry)
        assert coordinator.update_interval == timedelta(seconds=10)
        assert coordinator.consecutive_failures == 0
        assert hass.states.get(BED).state == "60.0"
        assert await hass.config_entries.async_unload(entry.entry_id)


async def test_glitch_after_recovery_gets_a_fresh_grace(hass):
    with patch(READ, new=AsyncMock(return_value=PrinterStatus(BASE))) as read:
        entry = await setup(hass)
        read.side_effect = PrinterError("Timeout")
        await poll(hass, entry)
        read.side_effect = None
        await poll(hass, entry)
        read.side_effect = PrinterError("Timeout")
        for _ in range(STALE_POLLS):
            await poll(hass, entry)
        assert hass.states.get(BED).state == "60.0"
        assert await hass.config_entries.async_unload(entry.entry_id)


async def test_verified_control_resets_failure_count(hass):
    with (
        patch(READ, new=AsyncMock(return_value=PrinterStatus(BASE))) as read,
        patch(
            "custom_components.creator5.Creator5Client.set_light",
            new=AsyncMock(return_value=PrinterStatus({**BASE, "lightStatus": "open"})),
        ),
    ):
        entry = await setup(hass)
        read.side_effect = PrinterError("Timeout")
        await poll(hass, entry)
        await entry.runtime_data.async_set_light(True)
        assert entry.runtime_data.consecutive_failures == 0
        assert await hass.config_entries.async_unload(entry.entry_id)


async def test_rejected_credentials_get_no_grace(hass):
    with patch(READ, new=AsyncMock(return_value=PrinterStatus(BASE))) as read:
        entry = await setup(hass)
        read.side_effect = AuthenticationError("Rejected")
        await poll(hass, entry)
        await hass.async_block_till_done()
        assert hass.states.get(BED).state == "unavailable"
        assert any(
            f["context"]["source"] == "reauth" for f in hass.config_entries.flow.async_progress()
        )
        assert entry.state is ConfigEntryState.LOADED
        assert await hass.config_entries.async_unload(entry.entry_id)
