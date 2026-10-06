# LAN API evidence and probe plan

Reviewed 2026-10-06. This implementation is original code based on wire behavior
documented by the community; no upstream implementation has been copied.

Sources:

- [Creator 5 series reference](https://github.com/Parallel-7/flashforge-api-docs/wiki/Creator-5-Series)
- [HTTP API reference](https://github.com/Parallel-7/flashforge-api-docs/wiki/HTTP-REST-API)
- [Existing Python client](https://github.com/GhostTypes/ff-5mp-api-py)
- [Existing HA integration](https://github.com/GhostTypes/ff-5mp-hass)
- [Creator 5 WebUI](https://github.com/varavut/FlashforgeCreator5WebUI)

The community already has Creator 5 Pro support. This small project starts from
scratch as requested, but comparing or contributing to those projects may reduce
future maintenance. These are community observations, not an official API contract.

The series reference describes HTTP-only API access on 8898, credentials on every
request (`serialNumber`, `checkCode`), and no legacy TCP server on 8899.
`POST /detail` returns `{code: 0, detail: {...}}`. Some firmware misspells the JSON
content type; the client decodes JSON independently of that header.
Authentication codes 1 and -2 indicate rejected credentials or LAN mode.
Progress is a ratio; remaining time is `estimatedTime`, not that value minus elapsed time.
Tool head fields and material station data differ from older printers; those sensors
are deferred until a real response is checked. Unknown fields are kept in memory
and not logged. No capability inference comes from success replies to control commands.

The source covers stock firmware through 1.9.8. The user reports stock 1.9.9-330,
LAN mode enabled. That firmware remains unverified here. The local target address
belongs in `.env`, not source or fixtures.

Probe sequence:

1. Check reachability of the supplied target's TCP port 8898 without authentication.
2. Enter the serial and check code locally and request `/detail` once.
3. Review the sanitized summary for valid state, progress and temperatures.
4. If extra field mapping is needed, inspect the raw detail locally; create a
   deliberately synthetic fixture rather than committing a raw capture.
5. Validate HA setup, duplicate prevention, polling, loss of connectivity,
   reauthentication and unload in a development instance.

No cloud login, firmware changes, network scans or printer controls are needed for this stage.

Initial local check: connecting to the supplied address on TCP 8898 timed out after
five seconds on 2026-10-06. No authentication request was sent. Verify the address
on the printer display and that the Mac can reach the printer's VLAN; a VPN or
firewall may affect reachability. Authenticated status and HA runtime remain untested.
