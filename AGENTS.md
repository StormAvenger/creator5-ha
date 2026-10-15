# Standing user constraints

The user requires zero paid GitHub usage. Student benefits may be used after
activation only when the feature is verified free and cannot produce overage charges.

- Never start paid features, trials that can convert to paid plans, plan upgrades,
  payment-method setup, budget increases or purchases.
- Keep repository Actions disabled. Run tests, lint, typing and builds locally.
  Do not run/rerun hosted workflows, create Codespaces, request paid Copilot reviews,
  enable paid security/marketplace services, or use metered LFS/package features.
- After education benefits activate, verify the active offer, expiry, limits and
  no-overage controls before proposing a covered feature. Never enable it solely
  because three days have elapsed or because free credits are advertised.
- Use ordinary source commits, branches, issues, PRs and source releases. Unknown
  cost means use a local/no-charge alternative instead of risking a charge.
- The former workflow in docs/reference is archival; never restore active triggers
  without a new feature-specific user decision and verified zero-cost controls.
- Do not change repository visibility as a cost workaround.

On 2026-10-11 the user resumed local LAN access while the printer is printing.
Do not stop, pause, resume, change temperatures, upload, reboot, update firmware,
or otherwise alter the print. Use only the one-shot authenticated POST /detail
status endpoint after credentials and target identity are available locally.
One directed UDP discovery packet to the supplied target on port 48899 may obtain
its serial. No broadcast, multicast, subnet scan, guessed codes or authentication bypass.
Discovery identified the Creator 5 Pro. After the owner corrected code capitalization,
one authenticated status read succeeded, reporting printing and firmware 1.9.9.
Keep credentials case-sensitive and private. Do not repeat reads without a concrete
validation need; use the private cached snapshot for offline development.
The user subsequently authorized continuing the next Home Assistant installation
steps while the print runs, provided it is not cancelled or otherwise altered.
An isolated creator5 component may be staged and read-only monitoring configured;
verify existing HA state first and preserve existing configuration. Normal status
polling is allowed for live monitoring; print-control requests remain prohibited.
Follow docs/legal-and-sources.md and docs/project-guide.md.

On 2026-10-14 the owner requested continuation of the prepared activation step.
The component was added successfully to HA Core 2026.10.1 without restarting HA.
Credentials are stored in HA's private config entry; one device and 13 sensors
refresh through the read-only coordinator. Do not repeat the standalone probe
without a concrete need while HA is already polling. No live disconnect, credential
change, unload or full-print test is yet recorded. Follow docs/live-acceptance.md.

The owner subsequently requested additional monitoring, device-specific Celsius,
and chamber light as the sole control. Version 0.2.0 was subsequently approved and installed after natural completion.
It is live with 30 entities. The narrow set_light(bool) method is authorized development
scope; all print, heater, fan, motion, upload and material writes remain prohibited.
Before browser activation of the custom update, obtain specific action-time
approval. Do not send live light commands as part of setup or ordinary polling.
Physical comparisons must not involve opening doors or disrupting a running print.

The approved 0.2.0 HA Core restart/recovery succeeded. One LED-only off/on cycle
was verified through status readback while ready, restoring the initial on state.
All twelve temperatures are Celsius. Do not repeat the light test without a new
validation need. Printing → completed → ready was observed naturally; remaining
time is unknown outside active/paused states because a stale value was observed
on completion. Physical comparisons and printer-network recovery remain pending.

The latest owner-approved development scope is version 0.3.0: 10-second default
and configurable polling, camera viewing, API health/last success, model/firmware/
validated error codes, slot colors, nozzle sizes and user-configured material-slot
assignments. The owner confirmed a current mapping privately; configure it in HA,
never hardcode it for all installations. Do not add other reporting/controls without
asking. Camera requests are read-only, bounded to the same configured printer;
never send camera-control commands, follow redirects, expose URLs or credentials,
record footage or create paid/cloud services. Obtain action-time approval before
browser installation/activation of the custom update and its new camera access.

Version 0.3.0 was specifically approved and installed on 2026-10-14 after ready
was observed. HA restarted and loaded all 49 entities. Ten-second status updates,
camera viewing/reopening, diagnostics redaction and manual mappings were checked.
The high-flow note describes material, not nozzle type; nozzle sizes remain API
reported. Two brief camera unavailable entries occurred around initial viewing/
closing and recovered on the next status poll; sustained later viewing worked.
Keep that observation in the acceptance guide until its cause is established.
No print controls or light test were sent during this activation.

The owner requested quiet Activity on 2026-10-14. The separate last-success timestamp
entity is disabled in HA; preserve that preference. The coordinator and cached
diagnostic timestamp still update every 10 seconds. Host Recorder/logbook exclude
that entity as well. Do not purge old history or re-enable the entity automatically.

On 2026-10-14 the owner explicitly approved installing 0.3.1, an idle-only HA
Core restart and a grouped slot dashboard. Preserve the active print protections.
The owner selected GPLv3: use GPL-3.0-only, with the unmodified GNU text in LICENSE.
Keep repository visibility private until a separate publication decision.

The owner also explicitly approved replacing remote history on both main and
offline-validation-guide with privacy-cleaned commits, understanding that commit
IDs change and other clones need resynchronization. This answers the auto-review
rejection's requested exact branch approval. The local rewrite preserved all
original commit trees/messages/dates and a private recovery bundle. Use exact
force-with-lease values recorded privately; do not overwrite unexpected remote work.

Approved privacy history replacement succeeded atomically on both GitHub branches;
all reachable branch author/committer emails now use the GitHub noreply identity.
The original recovery bundle is private and outside the repository. Unreferenced
GitHub objects/caches and other copies are not proven erased; do not claim that.
0.3.1 activation succeeded while ready; diagnostics show version 0.3.1 and 10-second
successful polling. Four native swatches and the Creator 5 slot dashboard are live.
The existing disabled timestamp preference and manual material mappings remain.
No print-affecting or light commands were sent. Repository remains private.

The owner requested HACS installation plus IP/LAN-code-only setup and model
detection. 0.3.2 is prepared: targeted discovery obtains serial; PID and status
model must agree. Pro-only chamber/door entities are omitted for base/unknown
models. Base support is documented as hardware-unverified. HACS metadata, original
local icons and component GPL text are included. 147 tests, clean component-archive
HA setup and official 2026.10.1 hassfest pass locally. Live 0.3.2 activation and
public HACS download acceptance are pending; the live host is still on 0.3.1.
Keep the repo private until separate publication approval. No hosted Actions.

The owner specifically approved 0.3.2 installation/restart/form checking. It is now
installed after ready/connected and no running HA scripts were verified. The live
form has only IP and LAN code; the existing printer returned already_configured
after targeted identity lookup, without altering its config entry. This checks
discovery/duplicates, not a fresh live authenticated setup. HA reports 0.3.2, one
device and 53 entities; 10-second successful polling, disabled timestamp, slot
mappings/high-flow note and clean component logs were checked. Normal OS file
picker uploads installed icons/license; browser security settings were untouched.
No light or print-affecting commands were sent. Keep repository private.

The owner now explicitly authorizes public publication and a real HACS install
test after deleting the integration. This supersedes the earlier keep-private
release gate. Promote the tested 0.3.2 code to the default branch before download.
Keep Actions disabled, protect credentials and preserve the print protections.
Record actual HACS download and fresh setup results without overstating evidence.

Public HACS acceptance succeeded on 2026-10-14 after owner action-time approval.
HACS downloaded main commit 8b69923; an idle-only HA restart and fresh two-field
authenticated setup created a new Pro entry with 53 entities. Diagnostics confirm
successful 10-second polling. Keep the optional timestamp disabled. No print or
light controls were sent. The repository is public; previous private-only gates
are historical. Retained older PR-linked commit metadata is not claimed erased.

The owner requests the next patch release and a concise public README with a
prominent experimental/use-at-your-own-risk warning, AI-assisted development
transparency, Pro-only hardware testing and contribution guidance. Current 0.3.2
advances to 0.3.3. This release changes documentation/version metadata only;
publication does not authorize a new HA restart or unrelated feature work.
Privacy audit covers tracked files and reachable branch history; distinguish
synthetic IP test values from real owner data and retain the old GitHub metadata
caveat. No raw diagnostics, MACs, known credentials or owner LAN/HA address were found.
