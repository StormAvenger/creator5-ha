# Home Assistant development and validation

For normal installation, use the [no-YAML installation guide](install.md).
The 0.3.2 candidate adds HACS metadata/local artwork and an IP/LAN-code setup form.
The user's existing 0.3.1 installation has already validated shared status polling,
camera viewing, slot swatches and the grouped material dashboard on HA 2026.10.1.
Do not confuse that live evidence with candidate or base-model acceptance.

## Runtime checks

Use a separate Python 3.14 environment for HA's pinned dependencies, apart from
the standalone client environment. Install requirements-ha-test.txt and the
repository locally, then run:

```sh
python -m pytest tests/ha --disable-socket --allow-unix-socket
```

Tests run actual HA config-entry, entity, coordinator, template and option code
with synthetic printer I/O. Unix sockets are allowed only for the event loop;
external sockets are blocked. The current suite covers two-field setup, targeted
identity lookup, both supported model IDs, model conflicts, credential rejection,
no discovery for invalid addresses/empty codes, duplicates, reauthentication,
Pro-only capability filtering, Celsius/mm, shared 10-second polling, updates,
connection loss/recovery, on-demand camera, exact local PNG colors and cleanup.
No hardware support claim should be inferred from a synthetic fixture alone.

Tests also run from a clean temporary source directory with a fresh mock config
entry and no owner's credentials. That verifies source setup/packaging boundaries,
not a new physical HA OS appliance. A real base Creator 5 has not been tested.

## Existing entries and privacy

Existing config entries keep their saved serial, LAN code, mappings and explicit
entity enable/disable choices. No serial migration or re-entry is needed. New
setup obtains serial automatically from one directed UDP request to the entered
private IPv4 address; no subnet scan, broadcast or multicast is used. Credentials
are sent only after supported discovery identification and checked against normal
status. Model identity must agree between discovery and authenticated status.

Diagnostics are built from cached numeric readings, update success/timestamp and
control capability. They omit config-entry data, raw responses, printer IP, serial,
LAN code, filenames, free-form strings and source URLs. Requests do not contact
the printer. HA can add surrounding system metadata; review the whole download
before sharing. Credentials and backups stored by HA must remain private.

## Distribution and limitations

HACS metadata and local original brand images are supplied. All runtime code is
inside custom_components/creator5, with no unpublished external client dependency.
The standalone creator5py package is exported from the same canonical client code.
Release checks run locally; do not enable hosted Actions or other paid services.
HACS download acceptance requires a public repo and a validated release/default
branch, and is separate from local packaging validation. Keep visibility private
until the owner's explicit publication decision.

The Pro has 53 registered entities, 52 enabled by default. Base/unknown model
setups omit door/lid, chamber temperature/target and chamber-fan entities; base has
49 registered/48 enabled by default when camera is enabled. Unknown/conflicting
models cannot be newly added. No guessed zero represents missing data. The only
write method is chamber-light on/off; no print, heater, fan, motion, firmware,
upload or material controls are implemented.

The optional slot dashboard remains separate from ordinary integration setup.
HACS does not install it automatically. See [slot display](slot-display.md) for
examples and live 0.3.1 evidence. Physical display comparisons, idle-only printer
network recovery and earlier brief camera availability transitions remain open.

## Unload and rollback

Remove this printer's config entry in Devices & services to stop its coordinator
and unload its entities. Tests verify polling stops after unload. Do not shut down
or alter a printing device to test removal. A private source rollback archive is
retained outside the repository for the owner's installed version. Do not change
other components or expose the HA configuration directory.
