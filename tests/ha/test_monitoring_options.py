"""Polling cadence, scoped material mappings, health and options without the LAN."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.creator5.const import DOMAIN
from custom_components.creator5.creator5py import PrinterError, PrinterStatus
from custom_components.creator5.settings import camera_source, validated_options

DATA = {"host": "10.0.0.42", "serial_number": "SYNTHETIC-SN", "check_code": "synthetic-code"}
DETAIL = {
    "status": "ready",
    "model": "Creator 5 Pro",
    "firmwareVersion": "1.9.9",
    "errorCode": "",
    "nozzleModel": "0.6mm;0.4mm;0.4mm;0.4mm",
    "matlStationInfo": {
        "slotInfos": [
            {"slotId": 3, "materialName": "PETG", "materialColor": "#BEBEBE", "hasFilament": True}
        ]
    },
}


async def test_ten_second_cadence_health_timestamp_and_manual_assignment(hass, freezer):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=DATA,
        options={"tool_3_slot": 3, "tool_3_note": "High flow (user confirmed)"},
        minor_version=2,
    )
    entry.add_to_hass(hass)
    # Timestamp is optional and quiet by default; explicitly opt in for this test.
    er.async_get(hass).async_get_or_create(
        "sensor",
        DOMAIN,
        "SYNTHETIC-SN_last_successful_update",
        config_entry=entry,
        suggested_object_id="creator_5_last_successful_status_update",
        disabled_by=None,
    )
    with patch(
        "custom_components.creator5.Creator5Client.get_status",
        new=AsyncMock(return_value=PrinterStatus(DETAIL)),
    ) as read:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.runtime_data.update_interval == timedelta(seconds=10)
        assert read.await_count == 1
        state = hass.states.get("sensor.creator_5_tool_3_material_configured_mapping")
        assert state.state == "PETG"
        assert state.attributes["configured_slot"] == 3
        assert state.attributes["color"] == "#BEBEBE"
        assert state.attributes["mapping_source"] == "user_configured"
        assert state.attributes["user_note"] == "High flow (user confirmed)"
        assert (
            hass.states.get("sensor.creator_5_tool_1_material_configured_mapping").state
            == "unknown"
        )
        assert hass.states.get("sensor.creator_5_tool_1_nozzle_diameter").state == "0.6"
        assert (
            hass.states.get("sensor.creator_5_tool_1_nozzle_diameter").attributes[
                "unit_of_measurement"
            ]
            == "mm"
        )
        assert hass.states.get("sensor.creator_5_model").state == "Creator 5 Pro"
        assert hass.states.get("sensor.creator_5_firmware_version").state == "1.9.9"
        assert hass.states.get("sensor.creator_5_error_code").state == "none"
        assert hass.states.get("binary_sensor.creator_5_printer_error").state == "off"
        initial = hass.states.get("sensor.creator_5_last_successful_status_update").state
        freezer.tick(timedelta(seconds=5))
        async_fire_time_changed(hass, datetime.now(UTC))
        await hass.async_block_till_done()
        assert read.await_count == 1
        freezer.tick(timedelta(seconds=6))
        async_fire_time_changed(hass, datetime.now(UTC))
        await hass.async_block_till_done()
        assert read.await_count == 2
        latest = hass.states.get("sensor.creator_5_last_successful_status_update").state
        assert latest != initial
        read.side_effect = PrinterError("Disconnected")
        await entry.runtime_data.async_refresh()
        await hass.async_block_till_done()
        assert hass.states.get("binary_sensor.creator_5_status_connection").state == "off"
        assert hass.states.get("sensor.creator_5_last_successful_status_update").state == latest
        assert hass.states.get("sensor.creator_5_firmware_version").state == "unavailable"
        read.side_effect = None
        read.return_value = PrinterStatus({**DETAIL, "errorCode": "E0162"})
        await entry.runtime_data.async_refresh()
        await hass.async_block_till_done()
        assert hass.states.get("binary_sensor.creator_5_status_connection").state == "on"
        assert hass.states.get("binary_sensor.creator_5_printer_error").state == "on"
        assert hass.states.get("sensor.creator_5_error_code").state == "E0162"
        assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize(
    "url",
    [
        "http://8.8.8.8:8080/?action=stream",
        "http://10.0.0.42:8898/detail",
        "http://user:secret@10.0.0.42:8080/?action=stream",
        "http://10.0.0.42:8080/?action=stream&token=secret",
        "file:///tmp/a",
        "http://127.0.0.1:8080/?action=stream",
    ],
)
def test_camera_targets_cannot_escape_the_configured_printer(url):
    assert camera_source(DATA["host"], url) is None
    with pytest.raises(ValueError):
        validated_options({"camera_stream_url": url}, DATA["host"])


@pytest.mark.parametrize(
    "options",
    [
        {"poll_seconds": 1},
        {"poll_seconds": 301},
        {"poll_seconds": 10.5},
        {"tool_1_slot": True},
        {"tool_2_slot": 5},
        {"tool_1_note": "private\ntext"},
    ],
)
def test_invalid_options_are_rejected(options):
    with pytest.raises(ValueError):
        validated_options(options, DATA["host"])


async def test_options_flow_saves_without_printer_commands(hass):
    entry = MockConfigEntry(domain=DOMAIN, data=DATA)
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    with patch("custom_components.creator5.Creator5Client.get_status", new=AsyncMock()) as read:
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                "poll_seconds": 20,
                "camera_enabled": False,
                "camera_stream_url": "",
                "tool_1_slot": "1",
            },
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"]["poll_seconds"] == 20
        assert result["data"]["tool_1_slot"] == 1
        read.assert_not_awaited()


async def test_options_change_reloads_the_coordinator_with_new_interval(hass):
    entry = MockConfigEntry(domain=DOMAIN, data=DATA, minor_version=2)
    entry.add_to_hass(hass)
    with patch(
        "custom_components.creator5.Creator5Client.get_status",
        new=AsyncMock(return_value=PrinterStatus(DETAIL)),
    ) as read:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        original = entry.runtime_data
        assert original.options["poll_seconds"] == 10
        flow = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            flow["flow_id"],
            user_input={
                "poll_seconds": 20,
                "camera_enabled": False,
                "tool_3_slot": "3",
                "tool_3_note": "High flow",
            },
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        await hass.async_block_till_done()
        assert entry.runtime_data is not original
        assert not list(original.async_contexts())
        assert entry.runtime_data.update_interval == timedelta(seconds=20)
        assert entry.runtime_data.options["tool_3_slot"] == 3
        assert read.await_count == 2
        assert (
            hass.states.get("sensor.creator_5_tool_3_material_configured_mapping").state == "PETG"
        )
        assert await hass.config_entries.async_unload(entry.entry_id)
