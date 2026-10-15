"""Synthetic camera framing and bounded memory; no LAN access."""

import pytest
from creator5py import PrinterError
from creator5py.mjpeg import jpeg_frames


async def chunks(parts):
    for part in parts:
        yield part


async def test_split_markers_headers_multiple_frames_and_trailing_bytes():
    source = chunks(
        [
            b"--frame\r\nHeaders\r\n\xff",
            b"\xd8first\xff",
            b"\xd9\r\n--frame\r\n\xff\xd8second\xff\xd9tail",
        ]
    )
    assert [image async for image in jpeg_frames(source)] == [
        b"\xff\xd8first\xff\xd9",
        b"\xff\xd8second\xff\xd9",
    ]


@pytest.mark.parametrize("data", [b"not a JPEG" * 100, b"\xff\xd8" + b"x" * 1000])
async def test_unbounded_preamble_or_unterminated_image_is_rejected(data):
    with pytest.raises(PrinterError, match="size limit"):
        [frame async for frame in jpeg_frames(chunks([data]), limit=100)]
