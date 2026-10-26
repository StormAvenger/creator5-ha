# Setup, print summaries and reminders — 0.6.0

## Create a dashboard

After updating through HACS and restarting HA, open **Creator 5 tools** from the
integration's Configure form while signed in as an administrator. The optional
**Show Creator 5 tools in the sidebar** preference defaults to off. Select a
configured printer, choose a dashboard title/address and optional sidebar checkbox,
then click **Create dashboard**. Existing dashboards and their visibility are unchanged.

The new native dashboard has Printer and Materials views, using the selected
printer's actual entity IDs. Renamed entities are supported and disabled entities
are omitted. Materials are grouped into four slots with native color swatches.
Enabled controls, temperatures, the camera, last-print details and maintenance
records are included. Camera viewing still uses the existing on-demand entity.

The dashboard is a normal editable HA dashboard. Creation never replaces another
dashboard. If the address is already taken, choose another. Later integration
updates do not rewrite your cards. Controls enabled after creation can be added
using HA's card editor, or included by creating another dashboard at a new address.

The admin setup page is separate from the dashboard. If its usual sidebar address
is occupied, the integration uses an available suffix and preserves the existing panel.
Headless HA installations keep monitoring without loading a frontend.

## Choose notifications

On **Creator 5 tools**, choose **Home Assistant notifications** or a registered
HA Companion App phone, select the desired events, and click **Create alerts**.

| Event | Behavior |
| --- | --- |
| Print completed | Once when a tracked job reaches the printer's completed state |
| Bed cooled | Once after that completion, when the bed is below the configured Celsius threshold and its target is off |
| Printer error | Once for a newly observed error/code; unchanged errors do not repeat |
| Prolonged pause | Once after a continuous pause reaches the configured delay |
| Connection lost | Once after a continuous outage reaches the configured delay |
| Maintenance due | Once when a configured reminder crosses its printing-hours interval |

No alerts are created during installation or by saving Configure options. Creating
alerts explicitly adds an editable native automation. Existing automations are
preserved; an existing Creator 5 alert automation is detected rather than replaced.
New automations use unique IDs. Edit/disable/delete them under **Settings →
Automations & scenes**. Generated alerts send messages only; no printer commands,
completion acknowledgement, snapshots or recordings are attached. Filenames are
excluded from notifications.

The defaults are a 10-minute prolonged pause and a 2-minute connection outage.
Change them in the integration's **Configure** form. Startup/reload does not replay
past completion/error/reminder events. Alert timers begin fresh after reload, and
brief disconnects that recover before the delay do not notify. Events follow the
existing poll interval, so detection is not instantaneous.

## Last-print summary

The **Last print** sensor retains one most recent result: completed, cancelled or
unconfirmed. Attributes include filename, the reported elapsed duration, inferred
start time, completion-observed time and an incomplete-observation flag. The
created dashboard displays these details without needing custom cards.

HA records this summary from observed transitions; the printer is not queried for
a historical job log. Already-running jobs, missed updates, HA restarts during a
job and unobserved job transitions are marked incomplete. Returning to ready without
an observed completion is unconfirmed, never assumed successful. The last active
elapsed reading is retained when firmware resets its timer on completion; it may
lag the finish by a poll interval. Completion time is when HA observed the outcome,
not a timestamp supplied by the printer. Heating/error states do not by themselves
mean a job finished.

The summary survives integration reloads and remains readable while the printer
is offline. Only one previous job is retained; there is no growing job-history database.

## Bed-cooled indicator

**Bed cooled after print** is unknown before a tracked completion, then follows
the bed reading and target. The default threshold is strictly below 40 °C,
configurable from 20–70 °C. A missing/invalid reading is unknown, and a nonzero
bed target prevents an on state. Starting a new job clears the prior completion.
The notification fires only once per completion even if the bed is later reheated
and cools again. This reports the bed only, not the temperature or safety of the
nozzles, chamber or printed object.

## Maintenance reminders

Under **Configure**, set a printing-hours interval for bed cleaning, rail lubrication
and nozzle inspection. Each starts at **0 (disabled)**. The values are your own
reminder preferences, not manufacturer-prescribed service intervals.

Enabling an interval begins tracking from the current reported lifetime printing
hours; it does not claim maintenance was performed. After doing the work, press
**Record bed cleaning**, **Record rail lubrication** or **Record nozzle inspection**
on the device page or created dashboard. This records the date/current counter
and resets that reminder locally. No printer command or extra status request is sent.

Remaining hours and due indicators are available as entities. Unknown lifetime data
makes remaining/due unknown. A printer lifetime-counter rollback invalidates existing
baselines rather than inventing usage; record the next actual service to restart
tracking. Records and baselines survive reloads.

## Error explanations

The existing raw, format-validated error code remains available. A separate
**Error explanation** sensor adds original plain-language summaries for selected
codes in FlashForge's [Creator 5 error reference](https://wiki.flashforge.com/en/creator-series/creator-5-series/error_code_creator_5).
The supported set covers filament interruption/clog detection, rejected files,
model mismatch, tool pickup, nozzle heating/file-validation checks and bed/chamber
heating faults. The vendor lists multiple possible causes for some codes; hints
are checks, not remote diagnoses. Unknown codes remain visible with a reference
link; meanings from other printer families are not guessed. No error-clearing or
recovery command is sent.

## Local data and permissions

Job/maintenance state is stored with HA's storage helper under an entry-specific
`creator5.<entry_id>.history` key. It contains a bounded filename and selected job
metadata, not the printer's raw response or credentials. Writes are throttled and
pending changes flush on unload. Integration removal deletes its own storage file;
HA Recorder retention, existing dashboards/automations and backups are independent.
Filenames/summary records never enter integration diagnostics. Normal HA history
and authorized household users may still see the entities' attributes.

The setup helpers require an authenticated administrator. The frontend is bundled
with the integration, uses HA's authenticated dashboard/automation editor APIs,
and loads no third-party scripts. It contains no printer address or credentials.
These additions use the existing status poll and send no new printer commands.
