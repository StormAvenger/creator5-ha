"""Admin-only file tools with explicit, single-use, user-bound confirmations."""

import asyncio
import base64
import secrets
import tempfile
import time

import probatio as vol
from homeassistant.components import websocket_api
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.http.const import KEY_HASS_USER
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .creator5py import PrinterError
from .creator5py.client import ControlError
from .creator5py.files import MAX_UPLOAD, file_name, upload_name


def loaded_entry(hass, entry_id, *, write=False):
    from .setup_panel import printer_entry

    entry = printer_entry(hass, entry_id)
    if entry is None:
        raise PrinterError("Select a loaded Creator 5 printer")
    if write and entry.options.get("file_controls", False) is not True:
        raise PrinterError("Enable file uploads, reprints and cancellation in Configure first")
    return entry


class Confirmations:
    def __init__(self):
        self.pending = {}
        self.uploading = False

    def prepare(self, user, entry, action, name, elapsed=None):
        # One pending action per user/printer; bounded lifetime, no persisted filenames.
        now = time.monotonic()
        self.pending = {k: v for k, v in self.pending.items() if v[0] > now}
        if len(self.pending) >= 128:
            raise PrinterError("Too many pending confirmations; try again in a minute")
        token = secrets.token_urlsafe(24)
        self.pending[(user, entry)] = (now + 60, token, action, name, elapsed)
        return token

    def consume(self, user, entry, token, action=None):
        key = (user, entry)
        pending = self.pending.get(key)
        if (
            pending is None
            or not isinstance(token, str)
            or len(token) > 128
            or not token.isascii()
            or not secrets.compare_digest(pending[1], token)
            or pending[0] < time.monotonic()
            or (action is not None and pending[2] != action)
        ):
            raise PrinterError("Confirmation expired or changed; review the action again")
        del self.pending[key]
        return pending[2:]


def manager(hass):
    return hass.data[DOMAIN]["file_confirmations"]


@websocket_api.require_admin
@websocket_api.websocket_command({"type": "creator5/files", vol.Required("entry_id"): str})
@websocket_api.async_response
async def ws_files(hass, connection, msg):
    try:
        entry = loaded_entry(hass, msg["entry_id"])
        names = await entry.runtime_data.client.list_files()
        connection.send_result(msg["id"], {"files": names})
    except PrinterError as err:
        connection.send_error(msg["id"], "printer_error", str(err))


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        "type": "creator5/file_thumbnail",
        vol.Required("entry_id"): str,
        vol.Required("filename"): str,
    }
)
@websocket_api.async_response
async def ws_thumbnail(hass, connection, msg):
    try:
        entry = loaded_entry(hass, msg["entry_id"])
        content, mime = await entry.runtime_data.client.get_file_thumbnail(msg["filename"])
        connection.send_result(
            msg["id"], {"image": base64.b64encode(content).decode(), "mime": mime}
        )
    except (PrinterError, ValueError) as err:
        connection.send_error(msg["id"], "printer_error", str(err))


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        "type": "creator5/file_prepare",
        vol.Required("entry_id"): str,
        vol.Required("action"): vol.In(("start", "cancel", "upload")),
        vol.Optional("filename"): str,
    }
)
@websocket_api.async_response
async def ws_prepare(hass, connection, msg):
    try:
        entry = loaded_entry(hass, msg["entry_id"], write=True)
        c = entry.runtime_data
        status = await c.client.get_status()
        action, name, elapsed = msg["action"], msg.get("filename", ""), None
        if action == "cancel":
            name, elapsed = c.client.file_job_name(status), status.nonnegative("printDuration")
            if (
                status.state not in ("printing", "heating", "paused", "pause")
                or name is None
                or elapsed is None
            ):
                raise PrinterError("No identifiable active print to cancel")
            message = f"Cancel the current print “{name}”? This stops the job and cannot be undone."
        else:
            file_name(name)
            c.client._ready(status)
            if action == "start":
                if name not in await c.client.list_files():
                    raise PrinterError("File is no longer in the printer's file list")
                message = (
                    f"Start “{name}”? Confirm the bed is physically clear, this file was sliced "
                    "for this printer/nozzles, and numbered material slots match the slicer "
                    "(filament 1 → slot 1, etc.). Previous custom mappings and HA tool notes "
                    "are not applied. Automatic leveling will run."
                )
            else:
                message = (
                    f"Upload “{name}” only? Confirm this is a trusted slice for this printer. "
                    "A unique filename will be used. Uploading never starts a print."
                )
        token = manager(hass).prepare(connection.user.id, entry.entry_id, action, name, elapsed)
        connection.send_result(msg["id"], {"token": token, "message": message})
    except (PrinterError, ValueError) as err:
        connection.send_error(msg["id"], "printer_error", str(err))


@websocket_api.require_admin
@websocket_api.websocket_command(
    {"type": "creator5/file_execute", vol.Required("entry_id"): str, vol.Required("token"): str}
)
@websocket_api.async_response
async def ws_execute(hass, connection, msg):
    try:
        entry = loaded_entry(hass, msg["entry_id"], write=True)
        action, name, elapsed = manager(hass).consume(
            connection.user.id, entry.entry_id, msg["token"]
        )
        c = entry.runtime_data
        if action == "start":
            status = await c.client.start_file(name, confirmed=True)
        elif action == "cancel":
            status = await c.client.cancel_print(name, elapsed, confirmed=True)
        else:
            raise PrinterError("Use the file upload form for this action")
        publish(c, status)
        connection.send_result(msg["id"], {"state": status.state})
    except (PrinterError, ValueError) as err:
        if isinstance(err, ControlError):
            entry.runtime_data.last_control_failure_stage = err.stage
        connection.send_error(msg["id"], "printer_error", str(err))


def publish(coordinator, status):
    coordinator.last_control_failure_stage = None
    coordinator.last_successful_update = dt_util.utcnow()
    coordinator._process_status(status)
    coordinator.async_set_updated_data(status)


class FileUploadView(HomeAssistantView):
    url = "/api/creator5/files/{entry_id}/upload"
    name = "api:creator5:files:upload"
    requires_auth = True

    async def post(self, request, entry_id):
        user = request[KEY_HASS_USER]
        if not user.is_admin:
            return self.json_message("Administrator access required", 403)
        hass = request.app["hass"]
        state = manager(hass)
        if state.uploading:
            return self.json_message("Another upload is in progress", 409)
        try:
            entry = loaded_entry(hass, entry_id, write=True)
            coordinator = entry.runtime_data
            _action, name, _elapsed = state.consume(
                user.id, entry_id, request.headers.get("X-Creator5-Confirmation", ""), "upload"
            )
        except PrinterError as err:
            return self.json_message(str(err), 400)
        state.uploading = True
        try:
            # Disk-backed private temporary storage, always removed even on disconnect/failure.
            with tempfile.TemporaryFile() as stream:
                async with asyncio.timeout(120):
                    reader = await request.multipart()
                    part = await reader.next()
                    if part is None or part.name != "file" or part.filename != name:
                        raise ValueError("Upload the exact file selected for confirmation")
                    size = 0
                    while chunk := await part.read_chunk(1024 * 1024):
                        size += len(chunk)
                        if size > MAX_UPLOAD:
                            raise ValueError("Sliced files must be at most 64 MiB")
                        await hass.async_add_executor_job(stream.write, chunk)
                    if await reader.next() is not None:
                        raise ValueError("Upload one sliced file at a time")
                loaded_entry(hass, entry_id, write=True)
                if entry.runtime_data is not coordinator:
                    raise PrinterError("Integration reloaded; review the upload again")
                stored_name = upload_name(name, secrets.token_hex(8))
                status = await coordinator.client.upload_file(stored_name, stream)
                publish(coordinator, status)
                return self.json({"filename": stored_name, "state": status.state})
        except (PrinterError, ValueError, TimeoutError, AssertionError) as err:
            if isinstance(err, ControlError):
                coordinator.last_control_failure_stage = err.stage
            message = (
                str(err)
                if isinstance(err, (PrinterError, ValueError))
                else "Upload could not complete; check the file list before retrying"
            )
            return self.json_message(message, 400)
        finally:
            state.uploading = False


def register_files(hass):
    hass.data.setdefault(DOMAIN, {})["file_confirmations"] = Confirmations()
    for handler in (ws_files, ws_thumbnail, ws_prepare, ws_execute):
        websocket_api.async_register_command(hass, handler)
    hass.http.register_view(FileUploadView())
