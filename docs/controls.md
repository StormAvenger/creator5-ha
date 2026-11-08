# Optional controls and extended telemetry — 0.6.0

Experimental. Only Creator 5 Pro has physical monitoring tests. The controls below
are implemented from documented LAN protocol facts and synthetic tests; they are
**not yet hardware-validated**, including on firmware 2.0.0. Development does not
send commands to a printer. Acknowledgements alone do not prove firmware support.

## Enable the groups you want

Open **Settings → Devices & services → Creator 5 → Configure**. Four new groups
start off, including for existing installations. Enable only the groups you want;
saving options and restarting the integration send no commands. Ordinary HA
buttons, number fields, dropdowns and a switch then appear on the device.

| Group | Controls | When available |
| --- | --- | --- |
| Job controls | Pause, resume, acknowledge completed print | Pause while printing; resume while paused; acknowledge only while completed |
| Material metadata | Material and named palette color per slot | Ready only; does not load/unload filament or change tool mapping |
| Printer settings | Speed override; auto-shutdown switch and delay | Speed while printing; shutdown configuration only while ready |
| Temperature targets | Bed, four nozzles, Pro chamber | Ready, printing or paused; no chamber control for non-Pro |

**Completion acknowledgement tells the printer the platform has been cleared**; it
cannot check that the object was physically removed. It never starts another print.
By default it only happens when you press the button (or your own automation does).

### Automatic dismissal of the print-complete screen (optional, off by default)

Enable **Automatically dismiss the print-complete screen** in Configure and choose
the delay (1–240 minutes, default 10). Separate from the job-controls group.

- The countdown starts when the printer shows its completed screen (including when
  HA first sees a printer already sitting on it). After the delay, one acknowledgement
  is sent; the printer must still report completed, and the result is verified.
- Pressing the button yourself, or starting a new print, cancels the countdown.
- A failed or unconfirmed attempt is never retried for that print; the screen stays
  until you press it. If the printer is offline when the delay ends, nothing is sent
  and a fresh countdown starts once it is seen on the completed screen again.

**Trade-off:** that screen is the printer's check that the bed is clear. While it
shows, a new job can't start. Once it's dismissed, a print sent remotely (slicer,
vendor app, or this integration's reprint) could start on top of a part left on the
bed. Starting the next print at the printer yourself is unaffected. Choose a delay
long enough that you'd normally have removed the part.

## Limits and behavior

- Speed: 50–150%, a conservative subset of the documented API. This is a multiplier,
  not measured motion speed in mm/s. It may affect print quality.
- Targets: bed 0–120 °C, nozzles 0–320 °C, Pro chamber 0–65 °C. Zero means off.
  These are input ceilings, not recommended temperatures for every material.
  Chamber is capped at the manufacturer's published 65 °C limit, even though the
  community protocol page describes a higher API limit.
- Target fields stay in Celsius on Fahrenheit-configured HA installations.
  They intentionally have no temperature number device class because that would
  automatically convert their display/input to household units. Temperature sensors
  keep their existing Celsius preference and temperature device class.
- Only the requested heater changes. Every nozzle command has exactly four array
  values; untouched heaters use the documented no-change sentinel. Scalar bed/chamber
  off values differ from nozzle off values, and are tested separately.
- Auto-shutdown delay: 1–120 minutes. Set a valid delay before enabling if the
  printer reports zero/unknown. Editing one setting preserves the other from fresh
  status. The integration has no direct power-off control. Enabling auto-shutdown
  schedules the printer's own shutdown after a later print completes.
- Slot edits accept the documented 21 material names and 24 exact palette colors.
  Newer materials remain readable but cannot be written until their exact palette
  values are verified. A partial edit requires the other reported field to be
  supported; unknown fields are never replaced with defaults.
- Every new control checks fresh model/state, sends one named command, and verifies
  the result through at most three status reads. Pending transitions may take longer
  than the verification window; check the printer instead of repeatedly retrying.
- Commands and polling are serialized. A timeout does not trigger another command
  or an alternative command name. A failed response leaves the outcome uncertain;
  a matching reported state is required before publishing a changed snapshot.
- Version 0.6.0 adds a separate, default-off file-actions preference for confirmed
  uploads, reprints and cancellation in the admin tools page. These actions do not
  expose an unconfirmed button/service to automations. See [file tools](files.md).
- No motion, extrusion, filament loading, Z-offset adjustment, fan control, firmware
  management or arbitrary-command service is included.

## New readouts

| Reading | Meaning and caveat |
| --- | --- |
| Reported lifetime filament | Cumulative metres across all tools, based on community observations; not remaining spool weight |
| Print speed multiplier | `printSpeedAdjust`, percent; not instantaneous linear speed |
| Z offset | Reported signed `zAxisCompensation`, millimetres; read only |
| Reported auto shutdown and delay | Current setting and minutes; unknown if absent/invalid |
| Reported material station slot/loading slot | Station's slot numbers, 0 = no reported slot; not the active tool |

Station action/step codes are numeric attributes with unverified meanings. The
integration does not label arbitrary codes as loading, unloading or printing.
Absent, malformed or out-of-range data stays unknown. All readings share the
existing status poll; they do not create extra per-entity polling.

Current/total layers and progress now have measurement state classes. HA's native
Activity filtering suppresses continuous sensor updates while Recorder history and
readings remain available. Past events are not purged. The optional last-success
entity remains disabled by default; existing preferences are retained.

## Chamber light

`lightControl_cmd` switches the chamber LED and is verified by status readback. The
owner confirms it works on firmware 2.0.0; earlier timeouts were a local Wi-Fi issue.
Command-request and status-verification failures are reported as separate stages in
cached diagnostics, and polling never overlaps a control request.

## Sources

Protocol facts: [Creator 5 reference](https://github.com/Parallel-7/flashforge-api-docs/wiki/Creator-5-Series),
[HTTP commands](https://github.com/Parallel-7/flashforge-api-docs/wiki/HTTP-REST-API),
[Creator 5 palette](https://github.com/Parallel-7/flashforge-api-docs/wiki/Creator-5-Filament-Palette).
Hardware ceilings: [FlashForge Creator 5 Pro specifications](https://www.flashforge.com/products/flashforge-creator-5-pro).
Lifetime units: [community field observations](https://github.com/afeind/Creator-5-Pro-Dashboard#detail-field-quirks).
Implementations/tests are original; no third-party code or firmware was copied.
