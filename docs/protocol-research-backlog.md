# Future protocol research

These are research questions, not enabled features or claims of firmware support.
Version 0.6.0 uses documented stock LAN endpoints only. No live probing, packet
capture, firmware inspection or modification was performed for this release.

## Questions worth investigating

1. Compare documented command behavior with firmware 2.0.0, particularly the light
   timeout and any differences in acknowledgement versus actual state changes.
2. Establish whether fan requests are ineffective as the Creator 5 reference says,
   or whether a newer stock API exposes a verified, distinct control path.
3. Look for a reliable, explicit active-tool signal and per-tool filament usage.
4. Look for authenticated bed-mesh export and richer calibration status.
5. Check whether file metadata, full listings, stable job IDs or a supported
   material-matching endpoint have been added. Do not infer requirements from names.
6. Investigate accessory/drying-station telemetry only if relevant hardware and
   a stock LAN interface are available.
7. Verify base-model differences with volunteer hardware reports and sanitized fixtures.

## Method and boundaries

Start with public vendor documentation/release notes, published protocol facts and
community issue reports. Check provenance and licenses before including material.
If public facts are insufficient, propose narrow observations of the owner's
normal authenticated vendor-app traffic on the owner's device, with separate
permission and a deliberate idle/test-job session. Limit capture to that equipment;
never include unrelated network traffic. Keep raw captures, identifiers, codes and
proprietary content private; publish only original protocol descriptions and fully
synthetic fixtures after review.

Do not bypass authentication, intercept third-party accounts, root/modify firmware,
enable hidden services, decompile proprietary firmware, fuzz an active printer,
or expose arbitrary G-code/command forwarding. Unknown or no-op commands remain
unsupported until behavior and state/readback checks are established. Broader
methods or changed legal/contractual questions require a separate review rather
than assuming this project authorizes them.

See [development scope and provenance](legal-and-sources.md),
[Creator 5 reference](https://github.com/Parallel-7/flashforge-api-docs/wiki/Creator-5-Series)
and [HTTP reference](https://github.com/Parallel-7/flashforge-api-docs/wiki/HTTP-REST-API).
