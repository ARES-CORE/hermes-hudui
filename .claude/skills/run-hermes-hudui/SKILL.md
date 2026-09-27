---
name: run-hermes-hudui
description: Run, start, build, test, smoke-test or screenshot the Hermes HUD web UI (FastAPI backend + React frontend). Use to launch the HUD locally with fixture data in offline mode, check its API, verify that egress endpoints are blocked, or capture screenshots of its tabs.
---

# Run hermes-hudui

FastAPI server that serves a prebuilt React UI and reads a Hermes data dir
(`HERMES_HOME`). Agents drive it with `.claude/skills/run-hermes-hudui/driver.sh`:
background launch with fixture data, `curl` smoke checks, and Chromium screenshots.
All paths are relative to the repo root. The driver always runs with
`HERMES_HUD_OFFLINE=1` (no actions that reach external hosts).

## Prerequisites

Python 3.11+, Node 18+ (only for `setup`, to build the frontend), and for
screenshots Playwright + Chromium (preinstalled in the cloud container at
`/opt/node22/lib/node_modules/playwright` and `/opt/pw-browsers/chromium`;
override with `PLAYWRIGHT_MODULE` / `CHROMIUM_PATH`).

## Build

```bash
.claude/skills/run-hermes-hudui/driver.sh setup
```

Creates `.venv/`, installs the package in editable mode plus `httpx`/`pytest`,
builds `frontend/` and copies `frontend/dist` into `backend/static/`. ~30 s.

## Run (agent path)

```bash
D=.claude/skills/run-hermes-hudui/driver.sh
$D start 3099                 # background, fixture HERMES_HOME in .hud-run/hermes
$D smoke                      # 200 on UI/API, 403 on egress endpoints, prints profile
$D shot /tmp/hud.png skills   # tabs: dashboard | memory | skills | profiles
$D logs                       # server log
$D stop
```

- To inspect real data instead of the fixture: `HERMES_HOME=/srv/ares $D start 3099`.
- State lives in `.hud-run/` (gitignored): `pid`, `port`, `server.log`, fixture.
- `smoke` exits non-zero if any check fails.

## Direct invocation

Collectors and the offline guard are plain Python; most PRs only need:

```bash
.venv/bin/python -m pytest -q tests/test_offline_mode.py tests/test_profile_config.py
```

## Test

```bash
.venv/bin/python -m pytest -q tests
```

Expected today: 98 passed, 1 failed (`test_replay_api.py::test_replay_routes_are_registered`,
fails on `main` too: FastAPI `_IncludedRouter` has no `.path`).

## Human path

`source .venv/bin/activate && hermes-hudui` then open http://localhost:3001.
Useless headless; use the driver.

## Gotchas

- **Offline mode is a middleware** (`backend/offline.py`): with `HERMES_HUD_OFFLINE=1`
  these return 403: `POST /api/hermes/update`, `/api/gateway/restart`,
  `/api/plugins/install`, `/api/plugins/{name}/update`,
  `/api/chat/sessions/{id}/send|message`, `/api/cron`, `/api/cron/{id}/run`.
  Replay "publish" is local-only and stays allowed.
- **Profiles read `config.yaml` with real YAML now.** The old minimal parser dropped
  indented list items (`  - terminal`) and kept inline `# comments` in values.
- **Playwright from a global install**: bare `import 'playwright'` fails in an ESM
  script outside a project; `shot.mjs` uses `createRequire` with an absolute path.
- **Never `pkill -f hermes-hudui`** from a shell whose own command line contains that
  string: it kills your shell (exit 144). The driver uses the pid file.
- Tabs are switched with the number keys the UI binds (`1` dashboard, `2` memory,
  `3` skills, `0` profiles), not by URL.

## Troubleshooting

- `Permission denied` running `/opt/hermes-hudui/venv/bin/hermes-hudui` as the service
  user → the venv was created under `umask 077`; `deploy/install-offline.sh` now forces
  `umask 022`, re-run it.
- `useradd: group hermes exists` during deploy → fixed in `deploy/install-offline.sh`
  (reuses the existing group).
- Profile shows `toolsets: []` or provider with `# ...` appended → old parser; update
  to a build that includes `load_yaml` in `backend/collectors/profiles.py`.
