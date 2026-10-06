# Development scope and source provenance

Reviewed 2026-10-06. These are practical project boundaries, not a legal opinion
or assurance that every future activity is lawful. Exact contract applicability,
jurisdiction and the user's installed software terms remain unresolved.

## Research carried forward and rechecked

[17 U.S.C. §1201(f)](https://www.law.cornell.edu/uscode/text/17/1201) provides a
conditional interoperability exception involving lawfully obtained software and
an independently created program. It is not blanket permission for circumvention,
infringement or violations of other law; dissemination also has conditions.
Our current implementation uses normal authentication and performs no circumvention.

[FlashForge's published EU terms](https://eu.flashforge.com/pages/terms-of-service),
under Software License, restrict analyzing/modifying/redistributing its software
without consent. The page makes broad applicability claims; a regional URL alone
does not establish whether the user's actual license is governed by these terms.
We must identify the terms accompanying the installed software before deeper
analysis, and seek qualified advice if proposed work conflicts with them.

## Rules for this repository

1. Original client/integration code, documented LAN behavior and synthetic tests.
2. Normal LAN credentials for the owner's printer; no auth/signature/root bypasses.
3. No proprietary binary extraction, decompilation, firmware modification or cloud probing.
4. Observe only the owner's equipment/authorized traffic. Narrow packet capture
   is optional and deferred; never capture unrelated LAN traffic or publish raw captures.
5. Never commit secrets, certificates, private keys, proprietary resources or firmware dumps.
6. Check licenses before copying any third-party code, schemas, images or fixtures;
   preserve required attribution/notices. Publicly visible does not mean freely reusable.
7. Identify this as an unofficial project without implying vendor endorsement.

Current code was written independently; community implementations are reference
material only. No third-party implementation or firmware file has been copied into
the repository. Test values are fabricated. Libraries and the HA test framework
are installed dependencies rather than vendored source; review their notices when
choosing a distribution format.

## Provenance ledger

| Source | Purpose | Material included |
| --- | --- | --- |
| [Community HTTP reference](https://github.com/Parallel-7/flashforge-api-docs/wiki/HTTP-REST-API) | Request/envelope and basic field behavior | Protocol facts; no copied implementation/schema |
| [Creator 5 reference](https://github.com/Parallel-7/flashforge-api-docs/wiki/Creator-5-Series) | HTTP-only model and firmware caveats | Protocol facts; no firmware/binaries |
| [GhostTypes client](https://github.com/GhostTypes/ff-5mp-api-py) | Existing project/support awareness | Link only |
| [GhostTypes HA integration](https://github.com/GhostTypes/ff-5mp-hass) | Existing integration awareness | Link only |
| [Creator 5 WebUI](https://github.com/varavut/FlashforgeCreator5WebUI) | Community LAN implementation reference | Link only |
| [Home Assistant developer docs](https://developers.home-assistant.io/docs/creating_integration_manifest/) | Integration interfaces and lifecycle | Framework usage; original implementation |
| [HA custom-component test framework](https://github.com/MatthewFlamm/pytest-homeassistant-custom-component) | Offline runtime testing | Test dependency; no vendored source |

The user chooses this project's outbound license before public distribution.
Keep this ledger current if reuse is introduced. The prior chat's characterization
of any project's license is not a substitute for checking its actual license at reuse time.
