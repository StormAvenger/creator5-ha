# Project completion guide

**Goal:** an unofficial, local Home Assistant integration for the user's stock
Creator 5 Pro, backed by a portable standalone Python client. First release:
read-only monitoring. macOS development, Ubuntu deployment, GitHub for source and CI.

This guide carries forward the project and legal boundaries from **TPU Jams
Troubleshooting**. It is the ordered checklist we update as work progresses.
Last reviewed: 2026-10-06. Hardware is unavailable until the user returns later today;
there is no automatic retry or scheduled printer access.

## Working boundaries

Use normal LAN mode and the owner's credentials. Write our own implementation
from documented protocol behavior and observations of the owner's equipment.
Keep testing offline until hardware access resumes. See [legal and source notes](legal-and-sources.md).

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
- [ ] Choose an outbound license with the owner before public distribution.

**Complete when:** development scope and source provenance are documented; any
reuse has its license and required notices. No blanket legal clearance is claimed.
Exact installed terms and public-license choice remain release gates, not blockers
for original offline code and synthetic tests.

### 3. Validate Home Assistant without the printer — runtime tests complete locally

- [x] Use a pinned HA test framework and document the exact HA baseline.
- [x] Test setup validation, duplicates, invalid inputs and rejected credentials.
- [x] Test config-entry setup, sensor values and periodic coordinator refreshes.
- [x] Test missing fields, lost connectivity and recovery.
- [x] Test changed credentials/reauthentication and platform unload.
- [x] Add a separate Linux CI job for actual HA runtime tests.
- [ ] Confirm the new HA job passes on GitHub.

**Complete when:** the tests exercise real HA classes with synthetic status data,
no printer/network credentials, and CI passes. Mocks prove integration behavior,
not firmware compatibility.
Evidence so far: 30 client tests and nine real HA 2026.9.2 runtime tests pass locally.

### 4. Confirm live LAN access — resume with the printer

- [ ] Confirm IP, stock firmware version and LAN mode on the printer display.
- [ ] Check the Mac's route/VLAN/VPN/firewall if port 8898 still times out.
- [ ] Enter serial/check code locally and read `/detail` once.
- [ ] Confirm state and basic readings against the printer display.
- [ ] Record a sanitized compatibility note for the observed firmware.

**Complete when:** a valid authenticated status response is observed on the
user's printer. Earlier reachability timed out; hardware compatibility is unverified.
Follow [the first-session checklist](first-printer-session.md).

### 5. Complete the monitoring model

- [ ] Validate documented basic fields against real responses.
- [ ] Add four tool-head temperatures, targets, layers, elapsed/remaining time,
  door state and material-slot sensors only where field semantics are verified.
- [ ] Distinguish unsupported fields from genuine zero readings.
- [ ] Keep camera URLs and identifiers out of diagnostic/log output.
- [ ] Consider a camera entity only after verifying the local stream and privacy behavior.

**Complete when:** every shipped sensor has a documented meaning and tested
missing-field behavior; the real printer UI agrees with readings across states.
Do not infer capabilities from older printer models or an API success response.

### 6. Validate a development HA installation

- [ ] Install into a development HA instance; record its version.
- [ ] Confirm add/remove/restart, unavailable/recovery and credential changes.
- [ ] Observe idle and an ordinary user-started print without controlling it.
- [ ] Check polling load and entity/device naming for one printer.
- [ ] Confirm secrets stay out of logs, attributes and exported diagnostics.

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
- [ ] Run hassfest and HACS validation if HACS distribution is chosen.
- [ ] Write installation/troubleshooting/uninstall instructions and release notes.
- [ ] Review the full repository for secrets and proprietary assets.
- [ ] Obtain the owner's decision to publish publicly and create the first release.

**Complete when:** clean installs work, CI/validation passes, and release metadata
accurately describes support and limitations. Keep the repository private until then.

### 9. Optional follow-up scope — after monitoring is stable

Controls such as light, pause/resume/cancel or temperatures are separate future
work, requiring explicit feature selection, verified protocol semantics and
appropriate user confirmation. Motion, unsupported material operations, firmware
changes and cloud experiments are not assumed parts of this integration.

## How we continue each session

Start from the first unchecked item whose prerequisites are available. Keep
hardware items pending while offline. For each change, record what was verified,
update this guide, run relevant checks and publish a reviewable development branch/PR.
The user supplies hardware observations and decisions; Codex handles code, tests,
docs and CI. Never mark a hardware milestone complete from synthetic tests alone.
