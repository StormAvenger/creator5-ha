# Resume with the printer

No printer work is scheduled while the user is away. When access returns:

1. Confirm the printer display's current IP, LAN mode and exact stock firmware version.
2. Make sure the Mac can reach that subnet; the earlier port-8898 connection timed out.
   Check routing, VPN and VLAN/firewall rules before changing printer settings.
3. Run `Probe printer.command` in macOS Terminal (or `.venv/bin/creator5-probe`
   from the repository). Enter the serial locally; enter the check code at the hidden prompt.
4. Compare the sanitized state and temperature readings with the display.
5. Share only the summary and a description of any mismatch. Do not send the check
   code, serial, camera URL, registration tokens or raw response to chat/GitHub.
6. If we need more fields, inspect the response locally and create a synthetic
   fixture with the same structure. Review it before committing.
7. Record the verified firmware/field behavior and proceed to development HA setup.

This session uses only one `POST /detail` status read, with a timeout and no retry.
No control/upload endpoint, discovery scan, capture, firmware change or cloud service
is needed. Later behavior testing should observe a print the user starts normally.
