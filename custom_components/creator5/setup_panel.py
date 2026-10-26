"""Admin-only setup helpers. Native HA APIs perform the UI-requested mutations."""

from pathlib import Path
from uuid import uuid4

import probatio as vol
from homeassistant.components import websocket_api
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_COMPONENT_LOADED
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er

from .const import CONF_SERIAL, DOMAIN
from .history import MAINTENANCE

ALERTS = {
    "completed": "Print completed",
    "bed_cooled": "Bed cooled after completion",
    "error": "Printer error",
    "prolonged_pause": "Prolonged pause",
    "offline": "Connection lost",
    "maintenance": "Maintenance reminder due",
}


def printer_entry(hass, entry_id):
    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is None or entry.domain != DOMAIN or entry.state is not ConfigEntryState.LOADED:
        return None
    return entry


def entity_ids(hass, entry):
    prefix = entry.data[CONF_SERIAL] + "_"
    return {
        item.unique_id[len(prefix) :]: item.entity_id
        for item in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
        if item.platform == DOMAIN and not item.disabled_by and item.unique_id.startswith(prefix)
    }


def dashboard_config(hass, entry):
    ids = entity_ids(hass, entry)

    def entities(title, keys):
        return {
            "type": "entities",
            "title": title,
            "show_header_toggle": False,
            "entities": [ids[k] for k in keys if k in ids],
        }

    cards = [
        entities(
            "Print",
            [
                "status",
                "printProgress",
                "printLayer",
                "targetPrintLayer",
                "estimatedTime",
                "job_completion",
                "bed_cooled",
            ],
        ),
        entities(
            "Connection and errors", ["connection", "problem", "error_code", "error_explanation"]
        ),
    ]
    if "camera" in ids:
        cards.insert(
            0,
            {
                "type": "picture-entity",
                "entity": ids["camera"],
                "camera_view": "auto",
                "name": "Printer camera",
            },
        )
    if "last_print" in ids:
        cards.append(
            {
                "type": "entities",
                "title": "Last print",
                "entities": [
                    ids["last_print"],
                    *[
                        {
                            "type": "attribute",
                            "entity": ids["last_print"],
                            "attribute": attribute,
                            "name": label,
                        }
                        for attribute, label in (
                            ("filename", "File"),
                            ("duration_seconds", "Reported duration (seconds)"),
                            ("finished_at", "Completion observed at"),
                            ("incomplete", "Observation incomplete"),
                        )
                    ],
                ],
            }
        )
    cards.append(
        entities(
            "Temperatures · Celsius",
            ["platTemp", "platTargetTemp", "chamberTemp", "chamberTargetTemp"]
            + [
                f"tool_{tool}_{kind}"
                for tool in range(1, 5)
                for kind in ("temperature", "target_temperature")
            ],
        )
    )
    controls = [
        k
        for k, entity_id in ids.items()
        if entity_id.split(".")[0] in ("light", "number", "select", "switch", "button")
        and not k.startswith("record_")
    ]
    if controls:
        cards.append(entities("Controls", controls))
    cards.append(
        entities(
            "Maintenance",
            [f"{key}_{kind}" for key in MAINTENANCE for kind in ("remaining", "due")]
            + [f"record_{key}" for key in MAINTENANCE],
        )
    )
    cards.append(
        entities(
            "Printer information",
            [
                "model",
                "firmware_version",
                "job_lifetime",
                "job_storage",
                "telemetry_filament",
                "telemetry_speed",
                "telemetry_offset",
                "auto_shutdown_status",
                "telemetry_shutdown_delay",
                "telemetry_station_slot",
                "telemetry_loading_slot",
            ],
        )
    )
    slots = []
    for slot in range(1, 5):
        group = []
        swatch = ids.get(f"slot_{slot}_swatch")
        if swatch:
            group.append(
                {
                    "type": "picture-entity",
                    "entity": swatch,
                    "name": f"Slot {slot}",
                    "show_state": False,
                    "aspect_ratio": "4:1",
                    "tap_action": {"action": "none"},
                }
            )
        group.append(
            entities(
                f"Slot {slot}",
                [
                    f"slot_{slot}_material",
                    f"slot_{slot}_filament",
                    f"slot_{slot}_material_control",
                    f"slot_{slot}_color_control",
                ],
            )
        )
        slots.append({"type": "vertical-stack", "cards": group})
    tools = entities(
        "Tool assignments",
        [f"tool_{tool}_{kind}" for tool in range(1, 5) for kind in ("diameter", "material")],
    )
    return {
        "views": [
            {"title": "Printer", "path": "printer", "cards": cards},
            {
                "title": "Materials",
                "path": "materials",
                "cards": [
                    {"type": "grid", "columns": 2, "square": False, "cards": slots},
                    tools,
                ],
            },
        ]
    }


def notification_targets(hass):
    targets = {"persistent_notification.create": "Home Assistant notifications"}
    for service in hass.services.async_services().get("notify", {}):
        if service.startswith("mobile_app_"):
            targets[f"notify.{service}"] = service.removeprefix("mobile_app_").replace("_", " ")
    return targets


def alert_config(entry, target, kinds):
    return {
        "alias": f"{entry.title} · Printer alerts",
        "description": "Created by Creator 5 setup. Edit or disable in Automations.",
        "triggers": [
            {
                "trigger": "event",
                "event_type": "creator5_event",
                "event_data": {"entry_id": entry.entry_id},
            }
        ],
        "conditions": [
            {
                "condition": "template",
                "value_template": "{{ trigger.event.data.kind in " + repr(kinds) + " }}",
            }
        ],
        "actions": [
            {
                "action": target,
                "data": {"title": "Creator 5", "message": "{{ trigger.event.data.message }}"},
            }
        ],
        "mode": "queued",
        "max": 10,
    }


@websocket_api.require_admin
@websocket_api.websocket_command({"type": "creator5/setup_info"})
@callback
def ws_info(hass, connection, msg):
    connection.send_result(
        msg["id"],
        {
            "printers": [
                {
                    "entry_id": entry.entry_id,
                    "name": entry.title,
                    "dashboard_path": "creator5-" + entry.entry_id.lower(),
                }
                for entry in hass.config_entries.async_entries(DOMAIN)
                if entry.state is ConfigEntryState.LOADED
            ],
            "targets": notification_targets(hass),
            "alerts": ALERTS,
            "dashboards_available": "lovelace" in hass.config.components,
        },
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {"type": "creator5/dashboard_config", vol.Required("entry_id"): str}
)
@callback
def ws_dashboard(hass, connection, msg):
    entry = printer_entry(hass, msg["entry_id"])
    if entry is None:
        connection.send_error(msg["id"], "not_loaded", "Select a loaded Creator 5 printer")
        return
    connection.send_result(msg["id"], dashboard_config(hass, entry))


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        "type": "creator5/alert_config",
        vol.Required("entry_id"): str,
        vol.Required("target"): str,
        vol.Required("kinds"): [vol.In(ALERTS)],
    }
)
@callback
def ws_alerts(hass, connection, msg):
    entry = printer_entry(hass, msg["entry_id"])
    if entry is None or msg["target"] not in notification_targets(hass) or not msg["kinds"]:
        connection.send_error(
            msg["id"],
            "invalid_selection",
            "Select a loaded printer, available destination and at least one alert",
        )
        return
    prefix = "creator5_alerts_" + entry.entry_id.lower() + "_"
    if any(
        str(state.attributes.get("id", "")).startswith(prefix)
        for state in hass.states.async_all("automation")
    ):
        connection.send_error(
            msg["id"], "already_exists", "Printer alerts already exist; edit them in Automations"
        )
        return
    connection.send_result(
        msg["id"],
        {
            "automation_id": prefix + uuid4().hex,
            "config": alert_config(entry, msg["target"], msg["kinds"]),
        },
    )


async def async_setup_panel(hass):
    for command in (ws_info, ws_dashboard, ws_alerts):
        websocket_api.async_register_command(hass, command)
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                "/creator5_static/setup.js",
                str(Path(__file__).with_name("frontend") / "setup.js"),
                False,
            ),
        ]
    )

    async def register_panel():
        from homeassistant.components import frontend
        from homeassistant.components.panel_custom import async_register_panel

        if hass.data.setdefault(DOMAIN, {}).get("setup_panel_registered"):
            return
        path = "creator5-setup"
        suffix = 2
        while frontend.async_panel_exists(hass, path):
            path = f"creator5-setup-{suffix}"
            suffix += 1
        await async_register_panel(
            hass,
            frontend_url_path=path,
            webcomponent_name="creator5-setup-panel",
            sidebar_title="Creator 5 setup",
            sidebar_icon="mdi:printer-3d",
            module_url="/creator5_static/setup.js?v=0.5.0",
            require_admin=True,
            config_panel_domain=DOMAIN,
        )
        hass.data[DOMAIN]["setup_panel_registered"] = True
        hass.data[DOMAIN]["setup_panel_path"] = path

    if "frontend" in hass.config.components:
        await register_panel()
    else:

        @callback
        def frontend_loaded(event):
            if event.data.get("component") == "frontend":
                remove_listener()
                hass.async_create_task(register_panel())

        remove_listener = hass.bus.async_listen(EVENT_COMPONENT_LOADED, frontend_loaded)
