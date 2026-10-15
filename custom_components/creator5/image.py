"""Local PNG color swatches from the shared, validated material snapshot."""

import struct
import zlib
from functools import lru_cache

from homeassistant.components.image import ImageEntity
from homeassistant.core import callback
from homeassistant.util import dt as dt_util

from .const import CONF_SERIAL
from .entity import Creator5Entity


def _chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


@lru_cache(maxsize=32)
def color_png(color):
    """Render a bounded RGB swatch; callers supply only validated #RRGGBB values."""
    rgb = bytes.fromhex(color[1:])
    # A light border keeps black/white filament visible against either HA theme.
    border = bytes((128, 128, 128))
    rows = b"".join(
        b"\0"
        + b"".join(border if x < 2 or x >= 158 or y < 2 or y >= 78 else rgb for x in range(160))
        for y in range(80)
    )
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", 160, 80, 8, 2, 0, 0, 0))
        + _chunk(b"IDAT", zlib.compress(rows))
        + _chunk(b"IEND", b"")
    )


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(
        [
            Creator5SlotSwatch(entry.runtime_data, entry.data[CONF_SERIAL], slot)
            for slot in range(1, 5)
        ]
    )


class Creator5SlotSwatch(Creator5Entity, ImageEntity):
    _attr_content_type = "image/png"

    def __init__(self, coordinator, serial, slot):
        ImageEntity.__init__(self, coordinator.hass)
        Creator5Entity.__init__(
            self, coordinator, serial, f"slot_{slot}_swatch", f"Slot {slot} color swatch"
        )
        self._slot = slot
        self._color = self._current_color()
        if self._color is not None:
            self._attr_image_last_updated = dt_util.utcnow()

    def _current_color(self):
        slot = self.coordinator.data.material_slot(self._slot)
        return slot["color"] if slot else None

    @property
    def available(self):
        return super().available and self._color is not None

    @callback
    def _handle_coordinator_update(self):
        color = self._current_color()
        if color != self._color:
            self._color = color
            self._attr_image_last_updated = dt_util.utcnow() if color else None
        super()._handle_coordinator_update()

    async def async_image(self):
        # No printer request, URL, camera read or file is involved.
        return color_png(self._color) if self.available else None
