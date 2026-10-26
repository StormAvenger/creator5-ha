"""Validated integration options; never applied to printer settings."""

import re
from urllib.parse import parse_qs, urlsplit

from .creator5py.client import private_address

DEFAULT_POLL_SECONDS = 10
CONTROL_GROUPS = ("job_controls", "material_controls", "printer_controls", "temperature_controls")


def camera_source(host, value):
    """Restrict media reads to the configured printer, without credentials/redirects."""
    if not isinstance(value, str) or len(value) > 1024 or any(c.isspace() for c in value):
        return None
    try:
        parsed = urlsplit(value)
        if (
            parsed.scheme != "http"
            or parsed.hostname != str(private_address(host))
            or parsed.port != 8080
            or parsed.username is not None
            or parsed.password is not None
            or parsed.fragment
            or parsed.path != "/"
            or parse_qs(parsed.query, keep_blank_values=True) != {"action": ["stream"]}
        ):
            return None
    except ValueError:
        return None
    return value


def validated_options(data, host):
    """Return explicit defaults; reject malformed options before any I/O."""
    interval = data.get("poll_seconds", DEFAULT_POLL_SECONDS)
    enabled = data.get("camera_enabled", True)
    source = data.get("camera_stream_url", "")
    if (
        type(interval) not in (int, float)
        or not 5 <= interval <= 300
        or int(interval) != interval
        or type(enabled) is not bool
    ):
        raise ValueError("Invalid interval or camera preference")
    interval = int(interval)
    if not isinstance(source, str) or (source and camera_source(host, source) is None):
        raise ValueError(
            "Camera URL must be the configured printer's HTTP MJPEG stream on port 8080"
        )
    result = {"poll_seconds": interval, "camera_enabled": enabled, "camera_stream_url": source}
    for key in ("show_setup_sidebar", "file_controls"):
        value = data.get(key, False)
        if type(value) is not bool:
            raise ValueError("Sidebar and file-control preferences must be boolean")
        result[key] = value
    for key, default, low, high in (
        ("bed_cooled_c", 40, 20, 70),
        ("pause_alert_minutes", 10, 1, 120),
        ("offline_alert_minutes", 2, 1, 30),
        ("bed_cleaning_hours", 0, 0, 10000),
        ("rail_lubrication_hours", 0, 0, 10000),
        ("nozzle_inspection_hours", 0, 0, 10000),
    ):
        value = data.get(key, default)
        if type(value) not in (int, float) or not low <= value <= high or int(value) != value:
            raise ValueError("Invalid cooling, alert or maintenance preference")
        result[key] = int(value)
    for group in CONTROL_GROUPS:
        enabled_control = data.get(group, False)
        if type(enabled_control) is not bool:
            raise ValueError("Control preferences must be boolean")
        result[group] = enabled_control
    for tool in range(1, 5):
        slot = data.get(f"tool_{tool}_slot", 0)
        note = data.get(f"tool_{tool}_note", "")
        if isinstance(slot, str) and re.fullmatch(r"[0-4]", slot):
            slot = int(slot)
        if type(slot) is not int or not 0 <= slot <= 4:
            raise ValueError("Tool slot must be unspecified (0) or a slot from 1 to 4")
        if not isinstance(note, str) or not re.fullmatch(r"[A-Za-z0-9 +_.,()/-]{0,64}", note):
            raise ValueError("Material note must be short plain text")
        result[f"tool_{tool}_slot"] = slot
        result[f"tool_{tool}_note"] = note.strip()
    return result
