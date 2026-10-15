# Install Creator 5 in Home Assistant

Normal setup uses forms, not YAML. Add this project as a HACS custom repository;
it is not a HACS default listing. HACS itself must already be installed.
Version 0.3.2 is the first public candidate. End-to-end HACS acceptance is being
checked; see [validation evidence](hacs-candidate.md).

## Before starting

- Home Assistant 2026.10.1 or newer (2026.10.1 is the tested version).
- A Creator 5 Pro in LAN mode. Base Creator 5 is detected but remains experimental
  and untested on real hardware; its Pro-only sensors are omitted.
- The printer's private IPv4 address and LAN code. No serial entry is needed.
- HA can reach that address: UDP 48899 for identification, TCP 8898 for status,
  and TCP 8080 for optional on-demand camera viewing. Remote HA access alone does
  not give the HA server a route to the printer; both need network connectivity.

## Download through HACS

1. Open HACS, select the three-dot menu and **Custom repositories**.
2. Enter `https://github.com/StormAvenger/creator5-ha`, select **Integration**, and add it.
3. Open **Creator 5 LAN (experimental)** and select **Download**.
4. Restart Home Assistant when prompted.

This is a custom repository installation, not a claim of inclusion in the default
HACS catalog. Releases are preferred; without a release HACS uses the default
branch. Do not download an older scaffold branch that lacks the current setup flow.

## Connect your printer

1. Open **Settings → Devices & services → Add integration**.
2. Search **Creator 5** and choose **FlashForge Creator 5 (experimental)**.
3. Enter the IP address and case-sensitive LAN code. Select **Submit**.
4. HA reads the serial automatically and cross-checks the discovered model against
   authenticated status. It then adds the printer and its supported entities.

Setup performs one directed identification request, never broadcast/subnet scans,
then one authenticated status read. It does not send light, heater, fan, motion,
material or print commands. Wrong credentials return a form error; no code guessing
or automatic retry occurs. Unknown or conflicting models are not saved.

## Pro versus base Creator 5

Identification combines discovery product ID 41/40 (Pro/base) with the exact
`Creator 5 Pro` / `Creator 5` status model. The common productType value is not used
to distinguish them. Pro-only door/lid, chamber temperature, chamber target and
chamber fan readings are not created without a positive Pro identification.
Shared tools, materials, bed, camera, cooling-fan report and chamber light remain.
Base support follows documented protocol facts and synthetic tests; it has not
been validated on a physical base model. Existing entries do not require re-entry.

## Optional settings

The integration's **Configure** form adjusts polling (10 seconds by default),
camera viewing, tool-to-slot assignments and material notes. Assignments are manual;
no identity mapping is assumed. Temperatures default to Celsius for this device.
The noisy success-timestamp entity stays off by default; cached diagnostics retain
that timestamp. The only write control is the chamber light.

The grouped slot dashboard is optional and separate from connection setup. HACS
installs integration files, not dashboards. The repository supplies reusable native
card examples; automatic guided dashboard installation is not implemented yet.
The integration itself and its entities do not require that optional dashboard.

## Troubleshooting and removal

- **Could not identify:** check the exact address, LAN mode and UDP 48899 reachability.
  Some network isolation/firewall configurations block discovery even when HTTP works.
- **Invalid LAN code:** use exact capitalization; it is not the printer's serial.
- **Cannot read status:** check the HA-to-printer route and TCP 8898.
- **Model mismatch:** setup stops rather than guessing capabilities. Report the error
  and model/firmware, without posting credentials or raw responses.
- **No camera picture:** confirm LAN connectivity and TCP 8080. Viewing is on demand;
  it does not turn the camera or printer on.
- To remove: delete the printer entry in **Devices & services**, then remove the
  repository in HACS and follow its restart prompt. Preserve other integrations.

Credentials stay in HA's private configuration. Keep HA backups private. Downloaded
integration diagnostics exclude the printer IP, serial and LAN code, but HA may add
system metadata around them; review a diagnostic file before sharing it.

References: [HACS custom repositories](https://www.hacs.xyz/docs/faq/custom_repositories/),
[HACS integration requirements](https://www.hacs.xyz/docs/publish/integration/),
[Creator 5 model reference](https://github.com/Parallel-7/flashforge-api-docs/wiki/Creator-5-Series).
