"""Real HA entities, imperial defaults, unit migration and LED-only services."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.const import UnitOfTemperature
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.creator5 import async_migrate_entry
from custom_components.creator5.const import DOMAIN
from custom_components.creator5.creator5py import PrinterError, PrinterStatus

DATA = {"host": "10.0.0.42", "serial_number": "SYNTHETIC-SN", "check_code": "synthetic-code"}
DETAIL = {
    "status": "printing",
    "model": "Creator 5 Pro",
    "doorStatus": "close",
    "lightStatus": "open",
    "platTemp": 60,
    "chamberTemp": 35,
    "platTargetTemp": 65,
    "chamberTargetTemp": 0,
    "nozzleTemps": [210, 30, 31, 32],
    "nozzleTargetTemps": [215, 0, 0, 0],
    "printDuration": 123,
    "printLayer": 4,
    "targetPrintLayer": 200,
    "chamberFanSpeed": 0,
    "coolingFanSpeed": 79,
    "matlStationInfo": {
        "slotInfos": [
            {"slotId": 2, "materialName": "PETG", "materialColor": "#112233", "hasFilament": True},
            {"slotId": 1, "materialName": "PLA", "materialColor": "#FFFFFF", "hasFilament": False},
        ]
    },
}


async def test_shared_entities_celsius_on_imperial_host_and_light_only_services(hass):
    hass.config.units = US_CUSTOMARY_SYSTEM
    entry = MockConfigEntry(
        domain=DOMAIN, data=DATA, unique_id=DATA["serial_number"], minor_version=2
    )
    entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.creator5.Creator5Client.get_status",
            new=AsyncMock(return_value=PrinterStatus(DETAIL)),
        ) as read,
        patch(
            "custom_components.creator5.Creator5Client.set_light",
            new=AsyncMock(return_value=PrinterStatus({**DETAIL, "lightStatus": "close"})),
        ) as write,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert read.await_count == 1
        assert len(hass.states.async_all()) == 30
        states = {s.entity_id: s for s in hass.states.async_all()}
        temps = [s for s in states.values() if s.attributes.get("device_class") == "temperature"]
        assert len(temps) == 12
        assert all(s.attributes["unit_of_measurement"] == "°C" for s in temps)
        assert hass.config.units.temperature_unit == UnitOfTemperature.FAHRENHEIT
        assert states["sensor.creator_5_bed_temperature"].state == "60.0"
        assert states["sensor.creator_5_chamber_target_temperature"].state == "0.0"
        assert states["sensor.creator_5_slot_2_material"].state == "PETG"
        assert states["sensor.creator_5_slot_2_material"].attributes["color"] == "#112233"
        assert states["binary_sensor.creator_5_slot_1_filament_present"].state == "off"
        assert states["binary_sensor.creator_5_slot_2_filament_present"].state == "on"
        assert states["binary_sensor.creator_5_slot_3_filament_present"].state == "unknown"
        assert states["binary_sensor.creator_5_door_or_lid"].state == "off"
        assert states["light.creator_5_chamber_light"].state == "on"
        assert states["sensor.creator_5_reported_chamber_fan"].state == "0.0"
        assert states["sensor.creator_5_reported_cooling_fan"].state == "79.0"
        assert not hass.services.has_service(DOMAIN, "command")
        assert not hass.states.async_all("fan")
        write.assert_not_awaited()  # setup/polling never changes the light
        await hass.services.async_call(
            "light", "turn_off", {"entity_id": "light.creator_5_chamber_light"}, blocking=True
        )
        write.assert_awaited_once_with(False)
        assert read.await_count == 1  # verified readback is shared, no redundant poll
        assert hass.states.get("light.creator_5_chamber_light").state == "off"
        assert hass.states.get("sensor.creator_5_state").state == "printing"
        write.side_effect = PrinterError("Printer did not confirm the requested light state")
        with pytest.raises(HomeAssistantError, match="did not confirm"):
            await hass.services.async_call(
                "light", "turn_on", {"entity_id": "light.creator_5_chamber_light"}, blocking=True
            )
        assert hass.states.get("light.creator_5_chamber_light").state == "off"
        read.return_value = PrinterStatus({**DETAIL, "doorStatus": "open", "lightStatus": "close"})
        await entry.runtime_data.async_refresh()
        await hass.async_block_till_done()
        assert hass.states.get("binary_sensor.creator_5_door_or_lid").state == "on"
        read.return_value = PrinterStatus(
            {**DETAIL, "status": "completed", "estimatedTime": 2021, "printProgress": 0}
        )
        await entry.runtime_data.async_refresh()
        await hass.async_block_till_done()
        assert hass.states.get("sensor.creator_5_remaining_time").state == "unknown"
        assert hass.states.get("sensor.creator_5_print_progress").state == "0.0"
        assert hass.states.get("sensor.creator_5_state").state == "completed"
        coordinator = entry.runtime_data
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        assert not list(coordinator.async_contexts())


async def test_door_is_not_exposed_for_base_creator5(hass):
    entry = MockConfigEntry(domain=DOMAIN, data=DATA, minor_version=2)
    entry.add_to_hass(hass)
    with patch(
        "custom_components.creator5.Creator5Client.get_status",
        new=AsyncMock(return_value=PrinterStatus({**DETAIL, "model": "Creator 5"})),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert hass.states.get("binary_sensor.creator_5_door_or_lid") is None
        assert await hass.config_entries.async_unload(entry.entry_id)


async def test_old_automatic_units_migrate_without_touching_other_devices_or_overrides(hass):
    hass.config.units = US_CUSTOMARY_SYSTEM
    registry = er.async_get(hass)
    entry = MockConfigEntry(domain=DOMAIN, data=DATA, minor_version=1)
    entry.add_to_hass(hass)
    automatic = registry.async_get_or_create(
        "sensor", DOMAIN, f"{DATA['serial_number']}_platTemp", config_entry=entry
    )
    override = registry.async_get_or_create(
        "sensor", DOMAIN, f"{DATA['serial_number']}_chamberTemp", config_entry=entry
    )
    other = registry.async_get_or_create("sensor", "unrelated", "room-temperature")
    registry.async_update_entity_options(
        automatic.entity_id, "sensor.private", {"suggested_unit_of_measurement": "°F"}
    )
    registry.async_update_entity_options(
        override.entity_id, "sensor", {"unit_of_measurement": "°F"}
    )
    registry.async_update_entity_options(other.entity_id, "sensor", {"unit_of_measurement": "°F"})
    assert await async_migrate_entry(hass, entry)
    assert entry.minor_version == 2
    assert registry.async_get(automatic.entity_id).options["sensor"]["unit_of_measurement"] == "°C"
    assert registry.async_get(override.entity_id).options["sensor"]["unit_of_measurement"] == "°F"
    assert registry.async_get(other.entity_id).options["sensor"]["unit_of_measurement"] == "°F"
    assert hass.config.units.temperature_unit == UnitOfTemperature.FAHRENHEIT
    registry.async_update_entity_options(
        automatic.entity_id, "sensor", {"unit_of_measurement": "°F"}
    )
    assert await async_migrate_entry(hass, entry)
    assert registry.async_get(automatic.entity_id).options["sensor"]["unit_of_measurement"] == "°F"
