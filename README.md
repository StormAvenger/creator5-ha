# Creator 5 Home Assistant project

Experimental read-only FlashForge Creator 5 / Creator 5 Pro LAN integration.
This is an unofficial project and is not endorsed by FlashForge.
Built on macOS; the same Python package and commands work on Ubuntu.
No printer controls, uploads, heater changes, motion, or print-job controls are implemented.
One authenticated status read succeeded on a Creator 5 Pro during printing; its API
reports firmware `1.9.9`. The reported full build `1.9.9-1.3.0` and display
comparisons remain unverified. On 2026-10-14, the integration was added to
the owner's HA Core 2026.10.1: one device, 13 available sensors and scheduled
status refreshes during printing. See [live acceptance evidence](docs/live-acceptance.md).

Follow the [project completion guide](docs/project-guide.md) for the ordered plan,
current status, offline work and the next printer session. Development follows the
[scope and provenance rules](docs/legal-and-sources.md).
The user requires [no paid GitHub usage](docs/cost-policy.md). Repository Actions
are disabled; future tests and builds run locally.

## Start on macOS or Ubuntu

Use Python 3.12 or later. Create a fresh virtual environment on each machine:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/pytest
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy
```

The tests use synthetic responses and never contact a printer. Earlier GitHub CI
validated macOS/Ubuntu and Python 3.12/3.14; future checks run locally. The former
workflow is archived under docs/reference and Actions is disabled for the repository.

If `CREATOR5_SERIAL` is absent, the CLI retrieves it with one directed UDP discovery
packet to the supplied IP on port 48899. It validates the Creator 5 family and HTTP
port before sending the normal authenticated status request. No network scan,
broadcast or multicast is used. To skip discovery, supply the serial locally in `.env`.
An authentication rejection stops the probe; it never tries code variations.

## First read-only probe

Enable LAN mode on the printer. Have its private IPv4 address, serial number, and
LAN check code ready. The check code is distinct from the serial number.
Run in your own interactive terminal so the check code stays out of chat:

```sh
.venv/bin/creator5-probe
```

Enter the IP and serial when asked; the check code prompt is hidden. The client sends
one authenticated `POST /detail` on port 8898 with an eight-second total timeout.
The method is POST because that is how the printer exposes status reads.
No redirects, broadcast discovery, scans, retries or control requests are made.
Only a small allowlist of status values is printed; no raw payload is saved.
HTTP LAN credentials travel without encryption: use your trusted local network.

Optional: copy `.env.example` to `.env`, set host and serial there, and restrict
permissions with `chmod 600 .env`. Leave the check code empty to keep using the
hidden prompt. `.env` files, packet captures, logs, and local HA configuration are
ignored by Git. Do not enable HTTP body/debug logging or commit raw printer responses.

## Layout and packaging

```text
custom_components/creator5/
  creator5py/       # canonical standalone client; no Home Assistant imports
  config_flow.py   # local setup and check-code reauthentication
  sensor.py        # provisional state/progress/bed/chamber/remaining-time sensors
  manifest.json
tests/             # offline protocol and credential-boundary tests
docs/              # API evidence, deployment and next steps
docs/reference/   # archived workflow reference, never automatically executed
```

The wheel exports `creator5py` as a top-level Python package from this canonical
directory. Home Assistant imports the same code relatively. This avoids two copies
and an unpublished PyPI dependency during initial development. The client can later
be published separately and the integration switched to a pinned manifest requirement.
Build it using `.venv/bin/python -m build`; do not upload version 0.1.0 to PyPI yet.

## Home Assistant scaffold

See [installation and limitations](docs/home-assistant.md). Eleven runtime tests
exercise Home Assistant 2026.10.1 with synthetic printer data and external network
sockets disabled. The HA tests use Python 3.14 and a pinned framework; run them locally.
Validate it on a development HA instance after the live printer probe succeeds.
This is not HACS/release-ready.

## GitHub and moving to Ubuntu

The private project repository is [StormAvenger/creator5-ha](https://github.com/StormAvenger/creator5-ha),
with default branch `main`. The GitHub connector installation is limited to this
repository. The local `origin` points to that repository.

Commit source and synthetic fixtures only. On Ubuntu, clone the repository and repeat
the setup commands above. Recreate `.venv` and `.env`; never copy virtual environments
between operating systems. Supply credentials locally on the new machine. Keep CI
offline; the printer must be reached from a machine with access to its LAN.

See [API research](docs/api-research.md) for sources and firmware-specific assumptions.
