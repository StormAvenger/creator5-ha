"""Synthetic identity packets; no real socket or printer requests."""

import struct

import pytest
from creator5py import PrinterError
from creator5py.cli import probe
from creator5py.discovery import PrinterIdentity, discover_identity, parse_identity


def packet(*, vid=0x2B71, pid=41, port=8898, serial=b"SYNTHETICSERIAL"):
    data = bytearray(276)
    struct.pack_into("!HH", data, 0x86, vid, pid)
    struct.pack_into("!H", data, 0x8E, port)
    data[0x92 : 0x92 + len(serial)] = serial
    return bytes(data)


@pytest.mark.parametrize("pid", [40, 41])
def test_identity_parsing_and_repr_privacy(pid):
    result = parse_identity(packet(pid=pid))
    assert result.serial == "SYNTHETICSERIAL"
    assert result.product_id == pid
    assert "SYNTHETICSERIAL" not in repr(result)


@pytest.mark.parametrize(
    "data",
    [
        b"short",
        packet(vid=0),
        packet(pid=38),
        packet(port=8899),
        packet(serial=b""),
        packet(serial=b"\xff"),
        packet(serial=b"PRIVATE-INVALID"),
    ],
)
def test_reject_wrong_family_or_invalid_identity(data):
    with pytest.raises(PrinterError) as error:
        parse_identity(data)
    assert "PRIVATE" not in str(error.value)


async def test_only_one_targeted_packet_and_no_broadcast(monkeypatch):
    calls = []

    class Socket:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def settimeout(self, timeout):
            calls.append(("timeout", timeout))

        def connect(self, target):
            calls.append(("connect", target))

        def send(self, payload):
            calls.append(("send", payload))

        def recv(self, limit):
            calls.append(("recv", limit))
            return packet()

    monkeypatch.setattr("creator5py.discovery.socket.socket", lambda *args: Socket())
    result = await discover_identity("10.0.0.42")
    assert result.product_id == 41
    assert calls == [
        ("timeout", 5),
        ("connect", ("10.0.0.42", 48899)),
        ("send", b"\x00"),
        ("recv", 1024),
    ]


async def test_invalid_target_never_opens_socket(monkeypatch):
    def unexpected(*args):
        pytest.fail("Socket opened for invalid target")

    monkeypatch.setattr("creator5py.discovery.socket.socket", unexpected)
    with pytest.raises(ValueError):
        await discover_identity("255.255.255.255")


async def test_discovery_failure_does_not_attempt_authentication(monkeypatch):
    async def unavailable(host):
        raise PrinterError("Targeted discovery unavailable")

    monkeypatch.setattr("creator5py.cli.discover_identity", unavailable)
    with pytest.raises(PrinterError, match="discovery unavailable"):
        await probe("10.0.0.42", None, "SYNTHETIC-CODE")


async def test_discovered_serial_passed_to_status_client(monkeypatch):
    from creator5py import PrinterStatus

    async def discovered(host):
        return PrinterIdentity("SYNTHETICSERIAL", 41)

    async def status(self):
        assert self._auth["serialNumber"] == "SYNTHETICSERIAL"
        return PrinterStatus({"status": "printing"})

    monkeypatch.setattr("creator5py.cli.discover_identity", discovered)
    monkeypatch.setattr("creator5py.cli.Creator5Client.get_status", status)
    assert (await probe("10.0.0.42", None, "SYNTHETIC-CODE"))["state"] == "printing"
