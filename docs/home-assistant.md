# Home Assistant development installation

This is an experimental integration, not a validated production release.
Offline runtime tests cover Home Assistant 2026.9.2; real printer compatibility
and the user's installed HA version remain unverified.
The remote About page subsequently confirmed the user's HA Core version is
2026.9.4 on HA OS 18.3. Runtime tests currently cover 2026.9.2; installation and
live validation on 2026.9.4 are still pending.

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

## Offline runtime tests

Use a separate Python 3.14 environment to keep HA's pinned dependencies separate
from the lightweight standalone client environment. Linux CI runs:

```sh
python -m pip install -r requirements-ha-test.txt
python -m pip install -e .
python -m pytest tests/ha --disable-socket --allow-unix-socket
```

The fixture runs real HA config-entry/coordinator/entity code, replacing only
printer I/O. Nine tests cover user setup, rejected credentials, unreachable and
invalid targets, duplicates, reauthentication, sensor values, scheduled polling,
missing values, disconnect/recovery, first-refresh failures and unload.
After unload, HA may keep unavailable entity-registry placeholders; polling stops.
The ordinary client suite skips the HA tests when the optional framework is absent.

Home Assistant stores credentials in its config entry under `.storage`. Treat the
configuration directory and backups as private; password masking is not encryption.
The integration exposes no diagnostics or raw-response attributes.

Developer references:
- [Config flow](https://developers.home-assistant.io/docs/core/integration/config_flow/)
- [Shared polling coordinator](https://developers.home-assistant.io/docs/integration_fetching_data/)
- [Integration manifest](https://developers.home-assistant.io/docs/creating_integration_manifest/)

Before distribution: run HA runtime tests against the user's target HA release, add more
sensor mappings from sanitized observations, choose a license with the owner,
validate packaging with hassfest/HACS as applicable. CI tests the client across OSes
and tests the integration against the pinned HA baseline; it does not establish
physical-printer compatibility or support for untested HA versions.
