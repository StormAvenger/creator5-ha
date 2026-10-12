# Resume with the printer

On 2026-10-11 the user resumed local access while the printer is printing.
The supplied API port accepts a TCP connection from the Mac; device identity and
authenticated status initially remained unverified.
The corrected reported stock firmware is `1.9.9-1.3.0`.

Protect the current print: no pause, stop, resume, temperature changes, uploads,
reboots, firmware changes or printer settings changes. The owner subsequently
authorized HA installation and read-only monitoring during the print. The first authenticated
probe remains one status request, without automatic retries. Enter credentials locally only
after confirming the supplied address belongs to this printer.

1. Without changing the current print, confirm the display's current IP, LAN mode and exact
   stock firmware version. Verify the supplied address still belongs to this printer.
2. The latest TCP-only check succeeded; the earlier port-8898 connection timed out.
   Check routing, VPN and VLAN/firewall rules before changing printer settings.
3. Run `Probe printer.command` in macOS Terminal (or `.venv/bin/creator5-probe`
   from the repository). With `CREATOR5_SERIAL` absent, the CLI sends one targeted
   discovery packet to that address and uses the validated Creator 5 serial locally.
   Enter the check code at the hidden prompt. Credentials need not be saved in `.env`.
4. Compare the sanitized state and temperature readings with the display.
5. Share only the summary and a description of any mismatch. Do not send the check
   code, serial, camera URL, registration tokens or raw response to chat/GitHub.
6. If we need more fields, inspect the response locally and create a synthetic
   fixture with the same structure. Review it before committing.
7. Record the verified firmware/field behavior and proceed to development HA setup.

## Remote access options

- **Tailscale:** an existing approved subnet route covering the printer's LAN IP
  can let the Mac use the same one-shot probe. Access to HA's own Tailscale address
  alone does not establish access to the printer. See [subnet routers](https://tailscale.com/docs/features/subnet-routers).
- **WiFiman Teleport:** an active VPN connection can provide home-network access;
  verify the specific printer address and VLAN/firewall permissions. See [Teleport](https://help.ui.com/hc/en-us/articles/5246403561495-UniFi-Gateway-Teleport-VPN).
- **Home Assistant Cloud:** provides remote HA access. A probe could run from an
  already-authorized terminal on the HA host if it can reach the printer; the cloud
  HA URL is not a general LAN tunnel. See [remote access](https://support.nabucasa.com/hc/en-us/sections/26496346499997).

Inspect existing access first. New subnet routes, firewall permissions, terminal
installation or changes to production HA need a concrete scope before making changes.
Remote inspection confirmed HA Core 2026.9.4, HA OS 18.3 and an existing running
Terminal & SSH app. Python is absent from that app. Its TCP check found a service
listening on port 8898 at the supplied address, but did not identify the device
or send authentication. The printer was subsequently reported off.
Keep code entry local to the trusted client/HA session and restrict output to the
sanitized status summary. No public printer endpoint is needed.

Normal CLI invocation uses one `POST /detail` status read, with a timeout and no retry.
No control/upload endpoint, discovery scan, capture, firmware change or cloud service
is needed. Later behavior testing should observe a print the user starts normally.

## Latest session evidence — 2026-10-11

One directed UDP packet to the owner-confirmed target on port 48899 returned the
expected FlashForge vendor, Creator 5 Pro PID 41 and HTTP port 8898. The serial was
retained privately outside Git. This normal discovery does not send a control command.
The authenticated status read was rejected; one manual diagnostic read of the same
endpoint confirmed HTTP 200 with application code 1 and no detail. Both used the
same supplied credentials; no code variations were tried. A preceding local import
failure sent no network request. At that point authentication was held until the
owner verified the exact LAN code; no variants or resets were attempted.
No raw response or code is committed.

The owner subsequently corrected the code capitalization. One authenticated
read succeeded: model Creator 5 Pro, firmwareVersion 1.9.9 and status printing.
Basic fields and both four-tool temperature arrays are present. The longer
firmware build suffix, display comparisons and live HA acceptance remain pending.
No further printer reads are needed to work on the saved private snapshot.
The code was used transiently; it is not stored in source or the project's `.env`.

The latest HA About page shows Core 2026.10.0 on HA OS 18.3. All 13 component files
are staged and the basic configuration check passed. Activation is pending; this
staging result does not yet validate live HA polling.
