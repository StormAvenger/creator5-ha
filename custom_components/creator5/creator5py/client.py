"""Authenticated status and narrowly scoped, readback-verified LAN controls."""

import asyncio
import ipaddress
import math
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import aiohttp

from .palette import COLORS, MATERIALS


class PrinterError(Exception):
    """Safe error that never includes credentials or a response body."""


class AuthenticationError(PrinterError):
    """Printer rejected credentials or LAN mode is disabled."""


class ControlError(PrinterError):
    """Known failure stage without command arguments or printer identifiers."""

    def __init__(self, stage: str, message: str) -> None:
        super().__init__(message)
        self.stage = stage


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

    def station_number(self, key: str) -> int | None:
        """Uninterpreted station codes; slot zero means no reported slot."""
        station = self.detail.get("matlStationInfo")
        value = station.get(key) if isinstance(station, dict) else None
        maximum = 4 if key in ("currentSlot", "currentLoadSlot") else 65535
        return value if type(value) is int and 0 <= value <= maximum else None

    @property
    def lifetime_filament_m(self) -> float | None:
        return self.nonnegative("cumulativeFilament", maximum=1_000_000_000)

    @property
    def current_filename(self) -> str | None:
        """A bounded job name, never stale idle metadata or a filesystem path."""
        value = self.detail.get("printFileName")
        if self.state not in ("printing", "paused", "pause") or not isinstance(value, str):
            return None
        if (
            not value.strip()
            or len(value) > 255
            or any(ord(c) < 32 or ord(c) == 127 for c in value)
        ):
            return None
        if "/" in value or "\\" in value:
            return None
        return value

    @property
    def lifetime_print_hours(self) -> float | None:
        """Creator 5 community-observed minutes converted to hours."""
        minutes = self.nonnegative("cumulativePrintTime", maximum=100_000_000)
        return minutes / 60 if minutes is not None else None

    @property
    def free_storage_gb(self) -> float | None:
        """Creator 5 community-observed GB, without assuming a byte conversion."""
        return self.nonnegative("remainingDiskSpace", maximum=1_000_000)

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
        # Keep polling from overlapping a command and its readback. This also
        # prevents concurrent slot/delay edits from restoring stale values.
        self._operation_lock = asyncio.Lock()

    async def get_status(self) -> PrinterStatus:
        """Send one status request; never follow redirects or retry automatically."""
        async with self._operation_lock:
            return await self._get_status()

    async def _get_status(self) -> PrinterStatus:
        payload = await self._request("/detail", {})
        detail = payload.get("detail")
        if not isinstance(detail, dict) or not isinstance(detail.get("status"), str):
            raise PrinterError("Printer returned missing or invalid status detail")
        return PrinterStatus(detail)

    async def get_current_thumbnail(self) -> tuple[bytes, str]:
        """Read the fixed LAN current-job image, never a reported URL or camera."""
        maximum = 2 * 1024 * 1024
        try:
            async with self._session.get(
                self._url + "/getThum",
                timeout=self._timeout,
                allow_redirects=False,
            ) as response:
                if response.status != 200:
                    raise PrinterError("Printer thumbnail unavailable")
                data = bytearray()
                async for chunk in response.content.iter_chunked(65536):
                    if len(data) + len(chunk) > maximum:
                        raise PrinterError("Printer thumbnail exceeds size limit")
                    data.extend(chunk)
        except (TimeoutError, aiohttp.ClientError):
            raise PrinterError("Printer thumbnail request failed") from None
        content = bytes(data)
        if content.startswith(b"\x89PNG\r\n\x1a\n") and len(content) >= 33:
            content_type = "image/png"
        elif content.startswith(b"\xff\xd8") and content.endswith(b"\xff\xd9"):
            content_type = "image/jpeg"
        else:
            raise PrinterError("Printer thumbnail is not a supported image")
        return content, content_type

    async def set_light(self, on: bool) -> PrinterStatus:
        """Set only the chamber LED, then verify using one status read."""
        if type(on) is not bool:
            raise ValueError("Light state must be a boolean")
        async with self._operation_lock:
            await self._send_control("lightControl_cmd", {"status": "open" if on else "close"})
            status = await self._control_status()
            if status.open_state("lightStatus") is not on:
                raise ControlError("mismatch", "Printer did not confirm the requested light state")
            return status

    async def _send_control(self, command: str, args: dict[str, Any]) -> None:
        """Never retry writes or substitute speculative firmware commands."""
        try:
            await self._request("/control", {"payload": {"cmd": command, "args": args}})
        except AuthenticationError:
            raise
        except PrinterError as err:
            raise ControlError(
                "request",
                "Control request failed; its outcome is unconfirmed. "
                "Check the printer before retrying. " + str(err),
            ) from err

    async def _control_status(self) -> PrinterStatus:
        try:
            return await self._get_status()
        except AuthenticationError:
            raise
        except PrinterError as err:
            raise ControlError(
                "readback",
                "Control was acknowledged, but status verification failed. "
                "Its outcome is unconfirmed; check the printer before retrying. " + str(err),
            ) from err

    async def _verified_control(
        self,
        command: str,
        prepare: Callable[[PrinterStatus], dict[str, Any]],
        confirmed: Callable[[PrinterStatus], bool],
        states: tuple[str, ...],
        *,
        pro_only: bool = False,
    ) -> PrinterStatus:
        async with self._operation_lock:
            before = await self._get_status()
            if before.model is None or (pro_only and not before.is_pro):
                raise PrinterError("Control is unavailable for this printer model")
            if before.state not in states:
                raise PrinterError("Control is unavailable in the current printer state")
            await self._send_control(command, prepare(before))
            # Acknowledgements alone are not evidence. Allow bounded readback
            # latency, never resending the command, including after a timeout.
            for attempt in range(3):
                if attempt:
                    await asyncio.sleep(0.5)
                after = await self._control_status()
                if confirmed(after):
                    return after
            raise ControlError(
                "mismatch", "Printer did not confirm the requested change; check its display"
            )

    async def pause(self) -> PrinterStatus:
        return await self._verified_control(
            "jobCtl_cmd",
            lambda _: {"action": "pause", "jobID": ""},
            lambda s: s.state in ("paused", "pause"),
            ("printing",),
        )

    async def resume(self) -> PrinterStatus:
        return await self._verified_control(
            "jobCtl_cmd",
            lambda _: {"action": "continue", "jobID": ""},
            lambda s: s.state in ("printing", "heating"),
            ("paused", "pause"),
        )

    async def dismiss_completion(self) -> PrinterStatus:
        """Explicit acknowledgement only; never scheduled by this client."""
        return await self._verified_control(
            "stateCtrl_cmd",
            lambda _: {"action": "setClearPlatform"},
            lambda s: s.state == "ready",
            ("completed",),
        )

    async def set_speed(self, percent: float) -> PrinterStatus:
        self._integer_range(percent, 50, 150)
        return await self._verified_control(
            "printerCtl_cmd",
            lambda _: {"speed": int(percent)},
            lambda s: s.number("printSpeedAdjust") == percent,
            ("printing",),
        )

    async def set_temperature(self, heater: str, celsius: float) -> PrinterStatus:
        limits = {"bed": 120, "chamber": 65, **{f"tool_{i}": 320 for i in range(1, 5)}}
        if heater not in limits:
            raise ValueError("Unknown heater")
        self._integer_range(celsius, 0, limits[heater])
        args: dict[str, Any] = {
            "platform": -200,
            "chamber": -200,
            "nozzles": [-200] * 4,
        }
        if heater.startswith("tool_"):
            index = int(heater[-1]) - 1
            args["nozzles"][index] = int(celsius)
        else:
            key = "platform" if heater == "bed" else "chamber"
            args[key] = int(celsius) if celsius else -100
            field_name = "platTargetTemp" if heater == "bed" else "chamberTargetTemp"

        def check(status: PrinterStatus) -> bool:
            if heater.startswith("tool_"):
                return status.nozzle_temperature(index, target=True) == celsius
            return status.number(field_name) == celsius

        return await self._verified_control(
            "temperatureCtl_cmd",
            lambda _: args,
            check,
            ("ready", "printing", "paused", "pause"),
            pro_only=heater == "chamber",
        )

    async def set_auto_shutdown(
        self,
        *,
        enabled: bool | None = None,
        minutes: float | None = None,
    ) -> PrinterStatus:
        if enabled is not None and type(enabled) is not bool:
            raise ValueError("Shutdown state must be a boolean")
        if minutes is not None:
            self._integer_range(minutes, 1, 120)
        if enabled is None and minutes is None:
            raise ValueError("Specify shutdown state or delay")
        desired: dict[str, Any] = {}

        def prepare(status: PrinterStatus) -> dict[str, Any]:
            on = enabled if enabled is not None else status.open_state("autoShutdown")
            delay = minutes if minutes is not None else status.number("autoShutdownTime")
            if on is None or delay is None or not delay.is_integer() or not 1 <= delay <= 120:
                raise PrinterError("Set a supported shutdown delay before enabling auto shutdown")
            desired.update(on=on, delay=int(delay))
            return {"automaticShutdown": "open" if on else "close", "shutdownAfterTime": int(delay)}

        return await self._verified_control(
            "delayClose_cmd",
            prepare,
            lambda s: (
                s.open_state("autoShutdown") is desired["on"]
                and s.number("autoShutdownTime") == desired["delay"]
            ),
            ("ready",),
        )

    async def set_slot(
        self,
        slot: int,
        *,
        material: str | None = None,
        color: str | None = None,
    ) -> PrinterStatus:
        if type(slot) is not int or not 1 <= slot <= 4:
            raise ValueError("Material slot must be between 1 and 4")
        if material is not None and material not in MATERIALS:
            raise ValueError("Choose a documented Creator 5 material")
        if color is not None and color not in COLORS.values():
            raise ValueError("Choose an exact Creator 5 palette color")
        if material is None and color is None:
            raise ValueError("Specify material or color")
        desired: dict[str, str] = {}

        def prepare(status: PrinterStatus) -> dict[str, Any]:
            old = status.material_slot(slot)
            mt = material if material is not None else (old["material"] if old else None)
            rgb = color if color is not None else (old["color"] if old else None)
            if (
                not isinstance(mt, str)
                or not isinstance(rgb, str)
                or mt not in MATERIALS
                or rgb not in COLORS.values()
            ):
                raise PrinterError("Slot metadata is unsupported; set both fields at the printer")
            desired.update(material=mt, color=rgb)
            return {"slot": slot, "mt": mt, "rgb": rgb}

        def confirmed(status: PrinterStatus) -> bool:
            actual = status.material_slot(slot)
            return actual is not None and all(actual[k] == v for k, v in desired.items())

        return await self._verified_control("msConfig_cmd", prepare, confirmed, ("ready",))

    @staticmethod
    def _integer_range(value: float, minimum: int, maximum: int) -> None:
        if (
            type(value) not in (int, float)
            or not math.isfinite(value)
            or not minimum <= value <= maximum
            or int(value) != value
        ):
            raise ValueError(f"Value must be a whole number between {minimum} and {maximum}")

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
