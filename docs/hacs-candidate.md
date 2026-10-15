# 0.3.2 HACS installation candidate

Prepared on 2026-10-14. Version 0.3.2 is the owner-approved first public candidate, not a catalog-listed
HACS download or a claim of default-catalog inclusion. Normal connection setup is
IP address + LAN code, with no serial entry or YAML configuration.

## Changes and boundaries

- One directed UDP 48899 identity request to the supplied private IPv4, followed
  by normal authenticated status on 8898. No scan, broadcast, code guessing,
  automatic retry or printer control command.
- Discovery ID 40/41 must agree with authenticated Creator 5 / Creator 5 Pro model.
  Serial is stored internally for HA's existing unique identity and authentication.
  Conflicting/unknown models are rejected before a config entry is created.
- Existing config entries retain their serial, credentials, options and entity IDs.
- Pro-only door/lid, chamber temperature/target and chamber fan entities are omitted
  for non-Pro/unknown model status. Base support is unverified on hardware.
- HACS metadata, GPLv3 text and original local icons ship with the component.
  No published PyPI client or third-party frontend dependency is required.
- The optional grouped slot dashboard is still separate from ordinary setup.
  HACS does not automatically create it; automatic dashboard import is out of scope.

## Local validation

- 102 standalone tests and 45 real HA 2026.10.1 tests pass (147 total).
- All 45 HA tests also pass from a fresh directory extracted from the component
  archive, using synthetic identity/status and no owner credentials/config entry.
- External sockets are blocked in HA tests; Unix sockets support the event loop.
- Home Assistant's official hassfest validator from tag 2026.10.1 reports one
  integration and zero invalid integrations, including manifest/flow/translations.
- Lint, formatting and client typing pass. Wheel and source distribution build;
  wheel contains GPL-3.0-only metadata and exact GNU license text.
- Local structural checks confirm one integration directory, required manifest
  fields, minimum HA version, local PNG dimensions, included license and sdist assets.
  These are local checks, not an end-to-end run of HACS against a public repository.
- No GitHub Actions, paid services or live printer commands were used for these checks.

## Before public download

The owner has approved public publication and HACS installation. Review repository description/topics,
merge a reviewed candidate into the default branch or publish its tested release,
and verify HACS custom-repository download after the repository becomes public.
Do not claim the private repo is already downloadable through HACS. Public/catalog
submission is not part of the packaging work. Camera-transition investigation,
physical comparisons and idle-only printer-network recovery remain in the wider
release acceptance checklist.

## Approved live acceptance

On 2026-10-14 the owner specifically approved 0.3.2 installation, an idle-only HA
Core restart and a setup-form check without removing the existing printer. A
private 0.3.1 source rollback archive was retained outside the repository.
Five changed source/translation/manifest files, the GPL text and both local PNG
icons were saved. The normal file picker completed uploads; no extension file-URL
permission or other browser security setting was changed.

HA configuration validation passed. The printer reported ready and connected
immediately before restart; HA reported no running automations/scripts. After
restart, the integration page reports 0.3.2, one device and 53 registered entities.
Diagnostics confirm successful 10-second polling and contain none of the actual
printer IP, serial or LAN code. The optional timestamp remains disabled, all four
slot groups and the high-flow material note still render, and filtered creator5
logs show no issues.

The live Add device form shows exactly IP address and password-masked LAN code,
with no serial field. Entering the existing printer's two values returned "This
printer is already configured." This validates targeted identity lookup and
serial-based duplicate protection without removing, replacing or modifying the
existing entry. Because duplicate protection stops before a fresh authenticated
setup, this was not a live clean-entry authentication test; synthetic clean setup
and model cross-check coverage remains the local test evidence. The form was
closed after the check. No light or print-affecting commands were sent.

Public HACS download and a physical base-model test remain pending. Repository
visibility remains private; no release, catalog submission or paid services were
activated.
