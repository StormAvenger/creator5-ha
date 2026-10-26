# Printer files and confirmed actions — 0.6.0

Experimental; use at your own risk. The implementation is tested with synthetic
responses and a loopback mock printer. It has not been physically validated on
firmware 2.0.0 or on a standard Creator 5.

## Open the tools

1. Sign into Home Assistant as an administrator.
2. Open **Settings → Devices & services → Creator 5 → Configure**.
3. Follow **Creator 5 tools**. Optionally enable **Show Creator 5 tools in the sidebar**.

The shortcut is off by default, including when upgrading from 0.5.0. It affects
only the integration's tools page. Existing dashboards and their sidebar settings
are preserved. With multiple printers, enabling the preference for any configured,
enabled entry shows one shared shortcut. The tools page remains admin-only.

## Browse and preview

Select a printer and click **Refresh files**. This reads the printer's reported
recent-file list; it is not a complete filesystem browser and older files may be
omitted. Select a file and click **Show preview** for its thumbnail. Missing or
unsupported thumbnails do not prevent a listed file from being selected.

Reading files/previews never uploads or starts anything and needs no file-action
opt-in. Reads happen on request, not every status poll. Filenames and previews stay
in the authenticated tools session; they are not added to diagnostics or alerts.

## Enable actions

Enable **file uploads, reprints and cancellation** in Configure. This is separate
from the existing pause/resume group and starts off for new and upgraded entries.
Saving the preference sends no printer command. Reopen the tools page after changing
preferences; the backend checks current permissions for every action regardless.

Each write requires an explicit confirmation prepared for that administrator,
printer and exact action. A confirmation expires after 60 seconds and can be used
only once. Failed or timed-out writes are never retried automatically. Check the
printer and refresh the file list before deciding whether to retry yourself.

### Upload only

Choose a trusted sliced `.3mf` or `.gcode`, then **Upload only…** and confirm.

- Maximum 64 MiB. Unsliced 3MF models, invalid archives, archive path traversal,
  encrypted entries and excessive expanded data are rejected. Archive contents
  are validated without being extracted on HA. This does not establish that the
  slice is correct or physically safe for your printer, nozzles or materials.
- HA temporarily spools the upload to a private temporary file and removes it on
  success, validation failure or disconnect. The source file on your computer is unchanged.
- The printer receives a unique filename based on the original name, protecting
  existing files from ordinary name collisions. The verified stored name is shown.
- Upload requires a fresh **ready** state. It always sends `printNow: false` and
  never includes material mappings, avoiding the documented retained-mapping hazard.
- No print follows an upload automatically. Refresh the list to select the new file.
  Upload acceptance without a matching list entry is reported as unconfirmed.

### Start / reprint

Select an existing sliced file and click **Start / reprint selected file…**.
Before confirming, physically clear the bed and verify printer model, nozzle sizes,
and that the material in each numbered slot matches the slicer filament number:
filament 1 → slot 1, filament 2 → slot 2, etc.

**Previous custom material mappings are not restored.** The stock file list reports
no per-tool material requirements. Version 0.6.0 sends no guessed mappings; the
printer uses its slicer-numbered default assignments. HA's manual tool notes and
monitoring assignments do not change those defaults. If the file requires custom
mappings or you cannot establish its requirements, start it using the vendor's
software instead. The UI states this limitation before confirmation.

Starting requires fresh ready status and file-list membership. Automatic leveling
is always requested. No completion dialog is dismissed automatically. A start
acknowledgement is checked against a matching active filename; slow transitions or
firmware naming differences can leave the result unconfirmed. Inspect the printer
before retrying. There is no scheduled queue or unattended restart.

### Cancel

Click **Cancel current print…**. The confirmation names the current reported job,
regardless of which file is selected in the browser. Cancellation requires a fresh
active/paused state, matching filename and plausible continuing elapsed time. It
sends one cancel command and checks for a cancelled/ready state. A transition taking
longer than the verification window is reported as unconfirmed.

The stock command has no atomic job identifier. Filename/elapsed checks reduce
stale-job mistakes but cannot guarantee identity in every external stop/restart
race. Review the current printer before confirming. The cancellation dialog is
not automatically cleared. No unconfirmed cancel entity or generic command service
is exposed for automations in this version.

## Validation still needed

With a deliberately chosen test job and the owner's approval: verify file listing,
one thumbnail, upload-only and reported filename, compatible-material reprint,
confirmation decline/expiry, cancellation, and state transitions on each firmware.
Do not use a valuable running print as a cancellation test. No such live acceptance
was performed during development.

Protocol references: [Creator 5 file behavior](https://github.com/Parallel-7/flashforge-api-docs/wiki/Creator-5-Series)
and [HTTP file endpoints](https://github.com/Parallel-7/flashforge-api-docs/wiki/HTTP-REST-API).
Original code/tests only; no vendor implementation or firmware was copied.
