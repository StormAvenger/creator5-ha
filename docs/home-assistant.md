# Home Assistant development installation

This is an experimental scaffold, not a validated production integration.

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

Home Assistant stores credentials in its config entry under `.storage`. Treat the
configuration directory and backups as private; password masking is not encryption.
The integration exposes no diagnostics or raw-response attributes.

Developer references:
- [Config flow](https://developers.home-assistant.io/docs/core/integration/config_flow/)
- [Shared polling coordinator](https://developers.home-assistant.io/docs/integration_fetching_data/)
- [Integration manifest](https://developers.home-assistant.io/docs/creating_integration_manifest/)

Before distribution: run HA runtime tests against the target HA release, add more
sensor mappings from sanitized observations, choose a license with the owner,
validate packaging with hassfest/HACS as applicable. Current CI checks the standalone
client and static integration source; it does not claim HA runtime compatibility.
