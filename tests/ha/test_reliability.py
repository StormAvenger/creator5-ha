"""0.6.1 fixes: expected outages, offline startup, address changes, error state, failures."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.creator5.const import DOMAIN
from custom_components.creator5.creator5py import PrinterError, PrinterStatus
from custom_components.creator5.creator5py.discovery import PrinterIdentity

DATA = {"host": "10.0.0.42", "serial_number": "SYNTHETIC-SN", "check_code": "synthetic-code"}
BASE = {
    "status": "ready",
    "model": "Creator 5 Pro",
    "firmwareVersion": "2.0.0",
    "errorCode": "",
    "cumulativePrintTime": 600,
    "platTemp": 25,
    "platTargetTemp": 0,
}
READ = "custom_components.creator5.Creator5Client.get_status"
FLOW_READ = "custom_components.creator5.config_flow.Creator5Client.get_status"
LOOKUP = "custom_components.creator5.config_flow.discover_identity"


def listen(hass):
    events = []

    @callback
    def record(event):
        events.append(event.data["kind"])

    hass.bus.async_listen("creator5_event", record)
    return events


async def setup(hass, data=DATA, options=None):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=data,
        options=options or {},
        unique_id=DATA["serial_number"],
        minor_version=2,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def update(hass, entry, read, **fields):
    read.side_effect = None
    read.return_value = PrinterStatus({**BASE, **fields})
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()


async def go_offline(hass, entry, read, freezer, minutes=2):
    read.side_effect = PrinterError("Offline")
    await entry.runtime_data.async_refresh()
    freezer.tick(timedelta(minutes=minutes))
    async_fire_time_changed(hass, datetime.now(UTC))
    await hass.async_block_till_done()


# 1. Connection-lost alerts only during a job


@pytest.mark.parametrize("last", ["ready", "completed", "error", "cancel"])
async def test_power_off_while_not_printing_does_not_alert(hass, freezer, last):
    events = listen(hass)
    with patch(READ, new=AsyncMock(return_value=PrinterStatus(BASE))) as read:
        entry = await setup(hass, options={"offline_alert_minutes": 1})
        await update(hass, entry, read, status=last)
        await go_offline(hass, entry, read, freezer, minutes=5)
        assert "offline" not in events
        assert hass.states.get("binary_sensor.creator_5_status_connection").state == "off"
        assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize("last", ["printing", "heating"])
async def test_connection_lost_during_job_alerts_once(hass, freezer, last):
    events = listen(hass)
    with patch(READ, new=AsyncMock(return_value=PrinterStatus(BASE))) as read:
        entry = await setup(hass, options={"offline_alert_minutes": 1})
        await update(hass, entry, read, status=last, printFileName="a.3mf", printDuration=5)
        await go_offline(hass, entry, read, freezer)
        await go_offline(hass, entry, read, freezer)
        assert events == ["offline"]
        assert await hass.config_entries.async_unload(entry.entry_id)


# 2. Printer switched off when Home Assistant starts


async def test_successful_setup_records_model_without_reloading(hass):
    with patch(READ, new=AsyncMock(return_value=PrinterStatus(BASE))) as read:
        entry = await setup(hass)
        assert entry.data["model"] == "Creator 5 Pro"
        assert read.await_count == 1  # no reload from the data update
        assert await hass.config_entries.async_unload(entry.entry_id)


async def test_known_printer_off_at_startup_loads_unavailable_and_recovers(
    hass, hass_storage, freezer
):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**DATA, "model": "Creator 5 Pro"},
        unique_id=DATA["serial_number"],
        minor_version=2,
    )
    hass_storage[f"creator5.{entry.entry_id}.history"] = {
        "version": 1,
        "key": f"creator5.{entry.entry_id}.history",
        "data": {
            "last_job": {
                "filename": "saved.3mf",
                "started_at": "2026-11-01T10:00:00+00:00",
                "finished_at": "2026-11-01T11:00:00+00:00",
                "duration_seconds": 3600,
                "incomplete": False,
                "outcome": "completed",
            }
        },
    }
    entry.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, DATA["serial_number"])},
        model="Creator 5 Pro",
        sw_version="2.0.0",
    )
    with patch(READ, new=AsyncMock(side_effect=PrinterError("Off"))) as read:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED
        assert hass.states.get("sensor.creator_5_last_print").state == "completed"
        assert hass.states.get("binary_sensor.creator_5_status_connection").state == "off"
        assert hass.states.get("sensor.creator_5_bed_temperature").state == "unavailable"
        # Pro-only entities are still created from the saved model.
        assert hass.states.get("sensor.creator_5_chamber_temperature") is not None
        # Unknown live values do not wipe the device's last reported details.
        device = dr.async_get(hass).async_get(device.id)
        assert (device.model, device.sw_version) == ("Creator 5 Pro", "2.0.0")
        # Polling continues and the printer is picked up when it is switched on.
        read.side_effect = None
        read.return_value = PrinterStatus(BASE)
        freezer.tick(timedelta(seconds=11))
        async_fire_time_changed(hass, datetime.now(UTC))
        await hass.async_block_till_done()
        assert hass.states.get("sensor.creator_5_bed_temperature").state == "25.0"
        assert hass.states.get("binary_sensor.creator_5_status_connection").state == "on"
        assert await hass.config_entries.async_unload(entry.entry_id)


async def test_unknown_model_off_at_startup_still_retries(hass):
    with patch(READ, new=AsyncMock(side_effect=PrinterError("Off"))):
        entry = await setup(hass, data={**DATA, "model": "Something else"})
    assert entry.state is ConfigEntryState.SETUP_RETRY


# 3. Address changes


async def test_readding_moved_printer_updates_address_without_status_read(hass):
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DATA["serial_number"], data=DATA)
    entry.add_to_hass(hass)
    with (
        patch(LOOKUP, new=AsyncMock(return_value=PrinterIdentity(DATA["serial_number"], 41))),
        patch(FLOW_READ, new=AsyncMock()) as read,
        patch("custom_components.creator5.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "user"},
            data={"host": "10.0.0.77", "check_code": "synthetic-code"},
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data["host"] == "10.0.0.77"
    assert entry.data["check_code"] == DATA["check_code"]
    read.assert_not_awaited()


async def test_reconfigure_updates_same_printer(hass):
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DATA["serial_number"], data=DATA)
    entry.add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)
    assert result["step_id"] == "reconfigure"
    with (
        patch(LOOKUP, new=AsyncMock(return_value=PrinterIdentity(DATA["serial_number"], 41))),
        patch(FLOW_READ, new=AsyncMock(return_value=PrinterStatus(BASE))),
        patch("custom_components.creator5.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "10.0.0.77", "check_code": "new-code"}
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {
        **DATA,
        "host": "10.0.0.77",
        "check_code": "new-code",
        "model": "Creator 5 Pro",
    }


async def test_reconfigure_rejects_a_different_printer(hass):
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DATA["serial_number"], data=DATA)
    entry.add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)
    with (
        patch(LOOKUP, new=AsyncMock(return_value=PrinterIdentity("OTHER-SN", 41))),
        patch(FLOW_READ, new=AsyncMock()) as read,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "10.0.0.77", "check_code": "synthetic-code"}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_printer"
    assert entry.data == DATA
    read.assert_not_awaited()


@pytest.mark.parametrize(
    "error,expected",
    [(PrinterError("Offline"), "cannot_connect"), (None, "model_mismatch")],
)
async def test_reconfigure_errors_keep_existing_data(hass, error, expected):
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DATA["serial_number"], data=DATA)
    entry.add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)
    read = AsyncMock(side_effect=error, return_value=PrinterStatus({**BASE, "model": "Creator 5"}))
    with (
        patch(LOOKUP, new=AsyncMock(return_value=PrinterIdentity(DATA["serial_number"], 41))),
        patch(FLOW_READ, new=read),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "10.0.0.77", "check_code": "synthetic-code"}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}
    assert entry.data == DATA


async def test_camera_url_for_previous_address_does_not_block_setup(hass):
    with patch(READ, new=AsyncMock(return_value=PrinterStatus(BASE))):
        entry = await setup(
            hass,
            data={**DATA, "host": "10.0.0.77"},
            options={"camera_stream_url": "http://10.0.0.42:8080/?action=stream"},
        )
        assert entry.state is ConfigEntryState.LOADED
        assert entry.runtime_data.options["camera_stream_url"] == ""
        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["type"] is FlowResultType.FORM
        assert await hass.config_entries.async_unload(entry.entry_id)


# 4. Error state without a code


async def test_error_state_with_empty_code_is_a_problem(hass):
    with patch(READ, new=AsyncMock(return_value=PrinterStatus(BASE))) as read:
        entry = await setup(hass)
        assert hass.states.get("binary_sensor.creator_5_printer_error").state == "off"
        await update(hass, entry, read, status="error", errorCode="")
        assert hass.states.get("binary_sensor.creator_5_printer_error").state == "on"
        await update(hass, entry, read, status="ready", errorCode="")
        assert hass.states.get("binary_sensor.creator_5_printer_error").state == "off"
        assert await hass.config_entries.async_unload(entry.entry_id)


# 5. Failed prints


async def start_job(hass, entry, read):
    await update(hass, entry, read, status="printing", printFileName="a.3mf", printDuration=0)
    await update(hass, entry, read, status="printing", printFileName="a.3mf", printDuration=300)


@pytest.mark.parametrize(
    "steps",
    [
        # Error state with no code, then the printer is reset to ready.
        [{"status": "error"}, {"status": "ready"}],
        # Error code, then the user cancels the broken job.
        [
            {"status": "paused", "printFileName": "a.3mf", "errorCode": "E0163"},
            {"status": "cancel"},
        ],
    ],
)
async def test_error_then_unfinished_end_is_failed(hass, steps):
    with patch(READ, new=AsyncMock(return_value=PrinterStatus(BASE))) as read:
        entry = await setup(hass)
        await start_job(hass, entry, read)
        for fields in steps:
            await update(hass, entry, read, **fields)
        state = hass.states.get("sensor.creator_5_last_print")
        assert state.state == "failed"
        assert state.attributes["error_seen"] is True
        assert await hass.config_entries.async_unload(entry.entry_id)


async def test_recovered_error_still_completes_and_failure_survives_reload(hass):
    with patch(READ, new=AsyncMock(return_value=PrinterStatus(BASE))) as read:
        entry = await setup(hass)
        await start_job(hass, entry, read)
        await update(hass, entry, read, status="paused", printFileName="a.3mf", errorCode="E0162")
        await update(hass, entry, read, status="printing", printFileName="a.3mf", printDuration=400)
        await update(hass, entry, read, status="completed")
        state = hass.states.get("sensor.creator_5_last_print")
        assert state.state == "completed"
        assert state.attributes["error_code"] == "E0162"

        await start_job(hass, entry, read)
        await update(hass, entry, read, status="error", errorCode="E0077")
        await update(hass, entry, read, status="ready", errorCode="")
        assert hass.states.get("sensor.creator_5_last_print").state == "failed"
        assert await hass.config_entries.async_unload(entry.entry_id)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        state = hass.states.get("sensor.creator_5_last_print")
        assert state.state == "failed"
        assert state.attributes["error_code"] == "E0077"
        assert await hass.config_entries.async_unload(entry.entry_id)


async def test_plain_return_to_ready_is_still_unconfirmed(hass):
    with patch(READ, new=AsyncMock(return_value=PrinterStatus(BASE))) as read:
        entry = await setup(hass)
        await start_job(hass, entry, read)
        await update(hass, entry, read, status="ready")
        assert hass.states.get("sensor.creator_5_last_print").state == "unconfirmed"
        assert await hass.config_entries.async_unload(entry.entry_id)
