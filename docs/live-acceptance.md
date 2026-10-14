# Live Home Assistant acceptance

Session: 2026-10-14. Experimental version 0.1.0, owner-authorized installation.

## Observed results

- HA Core 2026.10.1, Supervisor 2026.09.3, HA OS 18.3, frontend 20260930.3.
- The previously staged component appeared in Add integration. No HA restart,
  HA upgrade, printer restart or printer settings change was performed.
- Normal setup with the owner's supplied LAN credentials authenticated successfully.
  Credentials are saved in HA's config entry, never in the repository.
- One Creator 5 device and 13 available sensor entities appeared. No control
  entities, services, automations, scripts or scenes were added.
- The printer reported printing. Progress advanced from approximately 47.47% to
  49.11% and subsequently 52.52%; remaining time changed from 1,072 to 1,042 and
  then 982 seconds during scheduled refreshes. These are historical observations,
  not a current print-status guarantee.
- Cached diagnostics reported read-only mode and successful update. Their readings
  included bed 69 °C, chamber 31 °C, tools [31, 31, 250, 34] °C and targets
  [0, 0, 250, 0] °C. Values are examples from one moment, not fixed expectations.
- The entire downloaded diagnostics file was checked for the supplied LAN code,
  printer serial and printer IP; none were present. The component section contains
  only allowlisted cached numeric readings, read-only mode and update success.
  HA's surrounding system/component metadata remains private and should be
  reviewed before sharing. The raw download is outside Git.
- HA Core logs filtered to `creator5` showed no issues at the time of inspection.
  This is a point-in-time UI check, not proof that all future log paths are private.
- All 13 live state-attribute views were inspected without editing. They contain
  only friendly names, units and device classes; no raw payload, supplied code,
  printer serial or printer IP was found.
- Eleven real HA runtime tests passed against 2026.10.1 with external sockets
  disabled, using framework 0.13.372. The earlier 2026.10.0 baseline also passed.

## Display behavior

The host uses Fahrenheit. HA converts the component's Celsius readings for display;
for example 250 °C appears as 482 °F. A reported zero target appears as 32 °F.
These sensor entities cannot change a heater target. Four-tool numbering follows
the API array order; physical tool/display correspondence is still unverified.
Progress currently retains the API's precision and remaining time is displayed in
seconds. Display polish can be addressed after the compatibility checks.

## Acceptance still required

- Compare temperatures, tool numbering, progress and remaining time to the printer display.
- Verify the complete firmware build; the earlier direct API read reported only 1.9.9.
- Observe idle, ordinary print completion and a full normal print without controls.
- Observe a naturally occurring disconnect/recovery. Do not interrupt a running
  print or change network/power settings merely to manufacture this test.
- Validate live reload/restart, removal and changed credentials when appropriate;
  these behaviors currently have offline test coverage only.
- Recheck privacy on future failure paths; successful live attribute and log
  inspection does not replace review of new code or different failures.
- Recreate the portable checkout on the intended Ubuntu environment.

Keep the repo private until license/provenance review, historical-email cleanup,
owner publication approval and release validation are complete. Actions remains
disabled; no paid GitHub services were enabled for this session.
