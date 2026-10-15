"""On-demand media, one upstream, failure/retry and cleanup without sockets."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from custom_components.creator5.camera import Creator5Camera
from custom_components.creator5.creator5py import PrinterStatus
from custom_components.creator5.settings import validated_options

FRAME = b"\xff\xd8synthetic-frame\xff\xd9"
HOST = "10.0.0.42"
URL = f"http://{HOST}:8080/?action=stream"


class Response:
    def __init__(self, status=200):
        self.status = status
        self.headers = {"Content-Type": "multipart/x-mixed-replace; boundary=frame"}
        self.closed = False
        self.finish = asyncio.Event()
        self.content = self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        self.closed = True

    async def iter_chunked(self, size):
        yield b"--frame\r\n" + FRAME
        await self.finish.wait()


def camera(hass):
    coordinator = SimpleNamespace(
        options=validated_options({}, HOST),
        last_update_success=True,
        data=PrinterStatus({"status": "ready", "cameraStreamUrl": URL}),
    )
    entity = Creator5Camera(coordinator, "SYNTHETIC", HOST)
    entity.hass = hass
    entity.async_write_ha_state = Mock()
    return entity


async def test_two_viewers_share_one_upstream_and_last_viewer_closes_it(hass):
    entity = camera(hass)
    response = Response()
    session = SimpleNamespace(get=Mock(return_value=response))
    with patch("custom_components.creator5.camera.async_get_clientsession", return_value=session):
        assert session.get.call_count == 0
        async with entity._subscribe() as first:
            assert await asyncio.wait_for(first.get(), 1) == FRAME
            async with entity._subscribe() as second:
                assert await asyncio.wait_for(second.get(), 1) == FRAME
                assert session.get.call_count == 1
                args, kwargs = session.get.call_args
                assert args == (URL,)
                assert kwargs["allow_redirects"] is False
                assert "headers" not in kwargs and "auth" not in kwargs
            assert not response.closed
        assert response.closed
        assert entity._reader_task is None
        assert entity._latest_image is None
        assert not entity._subscribers


async def test_snapshot_is_on_demand_and_failed_camera_can_retry(hass):
    entity = camera(hass)
    failed = Response(status=503)
    success = Response()
    session = SimpleNamespace(get=Mock(side_effect=[failed, success]))
    with patch("custom_components.creator5.camera.async_get_clientsession", return_value=session):
        assert await entity.async_camera_image() is None
        assert not entity.available
        assert failed.closed
        entity._handle_coordinator_update()
        assert entity.available
        assert await entity.async_camera_image() == FRAME
        assert success.closed
        assert session.get.call_count == 2


async def test_invalid_reported_url_never_gets_requested(hass):
    entity = camera(hass)
    entity.coordinator.data = PrinterStatus(
        {"status": "ready", "cameraStreamUrl": "http://8.8.8.8/private"}
    )
    with patch("custom_components.creator5.camera.async_get_clientsession") as session:
        assert not entity.available
        assert await entity.async_camera_image() is None
        session.assert_not_called()


async def test_mjpeg_proxy_uses_jpeg_parts_without_exposing_source(hass):
    entity = camera(hass)
    response = Response()
    session = SimpleNamespace(get=Mock(return_value=response))
    outgoing = SimpleNamespace(prepare=AsyncMock(), write=AsyncMock(), headers=None)

    async def write(data):
        assert FRAME in data
        assert b"Content-Type: image/jpeg" in data
        response.finish.set()

    outgoing.write.side_effect = write

    def stream_response(*, headers):
        outgoing.headers = headers
        return outgoing

    with (
        patch("custom_components.creator5.camera.async_get_clientsession", return_value=session),
        patch("custom_components.creator5.camera.web.StreamResponse", side_effect=stream_response),
    ):
        assert await entity.handle_async_mjpeg_stream(object()) is outgoing
        assert outgoing.prepare.await_count == 1
        assert outgoing.write.await_count == 1
        assert HOST not in str(outgoing.headers)
        assert "no-store" == outgoing.headers["Cache-Control"]
        assert response.closed
        assert not entity._subscribers
