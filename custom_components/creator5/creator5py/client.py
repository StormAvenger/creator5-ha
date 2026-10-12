"""Read-only HTTP transport. No command, upload, or arbitrary-endpoint API."""

import ipaddress
import math
from dataclasses import dataclass, field
from typing import Any

import aiohttp


class PrinterError(Exception):
    """Safe error that never includes credentials or a response body."""


class AuthenticationError(PrinterError):
    """Printer rejected credentials or LAN mode is disabled."""


def private_address(host: str) -> ipaddress.IPv4Address:
    """Validate a literal private target before any network operation."""
    try:
        address = ipaddress.IPv4Address(host)
    except ipaddress.AddressValueError:
        raise ValueError("Use the printer's private IPv4 address, without a URL or port") from None
    if not any(
        address in ipaddress.IPv4Network(network)
        for network in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
    ):
        raise ValueError("Printer address must be an RFC1918 private LAN IPv4 address")
    return address


@dataclass(frozen=True)
class PrinterStatus:
    """Unknown fields remain available locally; never log raw detail."""

    detail: dict[str, Any] = field(repr=False)

    def number(self, key: str) -> float | None:
        value = self.detail.get(key)
        if isinstance(value, bool) or not isinstance(value, (float, int)):
            return None
        return float(value) if math.isfinite(value) else None

    @property
    def state(self) -> str | None:
        value = self.detail.get("status")
        return value if isinstance(value, str) else None

    @property
    def progress_percent(self) -> float | None:
        value = self.number("printProgress")
        return value * 100 if value is not None and 0 <= value <= 1 else None


class Creator5Client:
    """Use an externally managed session and a specific private IPv4 address."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        serial: str,
        check_code: str,
        *,
        port: int = 8898,
        timeout: float = 8,
    ) -> None:
        address = private_address(host)
        if not serial.strip() or not check_code.strip():
            raise ValueError("Serial number and check code are required")
        if not 1 <= port <= 65535 or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("Invalid port or timeout")
        self._session = session
        self._url = f"http://{address}:{port}/detail"
        self._auth = {"serialNumber": serial.strip(), "checkCode": check_code.strip()}
        self._timeout = aiohttp.ClientTimeout(total=timeout)

    async def get_status(self) -> PrinterStatus:
        """Send one status request; never follow redirects or retry automatically."""
        try:
            async with self._session.post(
                self._url,
                json=self._auth,
                timeout=self._timeout,
                allow_redirects=False,
            ) as response:
                if response.status in (401, 403):
                    raise AuthenticationError("Printer rejected LAN authentication")
                if response.status != 200:
                    raise PrinterError(f"Printer returned HTTP {response.status}")
                # Creator firmware sometimes misspells application/json.
                payload = await response.json(content_type=None)
        except (TimeoutError, aiohttp.ClientError):
            raise PrinterError("Printer unreachable or request timed out") from None
        except (ValueError, UnicodeError):
            raise PrinterError("Printer returned invalid JSON") from None
        if not isinstance(payload, dict) or type(payload.get("code")) is not int:
            raise PrinterError("Printer returned an invalid response envelope")
        code = payload["code"]
        if code in (1, -2):
            raise AuthenticationError("Check serial number, check code, and LAN mode")
        if code != 0:
            raise PrinterError(f"Printer API returned error code {code}")
        detail = payload.get("detail")
        if not isinstance(detail, dict) or not isinstance(detail.get("status"), str):
            raise PrinterError("Printer returned missing or invalid status detail")
        return PrinterStatus(detail)
