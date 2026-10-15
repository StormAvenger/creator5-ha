"""Fresh setup, exact color pixels and no extra requests for slot visuals."""

from io import BytesIO
from unittest.mock import AsyncMock, patch

from homeassistant.components.image import async_get_image
from homeassistant.helpers import entity_registry as er
from PIL import Image
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.creator5.const import DOMAIN
from custom_components.creator5.creator5py import PrinterStatus

DATA = {"host": "10.0.0.42", "serial_number": "SYNTHETIC-SN", "check_code": "synthetic-code"}


def detail(color):
    return PrinterStatus(
        {
            "status": "ready",
            "matlStationInfo": {
                "slotInfos": [
                    {
                        "slotId": 1,
                        "materialName": "PETG",
                        "materialColor": color,
                        "hasFilament": True,
                    }
                ]
            },
        }
    )


async def test_fresh_install_swatches_follow_color_only_and_cleanup(hass):
    entry = MockConfigEntry(domain=DOMAIN, data=DATA, minor_version=2)
    entry.add_to_hass(hass)
    with patch(
        "custom_components.creator5.Creator5Client.get_status",
        new=AsyncMock(return_value=detail("#1B1B1B")),
    ) as read:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        entity_id = "image.creator_5_slot_1_color_swatch"
        first = hass.states.get(entity_id).state
        rendered = await async_get_image(hass, entity_id)
        assert rendered.content_type == "image/png"
        image = Image.open(BytesIO(rendered.content))
        assert image.size == (160, 80)
        assert image.getpixel((80, 40)) == (27, 27, 27)
        assert read.await_count == 1
        assert hass.states.get("image.creator_5_slot_2_color_swatch").state == "unavailable"
        assert hass.states.get("sensor.creator_5_last_successful_status_update") is None
        registry = er.async_get(hass)
        timestamp_id = registry.async_get_entity_id(
            "sensor", DOMAIN, "SYNTHETIC-SN_last_successful_update"
        )
        assert registry.async_get(timestamp_id).disabled_by == er.RegistryEntryDisabler.INTEGRATION
        color = registry.async_get("sensor.creator_5_slot_1_color")
        assert color.entity_category.value == "diagnostic"
        await entry.runtime_data.async_refresh()
        await hass.async_block_till_done()
        assert hass.states.get(entity_id).state == first  # no every-poll image refresh
        read.return_value = detail("#BEBEBE")
        await entry.runtime_data.async_refresh()
        await hass.async_block_till_done()
        changed = await async_get_image(hass, entity_id)
        assert Image.open(BytesIO(changed.content)).getpixel((80, 40)) == (190, 190, 190)
        read.return_value = detail("not a color")
        await entry.runtime_data.async_refresh()
        await hass.async_block_till_done()
        assert hass.states.get(entity_id).state == "unavailable"
        coordinator = entry.runtime_data
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        assert not list(coordinator.async_contexts())


async def test_grouped_card_renders_the_configured_tool_not_an_assumed_slot(hass):
    from pathlib import Path

    import yaml
    from homeassistant.helpers.template import Template

    card = yaml.safe_load(Path("dashboards/material-slots.yaml").read_text())
    assert card["columns"] == 2
    assert len(card["cards"]) == 4
    first_slot = card["cards"][0]["cards"]
    assert first_slot[0]["entity"] == "image.creator_5_slot_1_color_swatch"
    hass.states.async_set("sensor.creator_5_slot_1_material", "PETG")
    hass.states.async_set("binary_sensor.creator_5_slot_1_filament_present", "on")
    hass.states.async_set(
        "sensor.creator_5_tool_3_material_configured_mapping",
        "PETG",
        {"configured_slot": 1, "user_note": "High-flow material"},
    )
    hass.states.async_set("sensor.creator_5_tool_3_nozzle_diameter", "0.4")
    rendered = Template(first_slot[1]["content"], hass).async_render()
    assert "PETG" in rendered
    assert "Filament loaded" in rendered
    assert "Tool 3 · 0.4 mm" in rendered
    assert "High-flow material" in rendered
    assert "Tool 1 ·" not in rendered
