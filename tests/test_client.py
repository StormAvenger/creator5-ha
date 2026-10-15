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


def test_four_tool_readings_and_zero_targets_are_distinct():
    status = PrinterStatus({"nozzleTemps": [210, 31, 32, 33], "nozzleTargetTemps": [215, 0, 0, 0]})
    assert [status.nozzle_temperature(i) for i in range(4)] == [210, 31, 32, 33]
    assert [status.nozzle_temperature(i, target=True) for i in range(4)] == [215, 0, 0, 0]


@pytest.mark.parametrize("values", [None, "210", [], [210], [210, 30, 31, 32, 33]])
def test_invalid_tool_array_remains_unknown(values):
    assert PrinterStatus({"nozzleTemps": values}).nozzle_temperature(0) is None


@pytest.mark.parametrize("value", [True, "210", None, -108, float("nan"), float("inf")])
def test_invalid_tool_value_does_not_poison_other_tools(value):
    status = PrinterStatus({"nozzleTemps": [value, 31, 32, 33]})
    assert status.nozzle_temperature(0) is None
    assert status.nozzle_temperature(1) == 31


@pytest.mark.parametrize("index", [-1, 4, True])
def test_invalid_tool_index_is_rejected(index):
    with pytest.raises(ValueError):
        PrinterStatus({}).nozzle_temperature(index)


@pytest.mark.parametrize(
    "value,expected",
    [("open", True), ("close", False), ("opened", None), (True, None), (None, None)],
)
def test_open_close_fields_are_strict(value, expected):
    assert PrinterStatus({"doorStatus": value}).open_state("doorStatus") is expected


def test_material_slots_are_selected_by_id_and_sanitized():
    status = PrinterStatus(
        {
            "matlStationInfo": {
                "slotInfos": [
                    {
                        "slotId": 4,
                        "materialName": "TPU",
                        "materialColor": "#ABCDEF",
                        "hasFilament": False,
                        "token": "PRIVATE",
                    },
                    {"slotId": 1, "materialName": "PETG", "materialColor": "bad", "hasFilament": 1},
                ]
            }
        }
    )
    assert status.material_slot(4) == {"material": "TPU", "color": "#ABCDEF", "has_filament": False}
    assert status.material_slot(1) == {"material": "PETG", "color": None, "has_filament": None}
    assert status.material_slot(2) is None
    assert "PRIVATE" not in str(status.material_slot(4))


@pytest.mark.parametrize(
    "slots",
    [None, "invalid", [None], [{"slotId": True}], [{"slotId": 1}, {"slotId": 1}], [{"slotId": 5}]],
)
def test_bad_material_station_is_unknown(slots):
    assert PrinterStatus({"matlStationInfo": {"slotInfos": slots}}).material_slot(1) is None


@pytest.mark.parametrize("value", [-108, True, "42", float("nan"), float("inf"), 101])
def test_fan_percentages_reject_invalid_and_sentinel_values(value):
    assert (
        PrinterStatus({"chamberFanSpeed": value}).nonnegative("chamberFanSpeed", maximum=100)
        is None
    )


class SequenceSession(Session):
    def __init__(self, payloads):
        self.responses = iter(Response(payload) for payload in payloads)
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return next(self.responses)


@pytest.mark.parametrize("on", [True, False])
async def test_light_has_only_the_documented_led_payload_and_verifies_readback(on):
    session = SequenceSession(
        [
            {"code": 0},
            {"code": 0, "detail": {"status": "printing", "lightStatus": "open" if on else "close"}},
        ]
    )
    result = await client(session).set_light(on)
    assert result.state == "printing"
    assert result.open_state("lightStatus") is on
    assert len(session.calls) == 2
    url, kwargs = session.calls[0]
    assert url == "http://10.0.0.42:8898/control"
    assert kwargs["json"] == {
        "serialNumber": "TEST-SN",
        "checkCode": "secret",
        "payload": {"cmd": "lightControl_cmd", "args": {"status": "open" if on else "close"}},
    }
    assert all(call[1]["allow_redirects"] is False for call in session.calls)
    assert session.calls[1][0].endswith("/detail")
    assert session.calls[1][1]["json"] == {"serialNumber": "TEST-SN", "checkCode": "secret"}


@pytest.mark.parametrize("reported", ["close", "unknown", None])
async def test_light_success_ack_without_matching_state_is_a_failure(reported):
    session = SequenceSession(
        [
            {"code": 0},
            {"code": 0, "detail": {"status": "printing", "lightStatus": reported}},
        ]
    )
    with pytest.raises(PrinterError, match="did not confirm"):
        await client(session).set_light(True)
    assert len(session.calls) == 2


async def test_invalid_light_input_never_sends_a_command():
    session = Session(None)
    with pytest.raises(ValueError):
        await client(session).set_light("open")
    assert not session.calls


async def test_light_authentication_failure_is_not_retried_or_echoed():
    session = Session({"code": 1, "message": "secret TEST-SN"})
    with pytest.raises(AuthenticationError) as error:
        await client(session).set_light(True)
    assert "secret" not in str(error.value)
    assert len(session.calls) == 1


@pytest.mark.parametrize(
    "value,expected",
    [
        ("0.6mm;0.4mm;0.4mm;0.4mm", [0.6, 0.4, 0.4, 0.4]),
        ("0.4mm", None),
        ("secret", None),
        (None, None),
        ("0mm;0.4mm;0.4mm;0.4mm", None),
        ("9mm;0.4mm;0.4mm;0.4mm", None),
    ],
)
def test_reported_nozzle_diameters_have_exactly_four_bounded_values(value, expected):
    result = [PrinterStatus({"nozzleModel": value}).nozzle_diameter(i) for i in range(4)]
    assert result == (expected if expected else [None] * 4)


@pytest.mark.parametrize(
    "value,expected",
    [
        ("", "none"),
        ("E0162", "E0162"),
        ("E9999", "E9999"),
        ("arbitrary secret", None),
        (123, None),
        (None, None),
    ],
)
def test_error_codes_are_format_validated_without_invented_descriptions(value, expected):
    assert PrinterStatus({"errorCode": value}).error_code == expected


@pytest.mark.parametrize(
    "value,expected",
    [("1.9.9", "1.9.9"), ("1.9.9-1.3.0", "1.9.9-1.3.0"), ("private-url", None), ([], None)],
)
def test_firmware_text_is_bounded_and_validated(value, expected):
    assert PrinterStatus({"firmwareVersion": value}).firmware_version == expected
