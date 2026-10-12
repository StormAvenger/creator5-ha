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
        "read_only": True,
        "last_update_success": (
            coordinator.last_update_success if coordinator is not None else None
        ),
        "cached_readings": (
            {
                "progress_percent": status.progress_percent,
                "bed_c": status.number("platTemp"),
                "chamber_c": status.number("chamberTemp"),
                "remaining_seconds": status.number("estimatedTime"),
                "tool_temperatures_c": [status.nozzle_temperature(i) for i in range(4)],
                "tool_targets_c": [status.nozzle_temperature(i, target=True) for i in range(4)],
            }
            if status is not None
            else None
        ),
    }
