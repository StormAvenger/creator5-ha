# Job monitoring (0.3.4)

Five additional entities share the existing 10-second status coordinator:

| Entity | Meaning |
| --- | --- |
| Current print filename | A bounded filename while printing or paused; unknown otherwise |
| Estimated finish time | UTC timestamp calculated from the printer's remaining seconds while printing |
| Reported lifetime printing time | Printer cumulative minutes converted to hours |
| Reported free storage | Printer's reported free space in GB |
| Current print thumbnail | On-demand PNG/JPEG of the current job, proxied by HA |

Finish time is unknown while paused, heating, idle, completed or in error. Identical
remaining/progress/layer reports retain the previous estimate rather than moving it
forward every poll. A changed estimate/progress/layer, new job, or resumed print
recalculates it. Disconnection makes entities unavailable and clears the old ETA.
This is a firmware estimate, not a promise of completion time.

Lifetime and storage units follow the Creator 5 Pro 1.9.4 observations documented
by [Creator 5 Pro Dashboard](https://github.com/afeind/Creator-5-Pro-Dashboard#detail-field-quirks):
`cumulativePrintTime` is minutes and `remainingDiskSpace` is GB. Those fields exist
in the owner's privately cached 1.9.9 status. Physical display comparison on 1.9.9
is still pending; values are explicitly labeled reported. Missing, malformed,
negative and nonfinite values remain unknown. Runtime uses HA's total-increasing
statistics semantics, which treats a counter decrease as a reset. It is the
printer's counter, not time independently measured by the integration.

The saved status thumbnail reference points to `/getThum` on the printer API port.
An original bounded reader uses that fixed endpoint on the configured printer,
not the reported URL. It sends no credentials, follows no redirects and accepts
only PNG/JPEG signatures up to 2 MiB with an eight-second timeout. No camera or
control commands are involved. Requests occur only when HA requests the image;
concurrent viewers share one cache, and attempts are limited to once per minute
per job. A job change clears the image, and late responses for older jobs are
rejected. The in-memory cache is cleared on unload; nothing is saved to disk.

The fixed current-job endpoint cannot independently prove the image matches the
filename; its accuracy remains dependent on printer firmware. Live thumbnail
compatibility on this owner's firmware has not yet been verified. A failed image
request does not mark the status coordinator disconnected or stop its polling.

Filenames are intentionally visible as HA entity states and may be retained in HA
history. Thumbnail image bytes remain in memory. Neither filenames, image bytes,
reported URLs nor printer identifiers are added to integration diagnostics. Review
HA backups, dashboards and screenshots before sharing them publicly.

[Job card example](../dashboards/job-overview.yaml) uses native cards and contains
no controls. Adjust entity IDs if your device uses a different prefix. Adding this
example to an existing dashboard is optional; upgrading does not edit dashboards.

Research uses protocol facts only; no third-party implementation was copied.
No live print, heater, fan, light, motion or material commands are needed to test
these features. Live thumbnail validation and an idle-only HA restart require the
owner's specific activation approval. Base Creator 5 remains hardware-unverified.
