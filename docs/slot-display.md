# Slot colors and grouped dashboard (0.3.1)

Four native HA image entities render the exact validated RGB material colors as
local PNG swatches. No external images, assets, files, frontend plugins or printer
requests are needed. The image refresh timestamp changes only when its color does.
Missing/invalid colors and disconnected status are unavailable, not a guessed color.
This is the configured/reported filament color, not a measured physical shade.

Existing slot-color sensor IDs and hex states are preserved for automations but
categorized as diagnostic details. Their previous entity-registry customization,
if any, takes precedence. The separate last-success timestamp is disabled by
default for fresh installs; existing explicit enable/disable choices are preserved.
There are 53 registered Pro entities, with 52 enabled by default (camera enabled).

The standard HA device page is an entity inventory; it has no integration-defined
slot sections. Use the original, native-card example in
[dashboards/material-slots.yaml](../dashboards/material-slots.yaml) for a two-column
four-slot group. Each slot shows its swatch, reported material and filament presence,
plus nozzle diameter and user note for tools actually mapped to that slot. No
identity mapping is assumed; assign mappings in the integration's options first.
Change example entity IDs if HA assigned a different device prefix. Unknown or
unassigned tools are not given a fabricated nozzle size.

This dashboard contains no control actions. Swatch taps are disabled, and material
cards are display-only. The camera and light remain separate existing entities.
The owner selected GPLv3 (GPL-3.0-only); the project is available as a public HACS custom repository.

Validation: 102 client tests and 35 real HA 2026.10.1 tests pass locally with external
HA sockets blocked. The new fresh-entry test checks exact decoded PNG pixels,
invalid/missing colors, unchanged-color timestamps, no extra status reads,
disabled-by-default timestamp registration and unload cleanup. The same 35 tests also pass from a clean temporary source directory with no
existing HA config entry or owner credentials. This validates clean source setup
against the installed HA test environment, not a fresh HA OS appliance. Live acceptance on 2026-10-14: after the owner specifically approved the update,
HA configuration validation passed and Core restarted while the printer reported
ready, with no automations/scripts running. HA loaded 0.3.1 and all four local
swatches. Diagnostics confirm successful status reads at 10 seconds with no actual
printer serial, check code or LAN address. The timestamp entity stays disabled.
Filtered component logs showed no creator5 issues.

A new Creator 5 sidebar dashboard groups four slot cards. It displays black PETG-CF
with tool 1 / 0.6 mm; black PETG with tool 2 / 0.4 mm; silver PETG with tool 3 /
0.4 mm and the user-supplied high-flow material note; and black PLA with tool 4 /
0.4 mm. These are API readings plus configured mappings, not fresh physical checks.
The reusable full dashboard is [dashboards/creator5.yaml](../dashboards/creator5.yaml).
No printer controls were sent.
