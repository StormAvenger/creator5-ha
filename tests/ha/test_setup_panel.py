"""Admin boundaries, dynamic dashboard mapping and native HA setup APIs."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.exceptions import Unauthorized
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_socket import socket_allow_hosts

from custom_components.creator5.const import DOMAIN
from custom_components.creator5.creator5py import PrinterStatus
from custom_components.creator5.setup_panel import (
    alert_config,
    dashboard_config,
    notification_targets,
    ws_info,
)

DATA = {"host": "10.0.0.42", "serial_number": "SYNTHETIC-SN", "check_code": "synthetic-code"}
BASE = {"status": "ready", "model": "Creator 5 Pro", "errorCode": ""}


@pytest.fixture(autouse=True)
def synthetic_printer_io():
    with (
        patch(
            "custom_components.creator5.Creator5Client.get_status",
            new=AsyncMock(return_value=PrinterStatus(BASE)),
        ),
        patch(
            "custom_components.creator5.Creator5Client._request",
            new=AsyncMock(side_effect=AssertionError("Test attempted printer I/O")),
        ),
    ):
        yield


async def setup(hass):
    entry = MockConfigEntry(domain=DOMAIN, data=DATA, minor_version=2, title="Demo printer")
    entry.add_to_hass(hass)
    with patch(
        "custom_components.creator5.Creator5Client.get_status",
        new=AsyncMock(return_value=PrinterStatus(BASE)),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


def all_entities(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "entity" and isinstance(item, str):
                yield item
            elif key == "entities" and isinstance(item, list):
                for row in item:
                    if isinstance(row, str):
                        yield row
                    else:
                        yield from all_entities(row)
            else:
                yield from all_entities(item)
    elif isinstance(value, list):
        for item in value:
            yield from all_entities(item)


async def test_dashboard_uses_registry_ids_disabled_entities_and_no_private_values(hass):
    entry = await setup(hass)
    registry = er.async_get(hass)
    item = registry.async_get("sensor.creator_5_print_progress")
    registry.async_update_entity(item.entity_id, new_entity_id="sensor.my_custom_printer_progress")
    color = registry.async_get("image.creator_5_slot_4_color_swatch")
    registry.async_update_entity(color.entity_id, disabled_by=er.RegistryEntryDisabler.USER)
    config = dashboard_config(hass, entry)
    ids = list(all_entities(config))
    assert "sensor.my_custom_printer_progress" in ids
    assert "sensor.creator_5_print_progress" not in ids
    assert color.entity_id not in ids
    assert "image.creator_5_slot_1_color_swatch" in ids
    assert "number.creator_5_bed_temperature_target" not in ids
    assert all(DATA[key] not in str(config) for key in DATA)
    assert all(registry.async_get(entity_id).config_entry_id == entry.entry_id for entity_id in ids)
    assert len(config["views"]) == 2
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_no_non_admin_can_read_setup_or_generate_configuration(hass):
    await setup(hass)
    with pytest.raises(Unauthorized):
        ws_info(hass, SimpleNamespace(user=SimpleNamespace(is_admin=False)), {"id": 1})


async def test_authenticated_websocket_helpers_validate_inputs_and_preserve_privacy(
    hass, hass_ws_client
):
    socket_allow_hosts(["127.0.0.1", "::1"], allow_unix_socket=True)
    entry = await setup(hass)
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "creator5/setup_info"})
    reply = await client.receive_json()
    assert reply["success"]
    assert reply["result"]["printers"][0]["entry_id"] == entry.entry_id
    assert DATA["check_code"] not in str(reply)
    assert DATA["serial_number"] not in str(reply)
    assert DATA["host"] not in str(reply)
    await client.send_json(
        {"id": 2, "type": "creator5/dashboard_config", "entry_id": "not-a-printer"}
    )
    assert not (await client.receive_json())["success"]
    await client.send_json(
        {
            "id": 3,
            "type": "creator5/alert_config",
            "entry_id": entry.entry_id,
            "target": "light.turn_on",
            "kinds": ["completed"],
        }
    )
    assert not (await client.receive_json())["success"]
    await client.send_json(
        {
            "id": 4,
            "type": "creator5/alert_config",
            "entry_id": entry.entry_id,
            "target": "persistent_notification.create",
            "kinds": ["completed", "error"],
        }
    )
    reply = await client.receive_json()
    assert reply["success"]
    config = reply["result"]["config"]
    assert config["actions"][0]["action"] == "persistent_notification.create"
    assert config["triggers"][0]["event_data"] == {"entry_id": entry.entry_id}
    assert reply["result"]["automation_id"].startswith("creator5_alerts_")
    hass.states.async_set(
        "automation.existing_printer_alerts", "off", {"id": reply["result"]["automation_id"]}
    )
    await client.send_json(
        {
            "id": 5,
            "type": "creator5/alert_config",
            "entry_id": entry.entry_id,
            "target": "persistent_notification.create",
            "kinds": ["completed"],
        }
    )
    reply = await client.receive_json()
    assert not reply["success"] and reply["error"]["code"] == "already_exists"
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_generated_alert_automation_only_delivers_selected_new_events(hass):
    entry = await setup(hass)
    notifications = []

    async def record(call):
        notifications.append(call.data)

    hass.services.async_register("notify", "mobile_app_synthetic_phone", record)
    config = alert_config(entry, "notify.mobile_app_synthetic_phone", ["completed", "error"])
    config["id"] = "synthetic-alerts"
    assert await async_setup_component(hass, "automation", {"automation": [config]})
    await hass.async_block_till_done()
    assert not notifications
    hass.bus.async_fire(
        "creator5_event", {"entry_id": "another-printer", "kind": "completed", "message": "ignore"}
    )
    hass.bus.async_fire(
        "creator5_event", {"entry_id": entry.entry_id, "kind": "bed_cooled", "message": "ignore"}
    )
    await hass.async_block_till_done()
    assert not notifications
    hass.bus.async_fire(
        "creator5_event",
        {"entry_id": entry.entry_id, "kind": "completed", "message": "Print completed."},
    )
    await hass.async_block_till_done()
    assert notifications == [{"title": "Creator 5", "message": "Print completed."}]
    assert "notify.mobile_app_synthetic_phone" in notification_targets(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_native_dashboard_create_and_save_preserves_existing(hass, hass_ws_client):
    socket_allow_hosts(["127.0.0.1", "::1"], allow_unix_socket=True)
    await setup(hass)
    assert await async_setup_component(hass, "frontend", {})
    assert await async_setup_component(hass, "lovelace", {})
    await hass.async_block_till_done()
    panel = hass.data["frontend_panels"]["creator5-setup"]
    assert panel.require_admin is True
    client = await hass_ws_client(hass)
    create = {
        "type": "lovelace/dashboards/create",
        "url_path": "demo-printer",
        "title": "Demo printer",
        "show_in_sidebar": True,
        "require_admin": False,
        "icon": "mdi:printer-3d",
    }
    await client.send_json({"id": 1, **create})
    reply = await client.receive_json()
    assert reply["success"], reply
    config = {"views": [{"title": "Demo", "cards": []}]}
    await client.send_json(
        {"id": 2, "type": "lovelace/config/save", "url_path": "demo-printer", "config": config}
    )
    assert (await client.receive_json())["success"]
    await client.send_json({"id": 3, **create})
    assert not (await client.receive_json())["success"]
    await client.send_json({"id": 4, "type": "lovelace/config", "url_path": "demo-printer"})
    reply = await client.receive_json()
    assert reply["success"] and reply["result"] == config


async def test_native_automation_editor_api_creates_without_changing_existing(hass, hass_client):
    from pathlib import Path

    from homeassistant.util.yaml import load_yaml

    socket_allow_hosts(["127.0.0.1", "::1"], allow_unix_socket=True)
    entry = await setup(hass)
    assert await async_setup_component(hass, "config", {})

    async def record(_call):
        raise AssertionError("Setup must not send notifications")

    hass.services.async_register("notify", "mobile_app_synthetic_phone", record)
    assert await async_setup_component(hass, "automation", {})
    client = await hass_client()
    existing = {
        "alias": "Existing automation",
        "triggers": [{"trigger": "event", "event_type": "synthetic_never"}],
        "actions": [
            {"action": "notify.mobile_app_synthetic_phone", "data": {"message": "Existing"}}
        ],
    }
    response = await client.post("/api/config/automation/config/keep-existing", json=existing)
    assert response.status == 200, await response.text()
    before = load_yaml(hass.config.path("automations.yaml"))
    config = alert_config(entry, "notify.mobile_app_synthetic_phone", ["completed"])
    response = await client.post(
        "/api/config/automation/config/creator5-alerts-synthetic", json=config
    )
    assert response.status == 200, await response.text()
    after = load_yaml(hass.config.path("automations.yaml"))
    assert next(item for item in after if item["id"] == "keep-existing") == before[0]
    assert len(after) == 2
    assert Path(hass.config.path("automations.yaml")).is_file()
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_setup_sidebar_never_replaces_an_existing_panel(hass):
    from homeassistant.components import frontend

    assert await async_setup_component(hass, "frontend", {})
    frontend.async_register_built_in_panel(
        hass,
        component_name="map",
        frontend_url_path="creator5-setup",
        sidebar_title="Existing panel",
    )
    original = hass.data["frontend_panels"]["creator5-setup"]
    entry = await setup(hass)
    assert hass.data["frontend_panels"]["creator5-setup"] is original
    assert hass.data["frontend_panels"]["creator5-setup-2"].require_admin is True
    assert await hass.config_entries.async_unload(entry.entry_id)
