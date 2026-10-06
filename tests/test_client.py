"""Protocol and credential-boundary tests use synthetic responses, never the LAN."""

from typing import cast

import aiohttp
import pytest
from creator5py import AuthenticationError, Creator5Client, PrinterError, PrinterStatus
from creator5py.cli import probe


class Response:
    def __init__(self, payload, status=200):
        self.payload, self.status = payload, status

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def json(self, *, content_type):
        assert content_type is None
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


class Session:
    def __init__(self, payload, status=200):
        self.response = Response(payload, status)
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


def client(session):
    return Creator5Client(cast(aiohttp.ClientSession, session), "10.0.0.42", "TEST-SN", "secret")


async def test_status_request_has_only_auth_and_never_follows_redirects():
    session = Session({"code": 0, "detail": {"status": "printing", "printProgress": 0.45}})
    result = await client(session).get_status()
    assert result.progress_percent == 45
    assert len(session.calls) == 1
    url, kwargs = session.calls[0]
    assert url == "http://10.0.0.42:8898/detail"
    assert kwargs["json"] == {"serialNumber": "TEST-SN", "checkCode": "secret"}
    assert kwargs["allow_redirects"] is False
    assert kwargs["timeout"].total == 8


@pytest.mark.parametrize(
    "host",
    [
        "8.8.8.8",
        "127.0.0.1",
        "169.254.1.2",
        "::1",
        "printer.local",
        "http://10.0.0.42",
        "10.0.0.42:8898",
    ],
)
def test_invalid_targets_are_rejected_before_network_access(host):
    with pytest.raises(ValueError):
        Creator5Client(cast(aiohttp.ClientSession, Session(None)), host, "TEST-SN", "secret")


@pytest.mark.parametrize("code", [1, -2])
async def test_auth_failure_does_not_echo_response(code):
    with pytest.raises(AuthenticationError) as error:
        await client(Session({"code": code, "message": "secret TEST-SN"})).get_status()
    assert "secret" not in str(error.value)
    assert "TEST-SN" not in str(error.value)


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {},
        {"code": False},
        {"code": "0"},
        {"code": 0},
        {"code": 0, "detail": []},
        {"code": 0, "detail": {}},
        ValueError("secret"),
    ],
)
async def test_malformed_responses_fail_safely(payload):
    with pytest.raises(PrinterError) as error:
        await client(Session(payload)).get_status()
    assert "secret" not in str(error.value)


@pytest.mark.parametrize("status", [301, 302, 500])
async def test_http_errors_and_redirects_are_not_retried(status):
    session = Session(None, status)
    with pytest.raises(PrinterError):
        await client(session).get_status()
    assert len(session.calls) == 1


async def test_timeout_is_safe():
    with pytest.raises(PrinterError, match="timed out"):
        await client(Session(TimeoutError())).get_status()


@pytest.mark.parametrize("value", [None, True, "42", float("nan"), float("inf")])
def test_absent_or_invalid_numbers_are_unknown(value):
    assert PrinterStatus({"platTemp": value}).number("platTemp") is None


def test_progress_range_and_raw_data_repr():
    status = PrinterStatus({"printProgress": 50, "checkCode": "secret"})
    assert status.progress_percent is None
    assert "secret" not in repr(status)


async def test_cli_output_excludes_identifiers_and_registration_codes(monkeypatch):
    async def fake_status(self):
        return PrinterStatus(
            {
                "status": "ready",
                "serialNumber": "PRIVATE",
                "checkCode": "secret",
                "flashRegisterCode": "secret",
                "cameraStreamUrl": "private-url",
                "printFileName": "private-file",
                "platTemp": 24,
            }
        )

    monkeypatch.setattr(Creator5Client, "get_status", fake_status)
    summary = await probe("10.0.0.42", "TEST-SN", "secret")
    assert summary["bed_c"] == 24
    assert "secret" not in str(summary)
    assert "private" not in str(summary).lower()
