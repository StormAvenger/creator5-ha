"""Real HA authenticated file tools; all physical printer transport is blocked."""

import io
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest
from homeassistant.exceptions import Unauthorized
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_socket import socket_allow_hosts

from custom_components.creator5.const import DOMAIN
from custom_components.creator5.creator5py import Creator5Client, PrinterError, PrinterStatus
from custom_components.creator5.file_browser import (
    Confirmations,
    manager,
    ws_execute,
    ws_files,
    ws_prepare,
    ws_thumbnail,
)
from custom_components.creator5.setup_panel import async_refresh_panel

ORIGINAL_REQUEST = Creator5Client._request

DATA = {"host": "10.0.0.42", "serial_number": "SYNTHETIC-SN", "check_code": "synthetic-code"}
READY = {"status": "ready", "model": "Creator 5 Pro", "errorCode": ""}
ACTIVE = {**READY, "status": "printing", "printFileName": "part.3mf", "printDuration": 30}


@pytest.fixture(autouse=True)
def block_printer_io():
    socket_allow_hosts(["127.0.0.1", "::1"], allow_unix_socket=True)
    with (
        patch(
            "custom_components.creator5.Creator5Client.get_status",
            new=AsyncMock(return_value=PrinterStatus(READY)),
        ),
        patch(
            "custom_components.creator5.Creator5Client._request",
            new=AsyncMock(
                side_effect=AssertionError("Physical printer access is forbidden in tests")
            ),
        ),
    ):
        yield


async def setup(hass, **options):
    entry = MockConfigEntry(domain=DOMAIN, data=DATA, minor_version=2, options=options)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def ws_call(client, id, type, entry, **data):
    await client.send_json({"id": id, "type": type, "entry_id": entry.entry_id, **data})
    return await client.receive_json()


@pytest.mark.parametrize("handler", [ws_files, ws_thumbnail, ws_prepare, ws_execute])
async def test_all_file_websocket_handlers_require_admin(hass, handler):
    with pytest.raises(Unauthorized):
        handler(hass, SimpleNamespace(user=SimpleNamespace(is_admin=False)), {"id": 1})


async def test_browsing_works_with_writes_off_and_prepare_is_blocked(hass, hass_ws_client):
    entry = await setup(hass)
    client = await hass_ws_client(hass)
    with patch.object(
        entry.runtime_data.client, "list_files", new=AsyncMock(return_value=["part.3mf"])
    ):
        reply = await ws_call(client, 1, "creator5/files", entry)
        assert reply["result"] == {"files": ["part.3mf"]}
        reply = await ws_call(
            client, 2, "creator5/file_prepare", entry, action="start", filename="part.3mf"
        )
        assert not reply["success"] and "Enable" in reply["error"]["message"]
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_start_confirmation_is_bound_to_user_entry_and_single_use(hass, hass_ws_client):
    entry = await setup(hass, file_controls=True)
    client = await hass_ws_client(hass)
    with (
        patch.object(
            entry.runtime_data.client, "list_files", new=AsyncMock(return_value=["part.3mf"])
        ),
        patch.object(
            entry.runtime_data.client,
            "start_file",
            new=AsyncMock(return_value=PrinterStatus(ACTIVE)),
        ) as start,
    ):
        reply = await ws_call(
            client, 1, "creator5/file_prepare", entry, action="start", filename="part.3mf"
        )
        assert reply["success"]
        assert "numbered material slots" in reply["result"]["message"]
        start.assert_not_awaited()
        token = reply["result"]["token"]
        with pytest.raises(PrinterError, match="expired or changed"):
            manager(hass).consume("another-user", entry.entry_id, token)
        assert (await ws_call(client, 2, "creator5/file_execute", entry, token=token))["success"]
        start.assert_awaited_once_with("part.3mf", confirmed=True)
        assert not (await ws_call(client, 3, "creator5/file_execute", entry, token=token))[
            "success"
        ]
        assert start.await_count == 1
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_cancel_prepares_current_job_and_does_not_write_until_confirmed(hass, hass_ws_client):
    entry = await setup(hass, file_controls=True)
    client = await hass_ws_client(hass)
    with (
        patch.object(
            entry.runtime_data.client,
            "get_status",
            new=AsyncMock(return_value=PrinterStatus(ACTIVE)),
        ),
        patch.object(
            entry.runtime_data.client,
            "cancel_print",
            new=AsyncMock(return_value=PrinterStatus({**READY, "status": "cancel"})),
        ) as cancel,
    ):
        reply = await ws_call(
            client, 1, "creator5/file_prepare", entry, action="cancel", filename="wrong.3mf"
        )
        assert reply["success"] and "part.3mf" in reply["result"]["message"]
        cancel.assert_not_awaited()
        assert (
            await ws_call(client, 2, "creator5/file_execute", entry, token=reply["result"]["token"])
        )["success"]
        cancel.assert_awaited_once_with("part.3mf", 30, confirmed=True)
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_disabling_file_controls_revokes_a_prepared_action(hass, hass_ws_client):
    entry = await setup(hass, file_controls=True)
    client = await hass_ws_client(hass)
    token = manager(hass).prepare("test", entry.entry_id, "start", "part.3mf")
    # Mutate permissions without initiating a real reload, to check action-time validation.
    with patch.object(hass.config_entries, "async_reload", new=AsyncMock(return_value=True)):
        hass.config_entries.async_update_entry(entry, options={"file_controls": False})
        reply = await ws_call(client, 1, "creator5/file_execute", entry, token=token)
        assert not reply["success"] and "Enable" in reply["error"]["message"]
    assert await hass.config_entries.async_unload(entry.entry_id)


def test_confirmation_expiry_replacement_and_action_binding():
    confirmations = Confirmations()
    token = confirmations.prepare("user", "entry", "cancel", "part.3mf", 30)
    for invalid in (None, "é", "x" * 129):
        with pytest.raises(PrinterError):
            confirmations.consume("user", "entry", invalid)
    with pytest.raises(PrinterError):
        confirmations.consume("user", "entry", token, "upload")
    replacement = confirmations.prepare("user", "entry", "upload", "new.gcode")
    with pytest.raises(PrinterError):
        confirmations.consume("user", "entry", token)
    assert confirmations.consume("user", "entry", replacement, "upload")[1] == "new.gcode"
    token = confirmations.prepare("user", "entry", "cancel", "part.3mf", 30)
    with (
        patch("custom_components.creator5.file_browser.time.monotonic", return_value=10**20),
        pytest.raises(PrinterError),
    ):
        confirmations.consume("user", "entry", token)


async def test_sidebar_hidden_default_link_available_and_toggle_preserves_collision(hass):
    assert await async_setup_component(hass, "frontend", {})
    from homeassistant.components import frontend

    frontend.async_register_built_in_panel(
        hass, "map", frontend_url_path="creator5-setup", sidebar_title="Keep this"
    )
    original = hass.data["frontend_panels"]["creator5-setup"]
    entry = await setup(hass)
    path = hass.data[DOMAIN]["setup_panel_path"]
    assert path == "creator5-setup-2"
    panel = hass.data["frontend_panels"][path]
    assert panel.sidebar_title is None and panel.require_admin
    assert panel.config_panel_domain == DOMAIN
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    assert flow["description_placeholders"]["setup_url"] == "/creator5-setup-2"
    with patch.object(hass.config_entries, "async_reload", new=AsyncMock(return_value=True)):
        hass.config_entries.async_update_entry(entry, options={"show_setup_sidebar": True})
        await async_refresh_panel(hass)
        assert hass.data["frontend_panels"][path].sidebar_title == "Creator 5 tools"
    hass.config_entries.async_update_entry(entry, options={"show_setup_sidebar": False})
    await async_refresh_panel(hass)
    await hass.async_block_till_done()
    assert hass.data["frontend_panels"][path].sidebar_title is None
    assert hass.data["frontend_panels"]["creator5-setup"] is original
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_http_upload_requires_auth_and_admin(hass, hass_client, hass_client_no_auth):
    entry = await setup(hass, file_controls=True)
    no_auth = await hass_client_no_auth()
    path = f"/api/creator5/files/{entry.entry_id}/upload"
    assert (await no_auth.post(path)).status == 401
    user = await hass.auth.async_create_user("Regular user")
    refresh = await hass.auth.async_create_refresh_token(user, client_id="https://example.test")
    token = hass.auth.async_create_access_token(refresh)
    client = await hass_client(token)
    assert (await client.post(path)).status == 403
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_http_upload_is_unique_upload_only_and_cleans_temporary_file(
    hass, hass_ws_client, hass_client
):
    entry = await setup(hass, file_controls=True)
    websocket = await hass_ws_client(hass)
    prepared = await ws_call(
        websocket, 1, "creator5/file_prepare", entry, action="upload", filename="part.gcode"
    )
    token = prepared["result"]["token"]
    client = await hass_client()
    captured = []

    async def upload(name, stream):
        captured.append((name, stream))
        stream.seek(0)
        assert stream.read() == b"; sliced\nG28\n"
        return PrinterStatus(READY)

    with patch.object(entry.runtime_data.client, "upload_file", side_effect=upload):
        form = aiohttp.FormData()
        form.add_field("file", io.BytesIO(b"; sliced\nG28\n"), filename="part.gcode")
        response = await client.post(
            f"/api/creator5/files/{entry.entry_id}/upload",
            data=form,
            headers={"X-Creator5-Confirmation": token},
        )
        assert response.status == 200, await response.text()
        result = await response.json()
        assert result["filename"].startswith("part-") and result["filename"].endswith(".gcode")
        assert len(captured) == 1 and captured[0][1].closed
        replay = await client.post(
            f"/api/creator5/files/{entry.entry_id}/upload",
            headers={"X-Creator5-Confirmation": token},
        )
        assert replay.status == 400
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_http_upload_size_guard_prevents_printer_write(hass, hass_ws_client, hass_client):
    entry = await setup(hass, file_controls=True)
    websocket = await hass_ws_client(hass)
    prepared = await ws_call(
        websocket, 1, "creator5/file_prepare", entry, action="upload", filename="part.gcode"
    )
    client = await hass_client()
    form = aiohttp.FormData()
    form.add_field("file", b"; sliced file\nG28\n", filename="part.gcode")
    with (
        patch("custom_components.creator5.file_browser.MAX_UPLOAD", 8),
        patch.object(entry.runtime_data.client, "upload_file", new=AsyncMock()) as upload,
    ):
        response = await client.post(
            f"/api/creator5/files/{entry.entry_id}/upload",
            data=form,
            headers={"X-Creator5-Confirmation": prepared["result"]["token"]},
        )
        assert response.status == 400
        upload.assert_not_awaited()
        assert not manager(hass).uploading
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_real_multipart_transport_stays_upload_only(hass, aiohttp_client, socket_enabled):
    """Exercise actual HTTP serialization against a loopback mock printer."""
    from aiohttp import web

    entry = await setup(hass, file_controls=True)
    received = []
    files = []

    async def detail(_request):
        return web.json_response({"code": 0, "detail": READY})

    async def listing(request):
        auth = await request.json()
        assert auth == {"serialNumber": DATA["serial_number"], "checkCode": DATA["check_code"]}
        return web.json_response({"code": 0, "gcodeList": files})

    async def upload(request):
        assert request.headers["printNow"] == "false"
        assert "materialMappings" not in request.headers
        assert request.headers["serialNumber"] == DATA["serial_number"]
        assert request.headers["checkCode"] == DATA["check_code"]
        reader = await request.multipart()
        part = await reader.next()
        assert part.name == "gcodeFile"
        data = await part.read()
        assert request.headers["fileSize"] == str(len(data))
        received.append(bytes(data))
        files.append(part.filename)
        assert await reader.next() is None
        return web.json_response({"code": 0})

    app = web.Application()
    app.router.add_post("/detail", detail)
    app.router.add_post("/gcodeList", listing)
    app.router.add_post("/uploadGcode", upload)
    server = await aiohttp_client(app)
    client = entry.runtime_data.client
    # Explicitly replace the synthetic target with this loopback-only mock server.
    client._url = str(server.make_url("/")).rstrip("/")
    with patch.object(client, "_request", ORIGINAL_REQUEST.__get__(client)):
        with io.BytesIO(b"; trusted slice\nG28\n") as stream:
            assert (await client.upload_file("unique.gcode", stream)).state == "ready"
    assert received == [b"; trusted slice\nG28\n"]
    assert files == ["unique.gcode"]
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_removing_last_sidebar_opt_in_hides_shared_shortcut(hass):
    assert await async_setup_component(hass, "frontend", {})
    entry = await setup(hass, show_setup_sidebar=True)
    path = hass.data[DOMAIN]["setup_panel_path"]
    assert hass.data["frontend_panels"][path].sidebar_title == "Creator 5 tools"
    assert await hass.config_entries.async_remove(entry.entry_id)
    assert hass.data["frontend_panels"][path].sidebar_title is None
