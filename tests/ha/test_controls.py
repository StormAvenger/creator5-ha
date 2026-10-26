"""Real HA service handling, opt-in permissions, Activity filtering and Celsius."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.components.logbook.helpers import is_sensor_continuous
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.creator5.const import DOMAIN
from custom_components.creator5.creator5py import PrinterError, PrinterStatus
from custom_components.creator5.settings import CONTROL_GROUPS

DATA = {"host": "10.0.0.42", "serial_number": "SYNTHETIC-SN", "check_code": "synthetic-code"}
DETAIL = {
    "status": "ready",
    "model": "Creator 5 Pro",
    "firmwareVersion": "2.0.0",
    "cumulativeFilament": 123.5,
    "printSpeedAdjust": 100,
    "zAxisCompensation": -0.05,
    "autoShutdown": "close",
    "autoShutdownTime": 30,
    "platTargetTemp": 0,
    "chamberTargetTemp": 0,
    "nozzleTargetTemps": [0, 0, 0, 0],
    "printLayer": 10,
    "targetPrintLayer": 200,
    "printProgress": 0.05,
    "matlStationInfo": {
        "currentSlot": 0,
        "currentLoadSlot": 2,
        "stateAction": 7,
        "stateStep": 12,
        "slotInfos": [{"slotId": 2, "materialName": "PLA", "materialColor": "#FFFFFF"}],
    },
}


async def setup(hass, options=None):
    entry = MockConfigEntry(domain=DOMAIN, data=DATA, minor_version=2, options=options or {})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_readouts_and_quiet_continuous_sensors_preserve_meaningful_state(hass):
    with patch(
        "custom_components.creator5.Creator5Client.get_status",
        new=AsyncMock(return_value=PrinterStatus(DETAIL)),
    ):
        entry = await setup(hass)
        expected = {
            "reported_lifetime_filament": "123.5",
            "print_speed_multiplier": "100.0",
            "z_offset": "-0.05",
            "reported_auto_shutdown_delay": "30.0",
            "reported_material_station_slot": "0",
            "reported_material_loading_slot": "2",
        }
        for suffix, value in expected.items():
            state = hass.states.get(f"sensor.creator_5_{suffix}")
            assert state.state == value
        assert hass.states.get("binary_sensor.creator_5_reported_auto_shutdown").state == "off"
        station = hass.states.get("sensor.creator_5_reported_material_station_slot")
        assert station.attributes["action_code"] == 7
        assert station.attributes["step_code"] == 12
        assert station.attributes["zero_means"] == "no_reported_slot"
        registry = er.async_get(hass)
        for suffix in ("current_layer", "total_layers", "print_progress"):
            entity_id = f"sensor.creator_5_{suffix}"
            assert hass.states.get(entity_id).attributes["state_class"] == "measurement"
            assert is_sensor_continuous(hass, registry, entity_id)
        assert not is_sensor_continuous(hass, registry, "sensor.creator_5_state")
        assert not hass.states.async_all("button")
        assert not hass.states.async_all("number")
        assert not hass.states.async_all("select")
        assert not hass.states.async_all("switch")
        assert await hass.config_entries.async_unload(entry.entry_id)
        # Historical Activity filtering also works from registry capabilities.
        hass.states.async_remove("sensor.creator_5_current_layer")
        assert is_sensor_continuous(hass, registry, "sensor.creator_5_current_layer")


async def test_opt_in_controls_use_real_services_and_shared_verified_snapshots(hass):
    hass.config.units = US_CUSTOMARY_SYSTEM
    with patch(
        "custom_components.creator5.Creator5Client.get_status",
        new=AsyncMock(return_value=PrinterStatus(DETAIL)),
    ) as read:
        entry = await setup(hass, dict.fromkeys(CONTROL_GROUPS, True))
        assert len(hass.states.async_all("button")) == 3
        assert len(hass.states.async_all("number")) == 8
        assert len(hass.states.async_all("select")) == 8
        assert len(hass.states.async_all("switch")) == 1
        for state in hass.states.async_all("number"):
            if "temperature_target" in state.entity_id:
                assert state.attributes["unit_of_measurement"] == "°C"
                assert state.state == "0.0"
        assert hass.config.units.temperature_unit == "°F"
        read.assert_awaited_once()  # setup and options cause no control calls
        with patch.object(
            entry.runtime_data.client,
            "set_temperature",
            new=AsyncMock(
                return_value=PrinterStatus({**DETAIL, "nozzleTargetTemps": [0, 220, 0, 0]})
            ),
        ) as write:
            await hass.services.async_call(
                "number",
                "set_value",
                {"entity_id": "number.creator_5_tool_2_temperature_target", "value": 220},
                blocking=True,
            )
            write.assert_awaited_once_with("tool_2", 220.0)
            assert hass.states.get("sensor.creator_5_tool_2_target_temperature").state == "220.0"
            assert hass.states.get("number.creator_5_tool_2_temperature_target").state == "220.0"
        with patch.object(
            entry.runtime_data.client, "set_slot", new=AsyncMock(return_value=PrinterStatus(DETAIL))
        ) as write:
            await hass.services.async_call(
                "select",
                "select_option",
                {"entity_id": "select.creator_5_slot_2_color_setting", "option": "Blue"},
                blocking=True,
            )
            write.assert_awaited_once_with(2, color="#4CAAF8")
            await hass.services.async_call(
                "select",
                "select_option",
                {"entity_id": "select.creator_5_slot_2_material_setting", "option": "PETG"},
                blocking=True,
            )
            assert write.call_args.args == (2,)
            assert write.call_args.kwargs == {"material": "PETG"}
        with patch.object(
            entry.runtime_data.client,
            "set_auto_shutdown",
            new=AsyncMock(return_value=PrinterStatus({**DETAIL, "autoShutdown": "open"})),
        ) as write:
            await hass.services.async_call(
                "switch", "turn_on", {"entity_id": "switch.creator_5_auto_shutdown"}, blocking=True
            )
            write.assert_awaited_once_with(enabled=True)
            assert hass.states.get("binary_sensor.creator_5_reported_auto_shutdown").state == "on"
        assert await hass.config_entries.async_unload(entry.entry_id)


async def test_completion_button_is_only_explicit_and_print_controls_follow_state(hass):
    with patch(
        "custom_components.creator5.Creator5Client.get_status",
        new=AsyncMock(return_value=PrinterStatus(DETAIL)),
    ):
        entry = await setup(hass, {"job_controls": True})
        client = entry.runtime_data.client
        with patch.object(
            client, "dismiss_completion", new=AsyncMock(return_value=PrinterStatus(DETAIL))
        ) as dismiss:
            assert (
                hass.states.get("button.creator_5_acknowledge_completed_print").state
                == "unavailable"
            )
            entry.runtime_data.async_set_updated_data(
                PrinterStatus({**DETAIL, "status": "completed"})
            )
            await hass.async_block_till_done()
            dismiss.assert_not_awaited()  # completion, polling and entity setup never auto-dismiss
            await hass.services.async_call(
                "button",
                "press",
                {"entity_id": "button.creator_5_acknowledge_completed_print"},
                blocking=True,
            )
            dismiss.assert_awaited_once_with()
            assert hass.states.get("sensor.creator_5_state").state == "ready"
        entry.runtime_data.async_set_updated_data(PrinterStatus({**DETAIL, "status": "printing"}))
        await hass.async_block_till_done()
        with patch.object(
            client,
            "pause",
            new=AsyncMock(return_value=PrinterStatus({**DETAIL, "status": "paused"})),
        ) as pause:
            await hass.services.async_call(
                "button", "press", {"entity_id": "button.creator_5_pause_print"}, blocking=True
            )
            pause.assert_awaited_once_with()
            assert hass.states.get("button.creator_5_pause_print").state == "unavailable"
            assert hass.states.get("button.creator_5_resume_print").state != "unavailable"
        with patch.object(
            client,
            "resume",
            new=AsyncMock(return_value=PrinterStatus({**DETAIL, "status": "printing"})),
        ) as resume:
            await hass.services.async_call(
                "button", "press", {"entity_id": "button.creator_5_resume_print"}, blocking=True
            )
            resume.assert_awaited_once_with()
        assert await hass.config_entries.async_unload(entry.entry_id)


async def test_failed_control_is_not_optimistic_and_permission_cannot_be_bypassed(hass):
    with patch(
        "custom_components.creator5.Creator5Client.get_status",
        new=AsyncMock(return_value=PrinterStatus(DETAIL)),
    ):
        entry = await setup(hass, {"temperature_controls": True})
        with patch.object(
            entry.runtime_data.client,
            "set_temperature",
            new=AsyncMock(side_effect=PrinterError("Printer did not confirm")),
        ) as write:
            with pytest.raises(HomeAssistantError, match="did not confirm"):
                await hass.services.async_call(
                    "number",
                    "set_value",
                    {"entity_id": "number.creator_5_bed_temperature_target", "value": 60},
                    blocking=True,
                )
            assert hass.states.get("number.creator_5_bed_temperature_target").state == "0.0"
            assert write.await_count == 1
        with patch.object(entry.runtime_data.client, "pause", new=AsyncMock()) as pause:
            with pytest.raises(PrinterError, match="Enable this control group"):
                await entry.runtime_data.async_control("job_controls", "pause")
            with pytest.raises(PrinterError, match="Enable this control group"):
                await entry.runtime_data.async_control("temperature_controls", "pause")
            pause.assert_not_awaited()
        assert await hass.config_entries.async_unload(entry.entry_id)


async def test_base_printer_gets_no_chamber_heater_target(hass):
    with patch(
        "custom_components.creator5.Creator5Client.get_status",
        new=AsyncMock(return_value=PrinterStatus({**DETAIL, "model": "Creator 5"})),
    ):
        entry = await setup(hass, {"temperature_controls": True})
        assert len(hass.states.async_all("number")) == 5
        assert hass.states.get("number.creator_5_chamber_temperature_target") is None
        assert await hass.config_entries.async_unload(entry.entry_id)


async def test_failure_diagnostics_only_include_safe_stage_and_enabled_groups(hass):
    from custom_components.creator5.creator5py.client import ControlError
    from custom_components.creator5.diagnostics import async_get_config_entry_diagnostics

    with patch(
        "custom_components.creator5.Creator5Client.get_status",
        new=AsyncMock(return_value=PrinterStatus(DETAIL)),
    ) as read:
        entry = await setup(hass, {"job_controls": True})
        with patch.object(
            entry.runtime_data.client,
            "set_light",
            new=AsyncMock(side_effect=ControlError("request", "Control request failed")),
        ):
            with pytest.raises(HomeAssistantError, match="Control request failed"):
                await hass.services.async_call(
                    "light",
                    "turn_on",
                    {"entity_id": "light.creator_5_chamber_light"},
                    blocking=True,
                )
        report = await async_get_config_entry_diagnostics(hass, entry)
        assert report["last_control_failure_stage"] == "request"
        assert report["control_scope"] == ["chamber_light", "job_controls"]
        assert read.await_count == 1
        assert "synthetic-code" not in str(report)
        with patch.object(
            entry.runtime_data.client,
            "set_light",
            new=AsyncMock(return_value=PrinterStatus({**DETAIL, "lightStatus": "open"})),
        ):
            await hass.services.async_call(
                "light", "turn_on", {"entity_id": "light.creator_5_chamber_light"}, blocking=True
            )
        assert (await async_get_config_entry_diagnostics(hass, entry))[
            "last_control_failure_stage"
        ] is None
        assert await hass.config_entries.async_unload(entry.entry_id)
