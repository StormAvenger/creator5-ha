"""On-demand MJPEG viewing through HA; one shared upstream per camera entity."""

import asyncio
from contextlib import asynccontextmanager, suppress

import aiohttp
from aiohttp import web
from homeassistant.components.camera import Camera
from homeassistant.const import CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_SERIAL
from .creator5py import PrinterError
from .creator5py.mjpeg import jpeg_frames
from .entity import Creator5Entity
from .settings import camera_source

TIMEOUT = 10
BOUNDARY = "creator5frame"


async def async_setup_entry(hass, entry, async_add_entities):
    if entry.runtime_data.options["camera_enabled"]:
        async_add_entities(
            [Creator5Camera(entry.runtime_data, entry.data[CONF_SERIAL], entry.data[CONF_HOST])]
        )


class Creator5Camera(Creator5Entity, Camera):
    def __init__(self, coordinator, serial, host):
        Camera.__init__(self)
        Creator5Entity.__init__(self, coordinator, serial, "camera", "Camera")
        self._host = host
        self._subscribers = set()
        self._reader_task = None
        self._camera_failed = False
        self._latest_image = None

    def _source(self):
        value = self.coordinator.options["camera_stream_url"] or self.coordinator.data.detail.get(
            "cameraStreamUrl"
        )
        return camera_source(self._host, value)

    @property
    def available(self):
        return super().available and self._source() is not None and not self._camera_failed

    def _handle_coordinator_update(self):
        # Permit an on-demand retry after the next status update; never probe idle cameras.
        if not self._subscribers:
            self._camera_failed = False
        super()._handle_coordinator_update()

    @asynccontextmanager
    async def _subscribe(self):
        if self._source() is None or not self.coordinator.last_update_success:
            raise PrinterError("Camera source is unavailable")
        queue = asyncio.Queue(maxsize=2)
        self._subscribers.add(queue)
        if self._reader_task is None or self._reader_task.done():
            self._latest_image = None
            self._reader_task = self.hass.async_create_background_task(
                self._read_frames(), "Creator 5 camera"
            )
        elif self._latest_image is not None:
            queue.put_nowait(self._latest_image)
        try:
            yield queue
        finally:
            self._subscribers.discard(queue)
            if not self._subscribers and self._reader_task is not None:
                task, self._reader_task = self._reader_task, None
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
                self._latest_image = None

    def _broadcast(self, image):
        if image is not None:
            self._latest_image = image
        for queue in self._subscribers:
            if image is not None:
                while not queue.empty():
                    queue.get_nowait()
            elif queue.full():
                queue.get_nowait()
            queue.put_nowait(image)

    async def _read_frames(self):
        try:
            source = self._source()
            session = async_get_clientsession(self.hass)
            async with session.get(
                source,
                allow_redirects=False,
                timeout=aiohttp.ClientTimeout(total=None, sock_connect=5, sock_read=TIMEOUT),
            ) as response:
                content_type = response.headers.get("Content-Type", "").lower()
                if response.status != 200 or not content_type.startswith(
                    ("multipart/x-mixed-replace", "image/jpeg")
                ):
                    raise PrinterError("Camera returned an unsupported response")
                async for image in jpeg_frames(response.content.iter_chunked(65536)):
                    self._camera_failed = False
                    self._broadcast(image)
        except (aiohttp.ClientError, TimeoutError, PrinterError, ValueError):
            self._camera_failed = True
        finally:
            if self._subscribers:
                self._camera_failed = True
                self._broadcast(None)
                self.async_write_ha_state()

    async def async_camera_image(self, width=None, height=None):
        try:
            async with self._subscribe() as queue:
                return await asyncio.wait_for(queue.get(), TIMEOUT)
        except (TimeoutError, PrinterError):
            self._camera_failed = True
            self.async_write_ha_state()
            return None

    async def handle_async_mjpeg_stream(self, request):
        response = None
        try:
            async with self._subscribe() as queue:
                image = await asyncio.wait_for(queue.get(), TIMEOUT)
                if image is None:
                    raise web.HTTPBadGateway(text="Printer camera unavailable")
                response = web.StreamResponse(
                    headers={
                        "Content-Type": f"multipart/x-mixed-replace; boundary={BOUNDARY}",
                        "Cache-Control": "no-store",
                    }
                )
                await response.prepare(request)
                while image is not None:
                    part = (
                        f"--{BOUNDARY}\r\nContent-Type: image/jpeg\r\n"
                        f"Content-Length: {len(image)}\r\n\r\n"
                    ).encode()
                    await asyncio.wait_for(response.write(part + image + b"\r\n"), TIMEOUT)
                    image = await asyncio.wait_for(queue.get(), TIMEOUT)
                return response
        except (TimeoutError, ConnectionResetError, PrinterError):
            if response is None:
                raise web.HTTPBadGateway(text="Printer camera unavailable") from None
            return response

    async def async_will_remove_from_hass(self):
        if self._reader_task is not None:
            task, self._reader_task = self._reader_task, None
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        self._subscribers.clear()
        self._latest_image = None
        await super().async_will_remove_from_hass()
