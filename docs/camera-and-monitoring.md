# Camera and monitoring — version 0.3.0

Status: implemented and tested locally; live HA still runs 0.2.0 until this update
is approved and loaded. No camera enable/start command or new printer control was
added. The light remains the sole write operation.

## Prepared scope

The Pro has 49 entities when its camera is enabled: 40 sensors, seven binary
sensors, one chamber light and one camera. The existing temperature entities
continue to default to Celsius. Reported nozzle diameters use millimeters even
when HA's household units are imperial.

- Status polling defaults to 10 seconds, with one shared request for every entity.
  The options form accepts whole intervals from 5 to 300 seconds. Refreshes do not
  overlap; slow replies and failures can extend the observed time between updates.
- Four slot-color sensors expose configured hex colors alongside the existing slot
  material/presence sensors. Color is a slot setting, not an optical measurement.
- Four nozzle-diameter sensors parse the ordered semicolon-delimited nozzleModel
  field. Exactly four positive bounded diameters are required. Physical tool order
  still needs display comparison; values are reported sizes, not measured bores.
- Four tool-material sensors use explicit user-configured slot assignments.
  Defaults are unassigned (unknown), not an assumed tool/slot identity mapping.
  Each includes configured_slot, mapping_source, current slot color and a bounded
  user_note. Material text follows the assigned slot's live report; notes remain
  owner-supplied and must be revised when their meaning changes.
- Model and firmware sensors validate bounded expected values. Device metadata also
  includes the first valid model/firmware read at setup.
- Error-code reporting accepts an empty code as none or the E#### form. Other
  values are unknown. A problem binary sensor reflects a validated nonempty code;
  no unverified error description or automatic recovery action is invented.
- Status connection goes off after a failed update while other data become
  unavailable. Last successful status update remains visible and retains its
  previous timestamp. These are status-API health indicators, not camera health.
  If the initial setup cannot connect, HA's normal setup-retry/unavailable behavior
  applies until a first successful read.

## Camera behavior

A bounded direct read of the owner's local stream returned HTTP 200,
multipart/x-mixed-replace and a valid JPEG frame. The frame was retained privately
outside Git. This validates the Mac-to-camera path, not yet HA viewing.

The HA entity gets the stream URL from cached printer status unless an optional
URL override is configured. It accepts only the configured private printer IPv4,
HTTP port 8080 and the known /?action=stream path. Credentials, fragments, alternate
hosts/ports, unrelated query parameters and redirects are rejected. No LAN check
code is added to a video request or exposed in entity attributes/diagnostics.

Viewing is through HA's normal camera access controls and proxy. Opening a live
view does not publish the printer's local URL. HA's standard camera access-token
mechanism still applies; camera links and screenshots should be treated as private.

Images/video connect only on demand, never as part of the 10-second status poll.
Concurrent still/live consumers share one upstream connection per camera entity.
Only the latest bounded frame is retained for active viewers; it is discarded
when the final viewer leaves. No recording, cloud upload or background video
capture is enabled. A visible dashboard requesting thumbnails counts as a viewer.

Media reads have connection/read timeouts and a 2 MiB frame limit. Closing views
or unloading cancels the upstream read. A failed media read marks the camera
unavailable; a subsequent status update permits a new on-demand attempt rather
than probing it continuously. The frame rate follows the camera stream and is
independent of the status interval.

## Settings and the owner's current mapping

After activation, use Settings → Devices & services → Creator 5 → Configure.
Keep the camera URL empty to use the validated printer report. Set tool-slot
assignments only after physical confirmation; they do not command or reconfigure
anything on the printer. The owner has confirmed the current tool/slot assignments
privately, so those will be entered in HA rather than hardcoded into this project.
The high-flow distinction is a user note because the API reports PETG generically.

## Validation and pending acceptance

Local evidence: 102 standalone client/framing tests and 33 real HA 2026.10.1 tests
pass, with external sockets disabled in the HA suite. Coverage includes the
10-second schedule, option-save reload, scoped mapping, malformed metadata,
connection failure/recovery, retained success timestamps, error-code behavior,
Celsius/mm on imperial hosts, shared on-demand media, bounded frame parsing,
media failure/retry, proxy output and cleanup. Lint, format, typing and builds
are checked locally; hosted Actions remains disabled.

Pending live checks: approve the custom update and HA restart; verify all 49 Pro
entities, manual mappings, 10-second timestamps, camera viewing/closing/reopening,
no credential/URL leakage in diagnostics and component log health. Confirm physical
nozzle order and camera illumination separately. No print is interrupted to test
these features. Lifetime counters, notifications, job-name/thumbnail reporting,
bed mesh and additional controls remain outside this update.

References (framework/protocol facts only; original implementation):
- [HA camera entities](https://developers.home-assistant.io/docs/core/entity/camera/)
- [HA MJPEG integration](https://www.home-assistant.io/integrations/mjpeg/)
- [HA options flow](https://developers.home-assistant.io/docs/core/integration/options_flow/)
- [Creator 5 protocol](https://github.com/Parallel-7/flashforge-api-docs/wiki/Creator-5-Series)
