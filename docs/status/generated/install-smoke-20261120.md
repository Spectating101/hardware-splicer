# Install smoke test: wheel, hs-serve, nginx and systemd (2026-11-20)

Follows [`../../INSTALL_REPORT_TEMPLATE.md`](../../INSTALL_REPORT_TEMPLATE.md) where it fits.
Raw command log: [`install-smoke-20261120.log`](install-smoke-20261120.log).
Paths are placeholders: `<checkout>` is a tracked-only worktree of `agent/project-bench`,
`<scratch>` a fresh directory outside it. Nothing was published, tagged or deployed.

## Metadata

| Field | Value |
|-------|-------|
| Date | 2026-11-20 |
| Commit | `agent/project-bench` at `6070b320` plus the fixes listed below |
| Package | `hardware-splicer` 1.1.0 (`pyproject.toml`); no `v1.1.0` tag exists, only `v1.1.0-alpha.*` |
| OS | Debian GNU/Linux 13 (trixie), Linux 6.12 |
| Python | 3.13.5 (fresh venv), pip 25.1.1, build with setuptools 84.2.1 |
| Node | 22.21.1 (UI build only) |
| KiCad | `kicad-cli` 9.0.2 on PATH |
| nginx | 1.27.5 (`nginx:1.27-alpine` container, host network); none on the host |
| systemd | 257 (`systemd-run --user` for the hardening run) |
| Browser | Playwright Chromium, headless |

## Steps and results

| Step | Command | Result |
|------|---------|--------|
| UI build and stage | `make ui-package` | PASS: 283 modules, `src/hardware_splicer/ui_dist` + `manifest.json` |
| Wheel and sdist | `python -m build --outdir <scratch>/dist .` | PASS: `hardware_splicer-1.1.0-py3-none-any.whl`, `hardware_splicer-1.1.0.tar.gz` (wheel built from the sdist) |
| Install | `python3 -m venv <scratch>/venv && <scratch>/venv/bin/pip install '<wheel>[digital]'` | PASS (not editable; no `PYTHONPATH`) |
| Doctor, no checkout | `hs-doctor` from `<scratch>/run` | `ok: false` (no `apps/` roots); `install.mode: installed`, `projects_available: false`, scratch in `~/.cache/hardware-splicer` |
| Doctor, checkout | `hs-doctor --repo-root <checkout>` | `ok: true`, all four app roots present, UI build found in the package |
| Serve | `hs-serve --ui --port 8813 --repo-root <checkout>` with fresh `HARDWARE_SPLICER_STATE_DIR` and `HARDWARE_SPLICER_TMP_ROOT` | PASS: `/health`, `/docs`, `/openapi.json`, `/v1/projects`, `/v1/scenes`, `/`, `/projects/x` = 200; `/assets/nope.js` = JSON 404 |
| Serve, no checkout | `hs-serve --ui --port 8813` | PASS: all routes 200, `/v1/scenes` = `[]`, registered study = 503 `digital_runtime_unavailable` naming `--repo-root`; no tracebacks |
| Project journey | `node scripts/verify_project_journey.cjs http://127.0.0.1:8813 <scratch>/journey` | PASS: 16 captures, "no console errors, failed requests or overflow" (Fielddeck 5 study and requirement change ran natively) |
| Persistence | `PUT /v1/projects/persist-smoke/snapshot`, stop, start, list | PASS: same 6 projects and revisions before and after; `persist-smoke` readable |
| Orphans | `find` over state, scratch, `/tmp`, site-packages, checkout | PASS: scratch holds one empty `tmp/`; nothing written outside the two configured directories |
| nginx parse | `nginx -t` with the example (ports and upstream rewritten) | PASS (one deprecation warning for `listen ... http2` on >= 1.25.1); FAILS closed when the key map is absent |
| nginx auth | curl over TLS, see matrix | PASS on every route |
| nginx SSE | `curl -N` through the proxy on `/v1/projects/drone-build/events` | PASS: `event: hello` streamed unbuffered |
| systemd verify | `systemd-analyze verify` on the example (ExecStart pointed at the test venv) | PASS, no warnings |
| systemd hardening | `systemd-run --user` with `NoNewPrivileges`, `ProtectSystem=strict`, `ProtectHome=read-only`, `PrivateTmp`, `ReadWritePaths=<state>` and the rest | PASS: probe write outside `ReadWritePaths` blocked; full journey passed against this instance; no permission errors in the journal |

nginx access matrix (HTTP status through the proxy):

| Path | none | wrong key | key | basic auth | bad password |
|------|------|-----------|-----|------------|--------------|
| `/` | 401 | 401 | 200 | 200 | 401 |
| `/docs` | 401 | 401 | 200 | 200 | 401 |
| `/openapi.json` | 401 | 401 | 200 | 200 | 401 |
| `/health` | 401 | 401 | 200 | 200 | 401 |
| `/v1/projects` | 401 | 401 | 200 | 200 | 401 |
| `/v1/scenes` | 401 | 401 | 200 | 200 | 401 |
| `/projects/x` (SPA) | 401 | 401 | 200 | 200 | 401 |
| `/v1/projects/<id>/events` | 401 | 401 | 200 | 200 | 401 |

Port 80 answers 301 to HTTPS. (`/health` takes about 2.4 s, so a 3 s curl timeout
first showed it as 000; with a longer timeout it is 200.)

## What broke and what changed

1. **Firmware templates missing from the wheel.** `data/firmware_application/**`
   (C++ templates used by the device application lane) was not package data.
   Added to `pyproject.toml`; a test now fails if any tracked non-Python file under
   `src/hardware_splicer` is not covered by package data.
2. **`--repo-root` did not reach the engine.** Importing the entry point imports
   the whole package, and `runtime.ROOT` and `digital_cases.ROOT` were fixed at
   import time to `site-packages/..`, ignoring `HARDWARE_SPLICER_REPO_ROOT` entirely.
   Result: `/health` reported `ok: false` and the journey failed creating the
   Fielddeck study ("Registered case inputs are unavailable", 46 paths). Now
   `state_paths.repo_root()` honours the variable (then the own checkout), those
   modules use it, and `hs-serve`/`hs-doctor --repo-root` re-execute themselves with
   the variable set so every module sees it.
3. **Installed package wrote scratch beside `site-packages`.** With
   `HARDWARE_SPLICER_TMP_ROOT` unset, scratch went to `<venv>/lib/python3.X/.cache`.
   It now defaults to `$XDG_CACHE_HOME/hardware-splicer` (or `~/.cache/...`) for an
   installed package; a checkout keeps its gitignored `.cache/`.
4. **`hs-doctor` misreported an install.** It took no arguments and showed
   `site-packages/..` as the root. It now accepts `--repo-root` and adds an
   `install` block: mode, checkout in use, whether `projects/` exists, UI build,
   state and scratch directories.
5. **Unavailable-case error was a 46-path dump with no remedy.** It now names three
   paths, the count, and says to use `--repo-root` / `HARDWARE_SPLICER_REPO_ROOT`.
6. **nginx example locked browsers out and committed a key.** A browser cannot put
   `X-API-Key` on page loads, scripts or `EventSource`, so the UI could not load
   behind it, and the placeholder key `CHANGE_ME_API_KEY` worked as-is if not
   replaced. Now: basic auth (htpasswd) for browsers, or a key from an included
   map file for scripts; both files live only on the server and `nginx -t` fails
   without them. Added TLS 1.2/1.3, session settings, HSTS, `client_max_body_size
   64m` for uploads, an unbuffered location for the event stream,
   `map_hash_bucket_size 128` (a 64-hex key failed the default), and stripping of
   credentials before the upstream.
7. **systemd example had no hardening.** Added a dedicated account,
   `StateDirectory`, `HOME` under the state directory, `HARDWARE_SPLICER_REPO_ROOT`,
   `NoNewPrivileges`, `ProtectSystem=strict`, `ReadWritePaths`, `ProtectHome`,
   `PrivateTmp`, `PrivateDevices`, kernel/cgroup protections and an address-family
   allow-list. `RestrictNamespaces` (bwrap) and `MemoryDenyWriteExecute` (JIT) are
   left off on purpose. Dropped the `PYTHONPATH` line.
8. **Docs pinned to tags that do not exist** (`v1.1.0`, `v1.0.1`, `v1.0.0`). Now
   `<release-tag>`. DEPLOY.md gained an installed-wheel section; SETUP.md no longer
   claims a wheel needs no checkout.

## Verdict

| | |
|--|--|
| Install | PASS (wheel, not editable, outside the checkout) |
| Demo | PASS (journey, persistence, nginx front, hardened service) |
| Ready for a pilot on this OS | With caveats below |

## Caveats and owner actions

- No real server, domain, certificate or release tag was used. A deploy needs a
  `<release-tag>` (none matching 1.1.0 exists), a hostname, a certificate, and the
  htpasswd and key-map files created on the server.
- An installed wheel still needs the checkout at the same release for registered
  cases, scenes and examples, and the `digital` extra (CadQuery) for studies.
- ~~`/health` returned absolute paths and took about 2.4 s~~ and ~~14 modules
  computed the checkout from `__file__`~~: fixed, see the addendum below.
- `project.license` as a TOML table is deprecated by setuptools (removal after
  2027-02-18).

## Addendum (same day, second round)

Two caveats above were fixed on `agent/project-bench` and re-checked with a fresh
wheel (UI rebuilt from the current tip) installed into the same venv.

**`/health` and `/v1/status`.** `/health` called `runtime_status()`, which started
three subprocesses to probe the 3D interpreter for FastAPI, uvicorn and CadQuery
(about 2.4 s with CadQuery installed). It now uses `headless_status()` (PATH and
import lookups only); the interpreter probes stay in `runtime_status()` for
`hs-doctor` and `/v1/status`, cached once per process. Neither endpoint returns a
filesystem path any more: app roots report `available` (or `exists`/`is_dir`),
the Python executable and 3D interpreter paths are dropped, and the UI reports
`served`, `source` (`argument`, `environment`, `packaged`, `checkout`) and the
index hash. The UI directory is logged once at startup ("Serving the UI build
from ...") and kept in `app.state.ui_dist`. Tests: no absolute path in either
JSON body, and `/health` answers with `subprocess.run`/`Popen` patched to fail.

**Checkout paths.** `mechanism_bridge`, `project_intake`, `golden_real_bench`,
`aerial_product_generator`, `board_vision_salvage`, `public_web_bench`,
`workshop_operator`, `drone_product_delivery`, `splice_manifest`,
`teardown_product`, `project_scene_api`, `integrations/engineering_review`,
`part_substitution_geometry` and `api.py` (example fixtures and the checkout UI
build) now use `state_paths.repo_root()`. A test fails if any module walks out of
the package from its own `__file__`; package-internal data (`data/`, `ui_dist`,
`tool_workers/`, `_pcbnew_helpers/`) is still found from `__file__`. With no
checkout configured, `GET /v1/examples/netlist-fixtures/<id>` answers 404 instead
of a 500.

| Check (installed wheel, port 8813) | `--repo-root <checkout>` | no checkout |
|------|------|------|
| `/health` `ok` | true | false (app roots unavailable) |
| Absolute-path strings in `/health` / `/v1/status` | 0 / 0 | 0 / 0 |
| `/health` time, three calls | 3.6 ms, 3.7 ms, 3.6 ms | 4.1 ms, 3.8 ms, 3.6 ms |
| `/v1/examples/splice-intakes` | 200, 7 examples | 200, 0 |
| `/v1/examples/donor-fixtures` | 200, 2 fixtures | 200, 0 |
| `/v1/examples/netlist-fixtures` | 200, 18 fixtures; one payload 200 | 200, 0; payload 404 |
| `/v1/scenes` | 3 | 0 |
| Tracebacks in the server log | 0 | 0 |
| Project journey (fresh state) | PASS, 18 captures, no console errors or failed requests | not run |

Full Python suite on the branch with these changes: 4619 passed, 81 skipped,
3 subtests passed (15 min 54 s, sequential).

Before this change an installed wheel served zero examples even with
`--repo-root`, because `api.py` looked beside `site-packages` (found by reading the
code, not re-run).
