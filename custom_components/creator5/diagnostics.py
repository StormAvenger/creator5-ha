"""Troubleshooting from cached readings only; never request printer data."""

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Exclude config, raw payloads, free-form strings and identifiers by design."""
    coordinator = getattr(entry, "runtime_data", None)
    status = coordinator.data if coordinator is not None else None
    return {
        "read_only": False,
        "control_scope": "chamber_light_only",
        "last_update_success": (
            coordinator.last_update_success if coordinator is not None else None
        ),
        "poll_seconds": coordinator.update_interval.total_seconds()
        if coordinator is not None
        else None,
        "last_successful_update": (
            coordinator.last_successful_update.isoformat()
            if coordinator is not None and coordinator.last_successful_update is not None
            else None
        ),
        "cached_readings": (
            {
                "progress_percent": status.progress_percent,
                "bed_c": status.number("platTemp"),
                "chamber_c": status.number("chamberTemp"),
                "remaining_seconds": status.nonnegative("estimatedTime")
                if status.state in ("printing", "paused", "pause")
                else None,
                "tool_temperatures_c": [status.nozzle_temperature(i) for i in range(4)],
                "tool_targets_c": [status.nozzle_temperature(i, target=True) for i in range(4)],
            }
            if status is not None
            else None
        ),
    }
