"""One-shot status probe with a hidden credential prompt."""

import argparse
import asyncio
import getpass
import json
import os
from pathlib import Path

import aiohttp
from dotenv import load_dotenv

from .client import Creator5Client, PrinterError
from .discovery import discover_identity


async def probe(host: str, serial: str | None, code: str) -> dict[str, object]:
    if not serial:
        serial = (await discover_identity(host)).serial
    async with aiohttp.ClientSession(trust_env=False) as session:
        status = await Creator5Client(session, host, serial, code).get_status()
    # Allowlist: omit identifiers, filenames, registration codes, URLs and raw errors.
    return {
        "state": status.state,
        "progress_percent": status.progress_percent,
        "bed_c": status.number("platTemp"),
        "chamber_c": status.number("chamberTemp"),
        "remaining_seconds": status.number("estimatedTime"),
        "tool_temperatures_c": [status.nozzle_temperature(i) for i in range(4)],
        "tool_targets_c": [status.nozzle_temperature(i, target=True) for i in range(4)],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Read status once: targeted discovery if serial is absent, then POST /detail"
    )
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    args = parser.parse_args()
    load_dotenv(args.env_file, override=False)
    host = os.getenv("CREATOR5_HOST") or input("Printer LAN IPv4: ").strip()
    serial = os.getenv("CREATOR5_SERIAL")
    code = os.getenv("CREATOR5_CHECK_CODE") or getpass.getpass("LAN check code (hidden): ")
    try:
        print(json.dumps(asyncio.run(probe(host, serial, code)), indent=2))
    except (ValueError, PrinterError) as err:
        parser.exit(1, f"Probe failed: {err}\n")


if __name__ == "__main__":
    main()
