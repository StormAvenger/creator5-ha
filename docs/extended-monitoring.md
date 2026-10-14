# Extended monitoring and chamber light — version 0.2.0

Status: implemented and tested locally; not installed on the live HA host yet.
The host still runs 0.1.0 with 13 read-only sensors. Its ten temperature entities
were individually changed to Celsius on 2026-10-14 without changing household units.
No light command has been sent to the owner's printer by this project.

## Prepared entities

Version 0.2.0 provides 24 sensors, four filament-presence binary sensors, one
Pro-only door/lid binary sensor and one chamber-light entity: 30 entities on the Pro.
The base Creator 5 omits the door/lid entity. All readings share one 30-second
status poll; adding entities does not add independent requests.

| Addition | Interpretation |
| --- | --- |
| Bed/chamber targets | Reported targets; a zero remains zero |
| Elapsed time, current/total layers | Values from the current job; missing/invalid values are unknown |
| Four slot materials and colors | Configured slot metadata, not automatic polymer identification |
| Four filament-presence signals | Explicit per-slot boolean; missing is unknown |
| Door or lid | Pro combined signal; cannot distinguish front door from top lid |
| Reported chamber/cooling fan percentages | Reported 0–100 values; not measured airflow or a separate exhaust signal |
| Chamber light | On/off only, with reported state and verified command readback |

Material slots are selected by their IDs, not their array positions. Duplicate or
malformed slot IDs fail closed to unknown. Colors must be six-digit hex strings;
material labels are bounded text. No raw station data is exposed. Do not infer the
active tool/material from currentSlot: that correspondence remains unverified.
The API's internal/external fan flags and TVOC field are not exposed as useful
readings, given the model-specific fixed-value caveats in the community reference.

Protocol references: [Creator 5 series](https://github.com/Parallel-7/flashforge-api-docs/wiki/Creator-5-Series)
and [HTTP fields/light command](https://github.com/Parallel-7/flashforge-api-docs/wiki/HTTP-REST-API).
These are community observations; cached owner data confirms the fields exist but
has not established display accuracy or physical light actuation on this firmware.
Implementation and synthetic tests are original; no source/schema was copied.

## Celsius behavior

Every temperature sensor supplies Celsius as its native and suggested display unit.
This overrides HA's household Fahrenheit default for new entities. HA still allows
an owner to override an individual sensor's unit explicitly; the integration does
not fight that setting. The one-time minor-version migration changes old automatic
units for this integration's temperature entities only and preserves explicit
per-entity overrides. Other devices and the global unit system are unchanged.

[HA's supported unit behavior](https://developers.home-assistant.io/docs/core/entity/sensor/)
provides this capability without removing the temperature device class or inventing
nonstandard units. Tests cover a Fahrenheit host, 12 Celsius entities and an old
registry entry, including preservation of unrelated devices and explicit overrides.

## Light control boundary

The only public write operation is set_light(bool). It sends a chamber LED
open/close payload to the normal authenticated control endpoint, then reads status
once. A success acknowledgement alone is insufficient: missing or mismatched
lightStatus raises a safe error. The verified snapshot updates all entity caches.
Setup, normal polling, diagnostics and unit migration never send a write command.
There is no arbitrary-command service, print control, heater control, fan control,
upload, motion, material configuration or camera command.

Diagnostics remain cache-only and omit credentials/identifiers/raw strings. Version
0.2.0 correctly reports read_only=false and control_scope=chamber_light_only;
this describes capability, not a record of commands being sent.

## Activation and acceptance

1. Obtain action-time approval to install/run this custom version and restart HA Core.
2. Preserve a rollback copy of 0.1.0, then replace only this component's files.
3. Load the new code and verify the Pro's 30 entities, Celsius units and status updates.
4. With the user's approval, observe the light, toggle it off/on once and restore
   the original state. Check both status readback and physical illumination.
5. Compare door/lid state and slot metadata with the printer display. Do not open
   doors, change power/network settings or manufacture faults during a running print.
6. Keep print completion and natural reconnect acceptance separate from simulated tests.

Local verification: 83 client tests and 14 real HA 2026.10.1 tests pass with no
external sockets in the HA suite. Tests cover request boundaries, ACK-without-effect,
unknown fields, slot parsing, shared polling, Celsius and LED-only HA services.
Lint, formatting, typing and source/wheel builds pass. Hosted Actions remains disabled.
