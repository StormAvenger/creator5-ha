# Home Assistant development installation

This is an experimental integration, not a validated production release.
Offline runtime tests cover Home Assistant 2026.10.0. One authenticated status read
succeeded on the user's Creator 5 Pro while printing (API firmware 1.9.9).
The latest signed-in About page confirmed HA Core 2026.10.0, Supervisor 2026.09.3,
HA OS 18.3 and frontend 20260930.2. All 11 runtime tests passed against that exact
Core version with external sockets disabled.

All 13 component files are staged in an isolated `/homeassistant/custom_components/creator5`
directory. HA's basic configuration check passed. This checks YAML startup validity;
it does not establish successful loading or live sensor behavior. Activation and
credential storage await the specific browser confirmation. No HA upgrade is needed.

1. Confirm that the standalone read-only probe succeeds first.
2. Copy the entire `custom_components/creator5` folder into the development Home
   Assistant configuration's `custom_components` folder.
3. Restart Home Assistant, then add **FlashForge Creator 5 (experimental)** under
   Settings → Devices & services.
4. Enter the printer's private IPv4, serial number and LAN check code.

The flow validates one status read. The coordinator polls every 30 seconds and
shares one response among the sensors. Failed updates make entities unavailable.
Authentication failure requests a new check code. Removing the integration unloads
its sensor platform. Missing numeric fields remain unknown rather than zero.
The 13 sensors include state, progress, bed/chamber temperature, remaining time,
and current/target temperatures for tools 1–4. Each four-element tool array is
validated; real zero targets remain zero, not unknown. Tool numbering follows
the documented array order and still needs comparison with the physical display.
The owner authorized installing read-only monitoring while the print runs. Never
send print controls or change printer settings. Activation stores credentials in
HA and starts the shared status poll; keep configuration and backups private.

## Offline runtime tests

The integration provides cached diagnostics through HA's integration menu. Our
diagnostics section includes only numeric readings, update success and read-only
mode. It omits config-entry data, raw responses, free-form status strings, IP,
serial, filenames, URLs and tokens; requesting it performs no printer I/O.
If the last update failed, numeric values are stale and update success is false.
Home Assistant can add its own surrounding system metadata to a downloaded
diagnostics file; review the whole file before sharing it.
See [HA diagnostics guidance](https://developers.home-assistant.io/docs/core/integration/diagnostics/).

Use a separate Python 3.14 environment to keep HA's pinned dependencies separate
from the lightweight standalone client environment. Run locally (Actions is disabled):

```sh
python -m pip install -r requirements-ha-test.txt
python -m pip install -e .
python -m pytest tests/ha --disable-socket --allow-unix-socket
```

The fixture runs real HA config-entry/coordinator/entity code, replacing only
printer I/O. Eleven tests cover user setup, rejected credentials, unreachable and
invalid targets, duplicates, reauthentication, sensor values, scheduled polling,
missing values, disconnect/recovery, first-refresh failures and unload.
After unload, HA may keep unavailable entity-registry placeholders; polling stops.
The ordinary client suite skips the HA tests when the optional framework is absent.

Home Assistant stores credentials in its config entry under `.storage`. Treat the
configuration directory and backups as private; password masking is not encryption.
The integration's diagnostics are allowlisted; raw-response attributes are not exposed.

Developer references:
- [Config flow](https://developers.home-assistant.io/docs/core/integration/config_flow/)
- [Shared polling coordinator](https://developers.home-assistant.io/docs/integration_fetching_data/)
- [Integration manifest](https://developers.home-assistant.io/docs/creating_integration_manifest/)

Before distribution: run HA runtime tests against the user's target HA release, add more
sensor mappings from sanitized observations, choose a license with the owner,
validate packaging with hassfest/HACS locally as applicable. Historical CI tested the
client across OSes and the pinned HA baseline; it does not establish
physical-printer compatibility or support for untested HA versions.
