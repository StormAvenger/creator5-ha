# Creator 5 Home Assistant project

Experimental FlashForge Creator 5 / Creator 5 Pro LAN monitoring and chamber light.
This is an unofficial project and is not endorsed by FlashForge.
Built on macOS; the same Python package and commands work on Ubuntu.
The current development candidate is 0.3.2: HACS packaging and a two-field setup
form (printer IP and LAN code), with automatic serial/model identification.
Creator 5 Pro on API firmware 1.9.9 is live-tested; base Creator 5 support is
experimental and not hardware-tested. Pro-only door/lid and chamber readings are
omitted for the base model. Version 0.3.2 is live on the owner-authorized HA host, with the two-field form
and duplicate protection verified. Monitoring and the slot dashboard are preserved.

## Install in Home Assistant — no YAML configuration

With HACS already installed:

1. In HACS, open **⋮ → Custom repositories**, add this repository's URL and choose
   **Integration**. Download **Creator 5 LAN (experimental)**.
2. Restart Home Assistant.
3. Open **Settings → Devices & services → Add integration** and search **Creator 5**.
4. Enter the printer's **IP address** and **LAN code**, then select **Submit**.
5. HA identifies the serial and model and adds the device, sensors, camera and light.

No serial entry, terminal or YAML file is needed for normal integration setup.
Setup sends one identification packet only to the entered address, then checks
normal authenticated status; it never scans the network. Only chamber-light control
is provided. Optional material/tool assignments are edited in HA's Configure form.
See [the installation guide](docs/install.md) for prerequisites and troubleshooting.

**Distribution:** install this repository through HACS custom repositories.
It is not listed in the default HACS catalog. Version 0.3.2 is the first public
candidate; public HACS download and fresh authenticated setup passed.
The grouped slot dashboard is an optional separate example; HACS does not install
that dashboard automatically. See [slot presentation](docs/slot-display.md).

The integration implements only chamber-light on/off control; no uploads, heater changes,
fan controls, motion or print-job controls are implemented. All twelve temperatures default to Celsius for this device.
See [extended monitoring and Celsius](docs/extended-monitoring.md).
One authenticated status read succeeded on a Creator 5 Pro during printing; its API
reports firmware `1.9.9`. The reported full build `1.9.9-1.3.0` and display
comparisons remain unverified. On 2026-10-14, the integration was added to
the owner's HA Core 2026.10.1: scheduled reads during printing, natural completion
and idle were observed. The later 0.2.0 upgrade exposes 30 entities and its LED
off/on command was verified through status readback, restoring the original on state. See [live acceptance evidence](docs/live-acceptance.md).

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
Build it using `.venv/bin/python -m build`; do not upload development packages to PyPI yet.

## Home Assistant integration

See [installation and limitations](docs/home-assistant.md). Runtime tests
exercise Home Assistant 2026.10.1 with synthetic printer data and external network
sockets disabled. The HA tests use Python 3.14 and a pinned framework; run them locally.
Validate it on a development HA instance after the live printer probe succeeds.
Public HACS custom-repository download and fresh two-field authenticated setup
passed on HA 2026.10.1. See [acceptance evidence](docs/hacs-candidate.md).

## GitHub and moving to Ubuntu

The project repository is [StormAvenger/creator5-ha](https://github.com/StormAvenger/creator5-ha),
with default branch `main`. The GitHub connector installation is limited to this
repository. The local `origin` points to that repository.

Commit source and synthetic fixtures only. On Ubuntu, clone the repository and repeat
the setup commands above. Recreate `.venv` and `.env`; never copy virtual environments
between operating systems. Supply credentials locally on the new machine. Keep CI
offline; the printer must be reached from a machine with access to its LAN.

See [API research](docs/api-research.md) for sources and firmware-specific assumptions.

## License

Copyright (C) 2026 StormAvenger. This project is licensed under the
[GNU General Public License, version 3 only](LICENSE) (`GPL-3.0-only`).
You may redistribute and modify it under those terms. It is provided without
warranty; see the license for the full terms. Third-party dependencies retain
their own licenses.
