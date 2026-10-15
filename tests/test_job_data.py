"""Synthetic job metadata and fixed-endpoint thumbnail boundaries."""

from typing import cast

import aiohttp
import pytest
from creator5py import Creator5Client, PrinterError, PrinterStatus


@pytest.mark.parametrize(
    "value", [None, "", " ", "x" * 256, "../secret", "C:\\secret", "a\nname", "a\x00b", 7]
)
def test_invalid_filename_stays_unknown(value):
    assert PrinterStatus({"status": "printing", "printFileName": value}).current_filename is None


def test_job_name_only_active_and_counters_preserve_zero():
    for state in ("printing", "pause", "paused"):
        status = PrinterStatus({"status": state, "printFileName": "Synthetic model 🛠.3mf"})
        assert status.current_filename == "Synthetic model 🛠.3mf"
    assert PrinterStatus({"status": "ready", "printFileName": "Old.3mf"}).current_filename is None
    status = PrinterStatus({"cumulativePrintTime": 120, "remainingDiskSpace": 0})
    assert status.lifetime_print_hours == 2
    assert status.free_storage_gb == 0


@pytest.mark.parametrize("value", [None, -1, True, "5", float("nan"), float("inf"), 1e12])
def test_counter_validation(value):
    status = PrinterStatus({"cumulativePrintTime": value, "remainingDiskSpace": value})
    assert status.lifetime_print_hours is None
    assert status.free_storage_gb is None


class Content:
    def __init__(self, chunks):
        self.chunks = chunks

    async def iter_chunked(self, size):
        for chunk in self.chunks:
            yield chunk


class Response:
    def __init__(self, chunks, status=200):
        self.content = Content(chunks)
        self.status = status

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None


class Session:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


async def test_thumbnail_uses_only_fixed_host_without_credentials_or_redirects():
    data = b"\xff\xd8synthetic\xff\xd9"
    session = Session(Response([data[:4], data[4:]]))
    client = Creator5Client(cast(aiohttp.ClientSession, session), "10.0.0.42", "TEST", "secret")
    assert await client.get_current_thumbnail() == (data, "image/jpeg")
    assert len(session.calls) == 1
    url, options = session.calls[0]
    assert url == "http://10.0.0.42:8898/getThum"
    assert set(options) == {"timeout", "allow_redirects"}
    assert options["allow_redirects"] is False
    assert options["timeout"].total == 8


@pytest.mark.parametrize(
    "chunks,status",
    [
        ([b"<svg>secret</svg>"], 200),
        ([b""], 200),
        ([b"ignored"], 302),
        ([b"x" * (2 * 1024 * 1024 + 1)], 200),
    ],
)
async def test_thumbnail_rejects_redirects_unsupported_and_oversized_images(chunks, status):
    client = Creator5Client(
        cast(aiohttp.ClientSession, Session(Response(chunks, status))),
        "10.0.0.42",
        "TEST",
        "secret",
    )
    with pytest.raises(PrinterError) as error:
        await client.get_current_thumbnail()
    assert "secret" not in str(error.value)
