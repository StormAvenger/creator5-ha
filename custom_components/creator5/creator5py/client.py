"""Status reads and one narrowly scoped chamber-light command."""

import ipaddress
import math
import re
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

    def nonnegative(self, key: str, *, maximum: float | None = None) -> float | None:
        value = self.number(key)
        return (
            value
            if value is not None and 0 <= value and (maximum is None or value <= maximum)
            else None
        )

    def open_state(self, key: str) -> bool | None:
        value = self.detail.get(key)
        return {"open": True, "close": False}.get(value) if isinstance(value, str) else None

    @property
    def is_pro(self) -> bool:
        return self.detail.get("model") == "Creator 5 Pro"

    def material_slot(self, slot: int) -> dict[str, Any] | None:
        """Return only validated slot metadata, never the raw station object."""
        if type(slot) is not int or not 1 <= slot <= 4:
            raise ValueError("Material slot must be between 1 and 4")
        station = self.detail.get("matlStationInfo")
        slots = station.get("slotInfos") if isinstance(station, dict) else None
        if not isinstance(slots, list) or len(slots) > 4:
            return None
        seen = set()
        selected = None
        for item in slots:
            if not isinstance(item, dict):
                return None
            slot_id = item.get("slotId")
            if type(slot_id) is not int or not 1 <= slot_id <= 4 or slot_id in seen:
                return None
            seen.add(slot_id)
            if slot_id == slot:
                selected = item
        if selected is None:
            return None
        material, color, present = (
            selected.get(k) for k in ("materialName", "materialColor", "hasFilament")
        )
        return {
            "material": material
            if isinstance(material, str) and re.fullmatch(r"[A-Za-z0-9 +_.-]{1,32}", material)
            else None,
            "color": color
            if isinstance(color, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", color)
            else None,
            "has_filament": present if type(present) is bool else None,
        }

    @property
    def state(self) -> str | None:
        value = self.detail.get("status")
        return value if isinstance(value, str) else None

    @property
    def progress_percent(self) -> float | None:
        value = self.number("printProgress")
        return value * 100 if value is not None and 0 <= value <= 1 else None

    @property
    def model(self) -> str | None:
        value = self.detail.get("model")
        return value if value in ("Creator 5", "Creator 5 Pro") else None

    @property
    def firmware_version(self) -> str | None:
        value = self.detail.get("firmwareVersion")
        if (
            isinstance(value, str)
            and len(value) <= 32
            and re.fullmatch(r"v?\d+(?:\.\d+){1,3}(?:-[A-Za-z0-9.]+)?", value)
        ):
            return value
        return None

    @property
    def error_code(self) -> str | None:
        value = self.detail.get("errorCode")
        if value == "":
            return "none"
        return value if isinstance(value, str) and re.fullmatch(r"E[0-9]{4}", value) else None

    def nozzle_diameter(self, index: int) -> float | None:
        """Parse the reported ordered diameters; never infer the physical tool mapping."""
        if type(index) is not int or not 0 <= index < 4:
            raise ValueError("Tool index must be between 0 and 3")
        value = self.detail.get("nozzleModel")
        if (
            not isinstance(value, str)
            or len(value) > 128
            or not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?mm(?:;[0-9]+(?:\.[0-9]+)?mm){3}", value)
        ):
            return None
        values = [float(part[:-2]) for part in value.split(";")]
        return values[index] if all(0 < number <= 5 for number in values) else None

    def nozzle_temperature(self, index: int, *, target: bool = False) -> float | None:
        """Read one of four ordered tools; reject malformed arrays and values."""
        if isinstance(index, bool) or not 0 <= index < 4:
            raise ValueError("Tool index must be between 0 and 3")
        values = self.detail.get("nozzleTargetTemps" if target else "nozzleTemps")
        if not isinstance(values, list) or len(values) != 4:
            return None
        value = values[index]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        return float(value) if math.isfinite(value) and value >= 0 else None


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
        self._url = f"http://{address}:{port}"
        self._auth = {"serialNumber": serial.strip(), "checkCode": check_code.strip()}
        self._timeout = aiohttp.ClientTimeout(total=timeout)

    async def get_status(self) -> PrinterStatus:
        """Send one status request; never follow redirects or retry automatically."""
        payload = await self._request("/detail", {})
        detail = payload.get("detail")
        if not isinstance(detail, dict) or not isinstance(detail.get("status"), str):
            raise PrinterError("Printer returned missing or invalid status detail")
        return PrinterStatus(detail)

    async def set_light(self, on: bool) -> PrinterStatus:
        """Set only the chamber LED, then verify using one status read."""
        if type(on) is not bool:
            raise ValueError("Light state must be a boolean")
        await self._request(
            "/control",
            {"payload": {"cmd": "lightControl_cmd", "args": {"status": "open" if on else "close"}}},
        )
        status = await self.get_status()
        if status.open_state("lightStatus") is not on:
            raise PrinterError("Printer did not confirm the requested light state")
        return status

    async def _request(self, endpoint: str, body: dict[str, Any]) -> dict[str, Any]:
        try:
            async with self._session.post(
                self._url + endpoint,
                json={**self._auth, **body},
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
        return payload
