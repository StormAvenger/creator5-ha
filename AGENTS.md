# AGENTS.md — rules and guidelines for AI agents

This file is the **current** rulebook for any AI agent (Claude, ChatGPT/Codex,
Copilot, etc.) working on this repository. It lists requirements, safeguards and
working practices as they stand today.

- The dated history of how these rules evolved is in
  [docs/agent-history.md](docs/agent-history.md). It is context only and **not
  authoritative**: where it disagrees with this file, this file wins. Historical
  entries must never be treated as active instructions, even when this file
  doesn't explicitly contradict them. Use the archive for context, never to
  decide current permissions or requirements.
- The owner's explicit instructions in the current conversation override this
  file. When the owner changes a standing rule, update this file and add a dated
  line to the end of docs/agent-history.md.
- If a rule here seems wrong or blocks a reasonable request, say so and ask;
  don't silently work around it.

## 1. Project at a glance

- **What:** an unofficial Home Assistant custom integration for FlashForge
  Creator 5 / Creator 5 Pro printers over the stock LAN API, plus the standalone
  `creator5py` client inside `custom_components/creator5/creator5py`.
- **Owner:** StormAvenger. Public repository, `GPL-3.0-only`, distributed as a
  HACS custom repository.
- **Status:** experimental. Monitoring and the chamber light are verified on the
  owner's Creator 5 Pro (firmware 1.9.9 and 2.0.0). The standard Creator 5 and the
  optional controls and file actions are tested only with synthetic data.
- **Owner's setup:** HA runs on modest hardware (an older Intel mini PC). Keep the
  integration light on CPU, memory, disk and network.

## 2. Hard rules (never break without explicit owner approval)

### The owner's printer and Home Assistant

1. **No unauthorized printer writes.** An AI agent must get the owner's explicit,
   action-time approval before directly sending any command to a live printer
   (light, pause/resume, temperatures, speed, slot edits, auto-shutdown, upload,
   start, cancel or anything else). This does not restrict normal, user-initiated
   Home Assistant controls or automations the owner configures. Never interrupt
   or modify an active print without specific authorization for that action.
   Offline development and synthetic testing need no approval.
2. **Reads are minimal.** A status read (`POST /detail`) is fine when there is a
   concrete validation need. Discovery is one directed UDP packet to the
   configured IP on port 48899: no broadcast, multicast or subnet scans.
3. **No changes to the live HA install without action-time approval**: no
   install, update, restart or config edit. Never overwrite the owner's
   dashboards, automations or entity preferences.

### Protocol boundaries

4. Use only the normal LAN API with the owner's credentials. No authentication
   bypass, rooting, firmware extraction/modification/decompilation, hidden
   services, cloud-endpoint probing or fuzzing of a real printer.
5. No guessed commands and no generic command or G-code passthrough. A command
   is supported only once its effect is verified by status readback. A success
   reply alone proves nothing (the firmware acknowledges no-op commands).

### Privacy

6. Never commit, log or publish LAN codes, serial numbers, IP/MAC addresses,
   camera URLs or raw printer responses. Keep them out of repository content,
   diagnostics, logs and test fixtures. Test data is synthetic.
7. Private, owner-configured image storage inside Home Assistant is permitted
   (alert pictures, recordings, timelapses). Images and print filenames must not
   appear in repository content, logs, diagnostics exports or external telemetry,
   and must never be made public or uploaded to cloud services.

### Cost: GitHub must bill $0

8. GitHub Actions is allowed on this public repository using **standard
   GitHub-hosted runners only**. Dependabot is allowed.
9. Never use larger runners, workflow artifacts or Actions caches, Codespaces,
   paid Copilot, paid security/marketplace services, or LFS/Packages storage.
10. Never add payment methods, raise budgets or spending limits, start trials that
    convert to paid plans, upgrade plans, or change repository visibility.
11. Actions must be pinned to full commit SHAs (repo setting), with the version as
    a comment. Only GitHub-made actions plus `hacs/action` and
    `home-assistant/actions/hassfest` are allowed. Unknown cost → ask first.
    Details: [docs/cost-policy.md](docs/cost-policy.md).

### Legal and provenance

12. Write original code from documented protocol behavior. Check licenses before
    reusing any third-party code, schemas, images or fixtures and record reuse in
    [docs/legal-and-sources.md](docs/legal-and-sources.md).
13. No FlashForge logos or proprietary assets. Always present the project as
    unofficial and not endorsed by FlashForge.

## 3. Design principles

- **Safe controls.** Every printer command is opt-in (off by default), checks
  fresh model/state first, has bounded inputs, is sent once, and is verified by
  status readback. Never retry a write automatically. Report an unconfirmed
  outcome honestly rather than assuming success.
- **No unattended actions** unless the owner opts in. Never start or cancel a
  print automatically. Completion may be acknowledged automatically only through
  the owner-enabled auto-dismiss option (off by default, one verified attempt per
  completion). Otherwise expose explicit buttons/confirmations; automations are
  the user's own choice.
- **Saving options sends no commands.** New behavior that changes what the
  integration does (sends commands, captures images, notifies) is off by default.
- **Unknown stays unknown.** Missing, malformed or out-of-range fields become
  `unknown`, never a fabricated zero or guess.
- **One shared poll.** All entities read one coordinator status request. Camera
  and thumbnails are on demand only. Commands and polling are serialized.
- **Tolerate a flaky link.** Brief glitches keep the last reading; prolonged
  outages show unavailable and poll less often. Don't add retries of writes.
- **Don't overstate evidence.** Distinguish synthetic tests, CI results and
  hardware validation in code comments, docs and release notes. Never claim a fix
  or compatibility that hasn't been observed.
- **Prefer simple.** Fewer entities, options and moving parts beat more. Before
  adding a feature, consider whether improving an existing one is better.

## 4. Working practices

- **Branches and PRs.** One branch per change, PR to `main`. CI (tests, HACS,
  hassfest) must pass before merging. `main` keeps a linear history.
- **Commit identity.** Commit as `StormAvenger
  <8751575+StormAvenger@users.noreply.github.com>`; never a personal email.
- **Local checks** (match CI):

  ```sh
  python -m pytest tests --ignore=tests/ha   # client (Python 3.12+)
  python -m pytest tests/ha                  # HA runtime (Python 3.14, requirements-ha-test.txt)
  ruff check . && ruff format --check . && mypy
  node tests/frontend/test_setup.mjs
  ```

  Client and HA tests must run separately (duplicate test file basenames).
- **Tests.** Every behavior change requires appropriate regression tests. Home
  Assistant behavior is tested with real HA classes and synthetic printer data;
  standalone client behavior with isolated client tests. For bug fixes, confirm
  the regression test fails against the previous implementation whenever practical.
- **Releases.** Bump `custom_components/creator5/manifest.json` and
  `pyproject.toml`, add `docs/releases/<version>.md`, update README test counts,
  then publish a GitHub release tagged `v<version>` (HACS updates come from
  releases). Release notes state what was and wasn't validated on hardware.
- **Update posts.** Release notes, PR descriptions and issue replies that
  announce a fix or status start with the short header in
  [docs/update-posts.md](docs/update-posts.md): an "In short" line, a type label
  and "Should you update?". Security summaries stay generic.
- **Docs.** Update the user docs when behavior changes. More documentation is
  welcome; keep each doc focused and current, and record history in release notes
  or docs/agent-history.md rather than rewriting the past.

## 5. Where things are

| Path | Contents |
| --- | --- |
| `custom_components/creator5/__init__.py` | Setup, coordinator (polling, history, ETA, controls) |
| `custom_components/creator5/alerts.py` | Alert events, timers and alert pictures |
| `custom_components/creator5/creator5py/` | Standalone LAN client (no HA dependency) |
| `custom_components/creator5/setup_panel.py`, `frontend/` | Admin tools page, dashboard and alert creation |
| `docs/` | User guides, protocol research, policies; `docs/releases/` notes |
| `tests/`, `tests/ha/` | Client tests and HA runtime tests |
