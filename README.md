# ⚠️ EXPERIMENTAL — USE AT YOUR OWN RISK

# FlashForge Creator 5 for Home Assistant

An unofficial LAN integration for monitoring a FlashForge Creator 5 printer in
Home Assistant, with an on-demand camera and optional, verified printer controls.

**Only the Creator 5 Pro has been tested on real hardware.** The standard Creator 5
is detected by the integration, but its behavior has not been verified on a
physical printer. Compatibility is not guaranteed.

I'm currently running this integration on my own Creator 5 Pro, and it is working
well for monitoring in my setup. Light control currently times out on firmware
2.0.0; see the compatibility note below. It was developed quickly with substantial AI assistance
("vibe-coded"), so expect rough edges and bugs. It is experimental software,
provided without warranty. Feedback, testing reports, code reviews and contributions
are very welcome. This project is not affiliated with or endorsed by FlashForge.

## Features

- Printer state, current filename, progress, layers, elapsed/remaining time and estimated finish time.
- On-demand current-model thumbnail and reported lifetime printing time/free storage.
- Bed and tool temperatures and targets, defaulting to Celsius for this device.
- Four material slots with material names, filament presence and color swatches.
- Reported nozzle diameters and optional manual tool-to-slot assignments and notes.
- Pro-specific chamber readings and door/lid status.
- Reported fan readings, firmware/model information, error codes and connection health.
- On-demand camera viewing through Home Assistant.
- Chamber-light on/off control (firmware 2.0.0 regression under investigation).
- Reported lifetime filament, speed multiplier, Z offset, auto-shutdown and material-station activity.
- Optional pause/resume, completion acknowledgement, slot metadata editing, auto-shutdown, speed and temperature-target controls.
- On-demand recent-file browser and previews; optional upload-only, reprint and confirmed cancellation.
- Guided native dashboard and optional notification setup, with an optional sidebar shortcut.
- Persisted last-print summary and a configurable bed-cooled indicator.
- User-set maintenance reminders and selected vendor-verified error explanations.
- Shared status polling every 10 seconds by default, configurable from 5–300 seconds.

New control groups are **off by default** and enabled individually in Configure.
Completion acknowledgement only runs when its button is pressed or called by your
own automation. Slot edits change metadata, not filament loading. Material
assignments remain manual; the integration does not detect which slot feeds each tool.
See [controls, limits and validation status](docs/controls.md).

## Requirements and tested setup

| Item | Requirement / evidence |
| --- | --- |
| Home Assistant | Minimum 2026.10.1; tested with 2026.10.1 |
| Printer | Creator 5 Pro in LAN mode |
| Firmware | Prior LAN/light tests: 1.9.9. Monitoring observed on 2.0.0; light requests time out. New controls need hardware validation |
| Standard Creator 5 | Experimental detection and synthetic tests only; no hardware validation |
| HACS | Installed and connected to GitHub |
| Network | HA must reach the printer: UDP 48899, TCP 8898, and TCP 8080 for camera viewing |

Use a trusted local network: the stock printer LAN API uses unencrypted HTTP.
Remote access to Home Assistant does not itself establish a route from HA to the printer.

## Installation

### 1. Download through HACS

1. Open **HACS → ⋮ → Custom repositories**.
2. Enter `https://github.com/StormAvenger/creator5-ha`.
3. Select **Integration**, then add the repository.
4. Open **Creator 5 LAN (experimental)** and select **Download**.
5. Restart Home Assistant.

This project is a HACS custom repository; it is not included in the default HACS catalog.

### 2. Connect the printer

1. Enable LAN mode on the printer and obtain its IP address and LAN check code.
2. In HA, open **Settings → Devices & services → Add integration**.
3. Search for **Creator 5** and select **FlashForge Creator 5 (experimental)**.
4. Enter the printer IP and case-sensitive LAN check code, then select **Submit**.
5. Finish the device setup. HA identifies the serial and model automatically.

Setup checks only the entered address. It does not scan the network or send printer
control commands. Unsupported or conflicting model identification stops setup.

### 3. Optional settings

Open the integration's **Configure** form to adjust the polling interval, enable
camera viewing, cooling/alert thresholds and maintenance intervals, assign tools to
material slots and enter material notes. Update
manual assignments when you change the physical setup. Optional control groups can
be enabled here too; saving options sends no printer commands.

The separate last-success timestamp entity is disabled by default to avoid noisy
Activity entries. Current/total layers and progress are continuous measurements,
so they retain history without a stream of Activity entries. Connection health remains available.

## Files, dashboard and notifications

As an administrator, open **Settings → Devices & services → Creator 5 → Configure**
and follow **Creator 5 tools**. The tools page remains accessible with its sidebar
shortcut off (the default). Enable **Show Creator 5 tools in the sidebar** if wanted.

Choose **Refresh files** for the printer's recent-file list and **Show preview** for
a selected thumbnail. Enable **file uploads, reprints and cancellation** separately
in Configure to use those actions. Each requires confirmation. Uploads use a unique
filename, accept trusted sliced `.3mf`/`.gcode` files up to 64 MiB, and never start
a print. Reprinting requires a clear bed and the correct slicer-numbered material
slots; previous custom mappings and HA tool notes are not applied. See the
[file tools guide and limitations](docs/files.md). These new actions are not yet
hardware-validated.

On the tools page, select your printer
and click **Create dashboard** for a separate, editable native dashboard with grouped
material slots, camera, print information and enabled controls. Existing dashboards
are never replaced. A checkbox chooses whether the new dashboard appears in the
sidebar; it defaults to off and does not change existing dashboards.

On the same page, choose a phone or Home Assistant notifications, select events
and click **Create alerts**. This creates a native automation you can edit or disable.
No alerts are installed automatically, and filenames are excluded from messages.

See [setup, print summaries, cooling and maintenance](docs/usability.md). The older
manual dashboard examples remain available:

- [Full dashboard example](dashboards/creator5.yaml)
- [Material-slot card example](dashboards/material-slots.yaml)
- [Dashboard setup and entity details](docs/slot-display.md)

A separate [job-information card example](dashboards/job-overview.yaml) displays
the current model preview, filename, finish estimate and usage/storage readings.
See [job-monitoring limitations and privacy](docs/job-monitoring.md).

Configure tool-to-slot assignments first. Adjust the examples' entity IDs if your
HA device has a different name. Dashboard examples are not automatically installed
or replaced by HACS updates.

## Updates and removal

HACS checks GitHub periodically and offers available updates. Install the desired
release, then restart Home Assistant to load the updated integration. Existing
printer configuration and options are retained; automatic installation requires
separate user configuration.

To remove the integration, delete its printer entry under **Devices & services**,
then remove the repository through HACS and follow its restart instructions.

## Troubleshooting

| Problem | Check |
| --- | --- |
| Could not identify printer | Correct IP, LAN mode and UDP 48899 access from HA |
| Invalid LAN code | Exact capitalization; use the LAN code, not the serial number |
| Cannot read status | Printer powered on and reachable from HA on TCP 8898 |
| Model mismatch | Report model and firmware; setup deliberately stops rather than guessing |
| No camera picture | Camera viewing enabled and TCP 8080 reachable |
| Light times out on firmware 2.0.0 | Known owner-reported regression despite working status polling; no verified workaround yet. Do not repeatedly retry commands |
| Optional control unavailable | Enable its group in Configure and check the allowed printer states in the controls guide |
| Tool material is unknown | Assign that tool to a material slot in Configure |

See the [installation guide](docs/install.md) for more detail.

## Feedback and contributions

Please [open an issue](https://github.com/StormAvenger/creator5-ha/issues) for bugs,
feature suggestions or testing reports. Include the integration version, HA version,
printer model, firmware and steps to reproduce the problem. Reports from standard
Creator 5 owners would be especially useful.

Do not post LAN codes, serial numbers, IP/MAC addresses, private camera URLs, raw
printer responses or unreviewed diagnostics. Integration diagnostics omit printer
credentials and identifiers, but review the entire file before sharing it.

Useful future work includes broader firmware/base-model testing, more verified error
meanings and investigating camera reconnect behavior. Hardware test reports are welcome.

## Development and validation

The standalone `creator5py` client lives inside `custom_components/creator5/creator5py`
and is also packaged as an independent Python library. It has no HA dependency.
Use Python 3.12 or newer for client development, with a fresh virtual environment
on macOS or Ubuntu:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m pytest tests --ignore=tests/ha
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy
node tests/frontend/test_setup.mjs
```

HA runtime tests use a separate Python 3.14 environment pinned to HA 2026.10.1.
Version 0.6.0 passes 252 client tests, 106 HA tests and 24 frontend workflow checks.
See [validation and physical-test limitations](docs/releases/0.6.0.md). Earlier
public HACS download and fresh authenticated Pro setup were also verified. This does not establish compatibility with every printer or HA version.
Tests use synthetic data and do not contact a printer. Tests and builds run locally;
repository Actions remains disabled.

See [validation evidence](docs/hacs-candidate.md), [API research](docs/api-research.md),
[development scope and sources](docs/legal-and-sources.md), and the
[project guide](docs/project-guide.md).

## License

Copyright (C) 2026 StormAvenger. Licensed under the
[GNU General Public License, version 3 only](LICENSE) (`GPL-3.0-only`), without
warranty. Third-party dependencies retain their own licenses.
