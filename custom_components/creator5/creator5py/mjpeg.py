"""Bounded JPEG frame extraction from an asynchronous MJPEG byte source."""

from collections.abc import AsyncIterator

from .client import PrinterError


async def jpeg_frames(chunks: AsyncIterator[bytes], limit: int = 2_097_152) -> AsyncIterator[bytes]:
    data = bytearray()
    async for chunk in chunks:
        data.extend(chunk)
        while True:
            start = data.find(b"\xff\xd8")
            if start >= 0:
                del data[:start]
                end = data.find(b"\xff\xd9", 2)
                if end >= 0:
                    if end + 2 > limit:
                        raise PrinterError("Camera frame exceeded the size limit")
                    frame = bytes(data[: end + 2])
                    del data[: end + 2]
                    yield frame
                    continue
            if len(data) > limit:
                raise PrinterError("Camera frame exceeded the size limit")
            break
