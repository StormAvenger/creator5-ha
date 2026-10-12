# Resume with the printer

On 2026-10-11 the user resumed local access while the printer is printing.
The supplied API port accepts a TCP connection from the Mac; device identity and
authenticated status remain unverified. Serial and check code are not saved locally.
The corrected reported stock firmware is `1.9.9-1.3.0`.

Protect the current print: no pause, stop, resume, temperature changes, uploads,
reboots, firmware changes or printer settings changes. Do not install/restart
production HA or start continuous polling during this print. The first authenticated
probe remains one status request, without retries. Enter credentials locally only
after confirming the supplied address belongs to this printer.

1. Without changing the current print, confirm the display's current IP, LAN mode and exact
   stock firmware version. Verify the supplied address still belongs to this printer.
2. The latest TCP-only check succeeded; the earlier port-8898 connection timed out.
   Check routing, VPN and VLAN/firewall rules before changing printer settings.
3. Run `Probe printer.command` in macOS Terminal (or `.venv/bin/creator5-probe`
   from the repository). Enter the serial locally; enter the check code at the hidden prompt.
   Credentials need not be saved in `.env` to use the probe.
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

This session uses only one `POST /detail` status read, with a timeout and no retry.
No control/upload endpoint, discovery scan, capture, firmware change or cloud service
is needed. Later behavior testing should observe a print the user starts normally.
