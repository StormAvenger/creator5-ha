"""Cached troubleshooting must not expose secrets or send extra requests."""

import json
from unittest.mock import AsyncMock, patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.creator5.const import DOMAIN
from custom_components.creator5.creator5py import PrinterError, PrinterStatus
from custom_components.creator5.diagnostics import async_get_config_entry_diagnostics

DATA = {"host": "10.0.0.42", "serial_number": "PRIVATE-SERIAL", "check_code": "PRIVATE-CODE"}


async def test_diagnostics_uses_cache_and_excludes_arbitrary_secrets(hass):
    entry = MockConfigEntry(domain=DOMAIN, data=DATA, unique_id=DATA["serial_number"])
    entry.add_to_hass(hass)
    status = PrinterStatus(
        {
            "status": "PRIVATE-STATE",
            "printProgress": 0.25,
            "platTemp": 60,
            "estimatedTime": 120,
            "checkCode": "PRIVATE-CODE",
            "serialNumber": "PRIVATE-SERIAL",
            "cameraStreamUrl": "PRIVATE-URL",
            "futureField": {"token": "PRIVATE-TOKEN"},
        }
    )
    with patch(
        "custom_components.creator5.Creator5Client.get_status",
        new=AsyncMock(return_value=status),
    ) as read:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        requests_before = read.await_count
        report = await async_get_config_entry_diagnostics(hass, entry)
        assert report == {
            "read_only": True,
            "last_update_success": True,
            "cached_readings": {
                "progress_percent": 25,
                "bed_c": 60,
                "chamber_c": None,
                "remaining_seconds": 120,
                "tool_temperatures_c": [None, None, None, None],
                "tool_targets_c": [None, None, None, None],
            },
        }
        assert "PRIVATE" not in json.dumps(report)
        assert DATA["host"] not in json.dumps(report)
        assert read.await_count == requests_before

        read.side_effect = PrinterError("PRIVATE-ERROR")
        await entry.runtime_data.async_refresh()
        requests_before = read.await_count
        report = await async_get_config_entry_diagnostics(hass, entry)
        assert report["last_update_success"] is False
        assert report["cached_readings"]["bed_c"] == 60
        assert "PRIVATE" not in json.dumps(report)
        assert read.await_count == requests_before
        assert await hass.config_entries.async_unload(entry.entry_id)


async def test_diagnostics_before_setup_has_no_readings(hass):
    entry = MockConfigEntry(domain=DOMAIN, data=DATA)
    assert await async_get_config_entry_diagnostics(hass, entry) == {
        "read_only": True,
        "last_update_success": None,
        "cached_readings": None,
    }
