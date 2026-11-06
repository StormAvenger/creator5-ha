"""Alert snapshots saved to Home Assistant's local media folder."""

from pathlib import Path

from homeassistant.util import dt as dt_util

# Alerts where the printer is reachable and a picture helps. Connection-lost and
# maintenance alerts are sent without one.
SNAPSHOT_KINDS = ("completed", "bed_cooled", "error", "prolonged_pause")
KEEP = 20  # most recent snapshots kept per printer
MAX_BYTES = 4 * 1024 * 1024


def _write(folder: Path, name: str, image: bytes) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_bytes(image)
    for old in sorted(folder.glob("*.jpg"))[:-KEEP]:
        old.unlink(missing_ok=True)


async def async_save_snapshot(hass, entry_id, kind, image):
    """Save one JPEG; return its media URL for notifications, or None."""
    media = hass.config.media_dirs.get("local")
    if (
        media is None
        or kind not in SNAPSHOT_KINDS
        or not image.startswith(b"\xff\xd8")
        or len(image) > MAX_BYTES
    ):
        return None
    folder = Path(media) / "creator5" / entry_id
    name = f"{dt_util.now().strftime('%Y%m%d-%H%M%S')}-{kind}.jpg"
    await hass.async_add_executor_job(_write, folder, name, image)
    return f"/media/local/creator5/{entry_id}/{name}"
