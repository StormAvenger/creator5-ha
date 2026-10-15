# Project completion guide

**Goal:** an unofficial, local Home Assistant integration for the user's stock
Creator 5 Pro, backed by a portable standalone Python client. Initial milestone:
read-only monitoring. The owner has now requested extra sensors and light-only control. macOS development, Ubuntu deployment, GitHub for source and review.

This guide carries forward the project and legal boundaries from **TPU Jams
Troubleshooting**. It is the ordered checklist we update as work progresses.
Last reviewed: 2026-10-14. The user has resumed local LAN access and the printer
is printing. Do not interrupt or alter the print. Reported stock firmware: `1.9.9-1.3.0`.
The standalone probe has no automatic retry. The owner has authorized HA status
polling; the active coordinator uses one shared request every 30 seconds.
The Mac's TCP-only API-port check succeeds. Targeted discovery identified the
Creator 5 Pro and supplied its serial privately. After the owner corrected the
code capitalization, one authenticated status read succeeded during printing.
The API reports firmware 1.9.9; its full build suffix and display comparisons
remain unverified. No printer controls have been sent. The 16 component files are
installed and active in HA Core 2026.10.1, with one device and 30 available entities.
Scheduled updates were observed while the printer continued reporting printing.

## Working boundaries

**Cost:** no paid GitHub usage. Actions is disabled; run checks locally. Student
benefits may be considered only once active and verified free with no-overage
controls. See [cost policy](cost-policy.md). Past CI success is historical evidence;
new workflow runs are not part of the current plan.

Use normal LAN mode and the owner's credentials. Write our own implementation
from documented protocol behavior and observations of the owner's equipment.
Keep testing offline until a route to the printer is verified. Remote access uses
the same normal LAN API and credentials. See [legal and source notes](legal-and-sources.md).

Work remains limited to the normal LAN API. Proprietary-code decompilation,
firmware extraction/modification, rooting, signing/authentication bypasses and
cloud endpoint experimentation are outside this plan. If a feature needs those,
record it as unavailable rather than adding a bypass. Packet capture, if needed,
must be narrowly scoped to the owner's printer and consenting computers; keep
raw captures private and out of Git. Use synthetic examples in tests.

## Ordered milestones

### 1. Establish the project — complete

- [x] Private GitHub repository and restricted connector access.
- [x] Standalone async Python package and HA custom integration scaffold.
- [x] Ignore credentials, captures, logs, and local HA configuration.
- [x] One-shot, read-only status probe with a hidden check-code prompt.
- [x] Tests, lint, typing, package builds, macOS/Ubuntu CI on Python 3.12/3.14.

**Complete when:** clean checkout installs and tests without any printer secrets.
Evidence: initial four CI jobs passed on GitHub.

### 2. Record scope and provenance — current offline work

- [x] Recover the earlier chat's project/legal constraints.
- [x] Recheck the statute and published FlashForge terms; record limitations.
- [x] Identify independent code and reference-only community sources.
- [ ] Identify the terms included with the user's actual firmware/Flash Studio installation.
- [x] Choose an outbound license with the owner: GPL-3.0-only.

**Complete when:** development scope and source provenance are documented; any
reuse has its license and required notices. No blanket legal clearance is claimed.
Exact installed terms and public-license choice remain release gates, not blockers
for original offline code and synthetic tests.

### 3. Validate Home Assistant without the printer — complete

- [x] Use a pinned HA test framework and document the exact HA baseline.
- [x] Test setup validation, duplicates, invalid inputs and rejected credentials.
- [x] Test config-entry setup, sensor values and periodic coordinator refreshes.
- [x] Test missing fields, lost connectivity and recovery.
- [x] Test changed credentials/reauthentication and platform unload.
- [x] Add cached, allowlisted diagnostics; prove no extra requests or secret export.
- [x] Add four tool temperatures and targets, with malformed/missing-field tests.
- [x] Add a separate Linux CI job for actual HA runtime tests.
- [x] Confirm the new HA job passes on GitHub.

**Complete when:** the tests exercise real HA classes with synthetic status data,
no printer/network credentials, and CI passes. Mocks prove integration behavior,
not firmware compatibility.
Evidence: 30 client tests and nine real HA 2026.9.2 runtime tests pass locally.
On 2026-10-11, 30 client tests and 11 HA runtime tests passed locally, including
the new diagnostics tests. Lint, formatting and typing checks also passed.
Latest local validation: 58 client tests and 11 HA runtime tests pass with all
13 sensors sharing one coordinator request. The latest 11 HA tests pass against
the exact installed Core version, 2026.10.1 (and the earlier 2026.10.0 baseline).
No external sockets are allowed in HA tests.
All five [GitHub CI jobs](https://github.com/StormAvenger/creator5-ha/actions/runs/37501135092)
passed for implementation commit `c8889c1`, including the Linux HA job.

### 4. Confirm live LAN access — resume with the printer

- [ ] Confirm IP, stock firmware version and LAN mode on the printer display.
- [ ] Verify that the responding address belongs to the already-printing printer
  before entering credentials; an open TCP port does not identify the device.
- [x] Identify the supplied target using one directed discovery packet: vendor,
  PID 41 (Creator 5 Pro), HTTP port 8898; serial kept private.
- [ ] Check the Mac's route/VLAN/VPN/firewall if port 8898 still times out.
- [ ] If away from home, verify an existing Tailscale subnet route or WiFiman
  Teleport connection, or an already-authorized HA-host terminal; remote HA UI
  access by itself does not establish a Mac-to-printer route.
- [x] Use the discovered serial and owner-corrected code for a successful `/detail` read.
- [ ] Confirm state and basic readings against the printer display.
- [ ] Record a sanitized compatibility note for the observed firmware.

**Complete when:** a valid authenticated status response is observed on the
user's printer. Earlier reachability timed out; hardware compatibility is unverified.
On 2026-10-11 a TCP-only check and targeted discovery succeeded. Two read-only
status attempts with the same credentials were rejected (HTTP 200, code 1).
After the owner supplied the lowercase spelling, one status read succeeded and
reported printing, Creator 5 Pro, firmware 1.9.9, valid progress and temperatures.
The client preserved the corrected code exactly; no guessed variants or controls
were sent. Readings are a snapshot, not continuous monitoring.
Follow [the first-session checklist](first-printer-session.md).
Earlier remote inspection found HA Core 2026.9.4 and a reachable API port while
the printer was subsequently off. The latest local session identifies the printer
and authenticates successfully; HA now reports Core 2026.10.1 on HA OS 18.3.

### 5. Complete the monitoring model

- [ ] Validate documented basic fields against real responses.
- [x] Add four tool-head temperatures and targets from the documented arrays
  present in the successful response; test missing arrays and genuine zero targets.
- [ ] Compare each tool's reading with the printer display; verify ordering physically.
- [ ] Add layers, elapsed time, door state and material-slot sensors only where
  field semantics are verified. Remaining time is already provisional.
- [ ] Distinguish unsupported fields from genuine zero readings.
- [ ] Keep camera URLs and identifiers out of diagnostic/log output.
- [ ] Consider a camera entity only after verifying the local stream and privacy behavior.

**Complete when:** every shipped sensor has a documented meaning and tested
missing-field behavior; the real printer UI agrees with readings across states.
Do not infer capabilities from older printer models or an API success response.

### 6. Validate a development HA installation

Current evidence: installed on the owner-authorized HA 2026.10.1 host on 2026-10-14;
one device, 13 available sensors and scheduled refreshes during an existing print.
No HA restart was needed. Downloaded diagnostics exclude the supplied serial,
LAN code and printer IP. See [live acceptance evidence](live-acceptance.md).

- [x] Install into the owner-authorized HA instance; record its version.
- [x] Confirm HA Core restart/recovery with 0.2.0.
- [ ] Confirm live remove/unload, printer-network recovery and credential changes.
- [x] Observe a user-started print without controlling it; scheduled readings update.
- [x] Observe natural completion and idle from an already-running print.
- [ ] Observe a full ordinary print from its start.
- [x] Confirm one device, 13 sensors and successful scheduled updates.
- [ ] Measure polling load without invasive instrumentation.
- [x] Confirm exported diagnostics omit the supplied serial, LAN code and printer IP.
- [x] Review all 13 live entity attributes and filtered component logs for privacy;
  no supplied credentials/identifiers or raw payloads exposed.

**Complete when:** monitoring works through a full normal print and reconnect cycle.
Tests can be authored offline; live acceptance depends on hardware access.

### 7. Confirm portability to Ubuntu

- [ ] Clone from GitHub into a fresh Ubuntu checkout and recreate its environment.
- [ ] Run the same client and HA tests; supply credentials locally.
- [ ] Verify LAN reachability from the intended Ubuntu/Unraid network.
- [ ] Install/test the integration on the intended HA host.

**Complete when:** no source changes or machine-specific paths are needed.
Virtual environments and secret files are recreated, never copied between OSes.

### 8. Prepare the first release

- [ ] Finalize legal/provenance notes, owner-selected license and notices.
- [ ] Confirm supported firmware and HA versions from evidence.
- [ ] Run hassfest and HACS validation locally if HACS distribution is chosen.
- [ ] Write installation/troubleshooting/uninstall instructions and release notes.
- [ ] Review the full repository for secrets and proprietary assets.
- [x] Replace personal email in existing commit history before publication;
  future commits use the verified GitHub noreply identity.
- [ ] Obtain the owner's decision to publish publicly and create the first release.

**Complete when:** clean installs work, CI/validation passes, and release metadata
accurately describes support and limitations. Keep the repository private until then.

### 9. Chamber-light control and extra sensors — prepared

The owner selected chamber light as the sole control and requested Celsius for
this device. Version 0.2.0 is installed: 24 sensors, five Pro binary sensors and one
on/off light. Its 83 client and 14 HA tests pass. The HA Core restart/recovery and
reported light off/on test succeeded; see [scope and evidence](extended-monitoring.md).
All ten installed temperature entities were set to Celsius through HA's normal
per-entity settings; household units were preserved.

- [x] Parse bounded material slots, combined Pro door/lid state and fan reports.
- [x] Add elapsed/layer/temperature-target readings from observed fields.
- [x] Implement LED-only writes with strict boolean input and status readback.
- [x] Test Celsius defaults/migration on a Fahrenheit host, preserving unrelated devices.
- [x] Approve and activate 0.2.0 on HA; verify the Pro's 30 entities.
- [x] Verify one LED-only off/on cycle by reported state and restore its initial on state.
- [ ] Independently observe physical illumination.
- [ ] Compare new fields to the device display; retain unsupported signals as unknown.

Print, motion, heater, fan, firmware and material-control commands remain outside
scope. Completion and reconnect checks must not interrupt a running job.

## How we continue each session

Start from the first unchecked item whose prerequisites are available. Keep
hardware items pending while offline. For each change, record what was verified,
update this guide, run relevant checks locally and publish a reviewable development branch/PR.
The user supplies hardware observations and decisions; Codex handles code, tests,
docs and local validation. Never mark a hardware milestone complete from synthetic tests alone.

## Next approved feature scope — version 0.3.0

The owner requested 10-second default/configurable polling, a camera entity,
connection health/last success, model/firmware/error reporting, nozzle sizes,
visible slot colors and user-configured tool/slot material assignments. No other
reporting or controls are assumed. See [implementation and acceptance plan](camera-and-monitoring.md).

- [x] Implement 49 Pro entities with a shared 10-second status poll.
- [x] Add editable HA-only mappings/notes, with unassigned defaults for new users.
- [x] Validate one bounded camera read on the Mac; keep the frame private.
- [x] Test shared on-demand media, URL restrictions, cleanup and retry.
- [x] Test interval cadence/options reload, health/recovery and metadata parsing.
- [x] Approve/load the custom 0.3.0 update and verify live HA camera/49 entities.
- [x] Enter the owner's confirmed current mappings in HA, not source code.
- [ ] Investigate brief camera unavailable entries around initial view closing;
  viewing/reopening and next-poll recovery work, with no component log errors.
- [ ] Compare physical nozzle order and display readings.

Local evidence: 102 client/framing and 33 HA tests pass. No hosted workflows run.
Lifetime counters, job-name/thumbnail reporting, notifications, bed mesh and more
controls require another scope decision from the owner.

## 0.3.1 slot presentation and public-release preparation

- [x] Implement local exact-color image entities and move raw hex details to diagnostics.
- [x] Supply native grouped slot cards with mapped nozzle/material notes.
- [x] Default the noisy timestamp entity off for new installations.
- [x] Run fresh-entry setup, exact-pixel, update and unload tests.
- [x] Load 0.3.1 on the owner HA host and verify its grouped dashboard.
- [x] Rewrite personal author/committer identities on both remote branches; verify noreply identities.
- [x] Owner selected GPLv3 (GPL-3.0-only); include GNU text and package metadata.
- [ ] Publish only after explicit owner approval.

See [slot presentation](slot-display.md) and [license](../LICENSE).

## 0.3.2 HACS and two-field setup

- [x] Normal setup asks only for IP and LAN code, discovering serial at that IP.
- [x] Cross-check supported discovery ID against authenticated status model.
- [x] Omit Pro-only chamber and door/lid entities for base/unknown models.
- [x] Add HACS metadata and original local icon assets; document no-YAML setup.
- [x] Official hassfest passes; clean component-archive setup and all 147 tests pass.
- [x] Approve/activate 0.3.2 while ready; verify two-field form and duplicate protection.
- [x] Obtain owner publication approval; promote the validated default branch.
- [x] Verify public HACS download, idle-only HA restart and fresh authenticated setup.

Pro is hardware-tested; base support is experimental/synthetic-test coverage only.
