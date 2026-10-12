"""Sensor values, unavailable/recovery, first refresh and unload."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntryState
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.creator5.const import DOMAIN
from custom_components.creator5.creator5py import AuthenticationError, PrinterError, PrinterStatus

DATA = {"host": "10.0.0.42", "serial_number": "SYNTHETIC-SN", "check_code": "synthetic-code"}


async def test_sensor_values_connection_loss_recovery_and_unload(hass, freezer):
    entry = MockConfigEntry(domain=DOMAIN, data=DATA, unique_id=DATA["serial_number"])
    entry.add_to_hass(hass)
    status = PrinterStatus(
        {
            "status": "printing",
            "printProgress": 0.5,
            "platTemp": 60,
            "chamberTemp": 35,
            "estimatedTime": 120,
            "nozzleTemps": [215, 31, 32, 33],
            "nozzleTargetTemps": [220, 0, 0, 0],
        }
    )
    with patch(
        "custom_components.creator5.Creator5Client.get_status", new=AsyncMock(return_value=status)
    ) as read:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert read.await_count == 1  # all thirteen sensors share one request
        states = {state.name: state for state in hass.states.async_all("sensor")}
        assert len(states) == 13
        by_id = {s.entity_id: s for s in states.values()}
        for suffix, value in {
            "tool_1_temperature": "215.0",
            "tool_2_temperature": "31.0",
            "tool_3_temperature": "32.0",
            "tool_4_temperature": "33.0",
            "tool_1_target_temperature": "220.0",
            "tool_2_target_temperature": "0.0",
            "tool_3_target_temperature": "0.0",
            "tool_4_target_temperature": "0.0",
        }.items():
            state = next(s for key, s in by_id.items() if key.endswith(suffix))
            assert state.state == value
            assert state.attributes["unit_of_measurement"] == "°C"
        progress = next(
            s for s in states.values() if s.attributes.get("unit_of_measurement") == "%"
        )
        assert progress.state == "50.0"
        assert all("synthetic-code" not in str(s.attributes) for s in states.values())

        freezer.tick(timedelta(seconds=31))
        async_fire_time_changed(hass, datetime.now(UTC))
        await hass.async_block_till_done()
        assert read.await_count == 2

        read.side_effect = PrinterError("Disconnected")
        await entry.runtime_data.async_refresh()
        await hass.async_block_till_done()
        assert all(s.state == "unavailable" for s in hass.states.async_all("sensor"))

        read.side_effect = None
        read.return_value = PrinterStatus({"status": "ready"})
        await entry.runtime_data.async_refresh()
        await hass.async_block_till_done()
        values = [s.state for s in hass.states.async_all("sensor")]
        assert values.count("unknown") == 12
        assert "ready" in values
        coordinator = entry.runtime_data
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.NOT_LOADED
        assert not list(coordinator.async_contexts())
        # HA keeps unavailable registry placeholders after a normal unload.
        assert all(s.state == "unavailable" for s in hass.states.async_all("sensor"))
        requests_at_unload = read.await_count
        freezer.tick(timedelta(seconds=60))
        async_fire_time_changed(hass, datetime.now(UTC))
        await hass.async_block_till_done()
        assert read.await_count == requests_at_unload


async def test_first_refresh_unreachable_retries_setup(hass):
    entry = MockConfigEntry(domain=DOMAIN, data=DATA)
    entry.add_to_hass(hass)
    with patch(
        "custom_components.creator5.Creator5Client.get_status",
        new=AsyncMock(side_effect=PrinterError("Disconnected")),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert not hass.states.async_all("sensor")


async def test_authentication_failure_requests_reauth(hass):
    entry = MockConfigEntry(domain=DOMAIN, data=DATA)
    entry.add_to_hass(hass)
    with patch(
        "custom_components.creator5.Creator5Client.get_status",
        new=AsyncMock(side_effect=AuthenticationError("Rejected")),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert any(
        f["context"]["source"] == "reauth" for f in hass.config_entries.flow.async_progress()
    )
