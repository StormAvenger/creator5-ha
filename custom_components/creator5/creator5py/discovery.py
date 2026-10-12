"""One targeted read-only UDP query; no broadcast, multicast or subnet scan."""

import asyncio
import math
import socket
import struct
from dataclasses import dataclass, field

from .client import PrinterError, private_address


@dataclass(frozen=True)
class PrinterIdentity:
    """Do not expose the serial in logs or default representation."""

    serial: str = field(repr=False)
    product_id: int


def parse_identity(packet: bytes) -> PrinterIdentity:
    """Accept only the documented Creator 5 family on its HTTP port."""
    if len(packet) < 276:
        raise PrinterError("Truncated discovery response")
    vid, pid = struct.unpack_from("!HH", packet, 0x86)
    port = struct.unpack_from("!H", packet, 0x8E)[0]
    if vid != 0x2B71 or pid not in (40, 41) or port != 8898:
        raise PrinterError("Target does not identify as a supported Creator 5")
    try:
        serial = packet[0x92:0x112].split(b"\x00", 1)[0].decode("ascii")
    except UnicodeError:
        raise PrinterError("Invalid discovery serial") from None
    if not serial or not serial.isalnum():
        raise PrinterError("Invalid discovery serial")
    return PrinterIdentity(serial, pid)


def _discover(host: str, timeout: float) -> PrinterIdentity:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as connection:
            connection.settimeout(timeout)
            # Connected UDP filters replies to this peer; never enable SO_BROADCAST.
            connection.connect((host, 48899))
            connection.send(b"\x00")
            packet = connection.recv(1024)
    except OSError:
        raise PrinterError("Targeted discovery unavailable; supply serial locally") from None
    return parse_identity(packet)


async def discover_identity(host: str, *, timeout: float = 5) -> PrinterIdentity:
    """Send one packet only to the supplied private IPv4; never retry."""
    address = private_address(host)
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("Invalid discovery timeout")
    return await asyncio.to_thread(_discover, str(address), timeout)
