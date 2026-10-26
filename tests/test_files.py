"""File protocol, confirmation and archive boundaries without printer access."""

import asyncio
import base64
import io
import zipfile
from unittest.mock import patch

import pytest
from creator5py import PrinterError
from creator5py.client import ControlError
from creator5py.files import MAX_UPLOAD, file_name, upload_name, validate_slice
from test_client import SequenceSession, Session, client


def detail(state="ready", name="part.3mf", elapsed=20):
    return {
        "code": 0,
        "detail": {
            "status": state,
            "model": "Creator 5 Pro",
            "printFileName": name,
            "printDuration": elapsed,
        },
    }


def listing(*names):
    return {"code": 0, "gcodeList": list(names)}


def archive(entries):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as output:
        for name, content in entries:
            output.writestr(name, content)
    stream.seek(0)
    return stream


@pytest.mark.parametrize(
    "name",
    [
        None,
        "",
        "../a.3mf",
        "a/b.gcode",
        "a\\b.gcode",
        "a\r\nx.gcode",
        ".x.3mf",
        "x.stl",
        "http:x.gcode",
        "x.3mf ",
        "a" * 201 + ".gcode",
    ],
)
def test_filename_boundary(name):
    with pytest.raises(ValueError):
        file_name(name)


def test_names_with_spaces_are_supported_unique_uploads_keep_extension():
    assert file_name("part number 2.3mf") == "part number 2.3mf"
    assert upload_name("part number 2.3mf", "unique") == "part-number-2-unique.3mf"


@pytest.mark.parametrize(
    "entries",
    [
        [("model.stl", b"model")],
        [("../x.gcode", b"G28")],
        [("/x.gcode", b"G28")],
        [("C:x.gcode", b"G28")],
        [("x.gcode", b"")],
    ],
)
def test_reject_unsliced_or_traversing_archives(entries):
    with pytest.raises(ValueError):
        validate_slice(archive(entries), "part.3mf")


def test_sliced_archive_validated_without_extraction_and_stream_rewound():
    stream = archive(
        [("Metadata/plate_1.gcode", b"; sliced\nG28\n"), ("Metadata/slice.xml", b"<slice/>")]
    )
    size = validate_slice(stream, "part.3mf")
    assert size > 0 and stream.tell() == 0


@pytest.mark.parametrize("content", [b"", b"PK\x00\x01", b"\xff\xfe", b"\x00"])
def test_gcode_rejects_empty_or_binary(content):
    with pytest.raises(ValueError):
        validate_slice(io.BytesIO(content), "part.gcode")


async def test_file_list_is_read_only_and_filters_unsafe_entries():
    session = Session(listing("part.3mf", "part.3mf", "../private.gcode", "model.stl", "a b.gcode"))
    assert await client(session).list_files() == ["part.3mf", "a b.gcode"]
    assert len(session.calls) == 1
    assert session.calls[0][0].endswith("/gcodeList")


async def test_thumbnail_is_fixed_authenticated_post_and_not_a_reported_url():
    content = b"\xff\xd8demo\xff\xd9"
    session = SequenceSession(
        [listing("part.3mf"), {"code": 0, "imageData": base64.b64encode(content).decode()}]
    )
    assert await client(session).get_file_thumbnail("part.3mf") == (content, "image/jpeg")
    assert session.calls[-1][0].endswith("/gcodeThumb")
    assert session.calls[-1][1]["json"]["fileName"] == "part.3mf"
    assert all(not kw["allow_redirects"] for _, kw in session.calls)


async def test_start_requires_explicit_confirmation_before_io():
    session = Session(None)
    with pytest.raises(ValueError):
        await client(session).start_file("part.3mf")
    assert not session.calls


@pytest.mark.parametrize("state", ["printing", "pause", "completed", "error", "unknown"])
async def test_start_never_interrupts_nonready_state(state):
    session = Session(detail(state))
    with pytest.raises(PrinterError, match="ready"):
        await client(session).start_file("part.3mf", confirmed=True)
    assert len(session.calls) == 1


async def test_start_checks_file_and_verifies_heating_without_guessed_mappings():
    session = SequenceSession([detail(), listing("part.3mf"), {"code": 0}, detail("heating")])
    status = await client(session).start_file("part.3mf", confirmed=True)
    assert status.state == "heating"
    writes = [kw for url, kw in session.calls if url.endswith("/printGcode")]
    assert len(writes) == 1
    assert writes[0]["json"] == {
        "serialNumber": "TEST-SN",
        "checkCode": "secret",
        "fileName": "part.3mf",
        "levelingBeforePrint": True,
        "flowCalibration": False,
        "timeLapseVideo": False,
    }


async def test_start_does_not_retry_after_timeout_or_clear_dialog():
    session = SequenceSession([detail(), listing("part.3mf"), TimeoutError()])
    with pytest.raises(ControlError, match="unconfirmed"):
        await client(session).start_file("part.3mf", confirmed=True)
    assert len(session.calls) == 3


@pytest.mark.parametrize("name,elapsed", [("other.3mf", 21), ("part.3mf", 1), ("part.3mf", 200)])
async def test_cancel_rejects_changed_job_before_write(name, elapsed):
    session = Session(detail("printing", name, elapsed))
    with pytest.raises(PrinterError, match="changed"):
        await client(session).cancel_print("part.3mf", 20, confirmed=True)
    assert len(session.calls) == 1


async def test_cancel_once_without_completion_acknowledgement():
    session = SequenceSession([detail("pause"), {"code": 0}, detail("cancel")])
    assert (await client(session).cancel_print("part.3mf", 20, confirmed=True)).state == "cancel"
    writes = [kw["json"]["payload"] for url, kw in session.calls if url.endswith("/control")]
    assert writes == [{"cmd": "jobCtl_cmd", "args": {"action": "cancel", "jobID": ""}}]


async def test_upload_never_starts_or_includes_mappings_and_verifies_listing():
    session = SequenceSession([detail(), listing(), {"code": 0}, detail(), listing("part.gcode")])
    stream = io.BytesIO(b"; trusted sliced file\nG28\n")
    assert (await client(session).upload_file("part.gcode", stream)).state == "ready"
    upload = next(kw for url, kw in session.calls if url.endswith("/uploadGcode"))
    assert upload["headers"]["printNow"] == "false"
    assert upload["headers"]["fileSize"] == str(len(stream.getvalue()))
    assert "materialMappings" not in upload["headers"]
    assert "json" not in upload and upload["allow_redirects"] is False
    assert not any(
        url.endswith("/printGcode") or url.endswith("/control") for url, _ in session.calls
    )


@pytest.mark.parametrize("state", ["printing", "pause", "completed"])
async def test_upload_refuses_nonready_printer(state):
    session = Session(detail(state))
    with pytest.raises(PrinterError, match="ready"):
        await client(session).upload_file("part.gcode", io.BytesIO(b"G28\n"))
    assert len(session.calls) == 1


async def test_upload_rejects_existing_name():
    session = SequenceSession([detail(), listing("part.gcode")])
    with pytest.raises(PrinterError, match="already exists"):
        await client(session).upload_file("part.gcode", io.BytesIO(b"G28\n"))
    assert len(session.calls) == 2


async def test_serialization_prevents_status_poll_interleaving_with_start():
    session = SequenceSession(
        [detail(), listing("part.3mf"), {"code": 0}, detail("printing"), detail("printing")]
    )
    api = client(session)
    await asyncio.gather(api.start_file("part.3mf", confirmed=True), api.get_status())
    assert [url.rsplit("/", 1)[-1] for url, _ in session.calls] == [
        "detail",
        "gcodeList",
        "printGcode",
        "detail",
        "detail",
    ]


def test_expanded_archive_and_upload_size_limits():
    stream = archive([("part.gcode", b"G28\n" * 30)])
    with patch("creator5py.files.MAX_EXPANDED", 20), pytest.raises(ValueError):
        validate_slice(stream, "part.3mf")
    stream = io.BytesIO(b"x")
    stream.seek(MAX_UPLOAD)
    stream.write(b"x")
    with pytest.raises(ValueError, match="64 MiB"):
        validate_slice(stream, "part.gcode")


async def test_oversized_file_reply_is_bounded_before_json_parsing():
    session = Session(listing("x" * (4 * 1024 * 1024)))
    with pytest.raises(PrinterError, match="size limit"):
        await client(session).list_files()
    assert len(session.calls) == 1


@pytest.mark.parametrize(
    "payload", [{"code": 0, "gcodeList": None}, {"code": 0, "gcodeList": ["x.gcode"] * 257}]
)
async def test_malformed_file_list_does_not_become_an_actionable_selection(payload):
    with pytest.raises(PrinterError, match="invalid file list"):
        await client(Session(payload)).list_files()


async def test_upload_ack_without_listing_is_unconfirmed_and_not_retried():
    session = SequenceSession([detail(), listing(), {"code": 0}, detail(), listing()])
    with pytest.raises(ControlError, match="not confirmed"):
        await client(session).upload_file("part.gcode", io.BytesIO(b"G28\n"))
    assert sum(url.endswith("/uploadGcode") for url, _ in session.calls) == 1


def test_corrupted_deflate_stream_is_rejected_as_an_invalid_slice():
    import struct

    data = bytearray(archive([("part.gcode", b"G28\n" * 30)]).getvalue())
    name_length, extra_length = struct.unpack_from("<HH", data, 26)
    offset = 30 + name_length + extra_length
    data[offset : offset + 4] = b"\xff" * 4
    with pytest.raises(ValueError, match="Invalid or unsupported"):
        validate_slice(io.BytesIO(data), "part.3mf")
