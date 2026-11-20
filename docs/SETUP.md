# Hardware-Splicer setup

One-time bootstrap for the professor/demo path. No API keys required for the default walkthrough.

## Prerequisites

| Tool | Required for | Install |
|------|----------------|---------|
| Python 3.12+ | compiler, intake, tests | system package or pyenv |
| Node.js 18+ | KiCad PCB build compiler (`compile_build_graph.cjs`) | [nodejs.org](https://nodejs.org/) |
| KiCad 9+ (`kicad-cli`) | Gerber export + honest fab audit | [kicad.org](https://www.kicad.org/download/) |
| npm | dashboard demo | bundled with Node |

Optional:

- **CadQuery** — true STL rendering via 3D-Splicer (without it, script fallback still works)
- **Qwen/Gemini API key** — live vision and text LLM (offline tier scoring and hybrid compose work without keys)
- **agy CLI** (Antigravity) — text fallback when DashScope quota is tight; see [`docs/LLM_OPS.md`](LLM_OPS.md)

## Quick install

```bash
cd Hardware-Splicer
make setup
source .venv/bin/activate   # created by setup_demo.sh
```

`make setup` creates a venv, installs Python deps, runs `npm install` in **both** `apps/circuit-ai/circuit-ai-frontend` (required for the KiCad build compiler) and `apps/hardware-splicer-demo` (dashboard), then runs doctor.

Expected `doctor` output for a full fab demo:

- `demo_ready=True` (Python + Node)
- `fab_export_ready=True` (`kicad-cli` on PATH)
- `dependencies=node:ok, kicad_cli:ok, fastapi:ok, uvicorn:ok`

## Run the app

One app serves the whole product: `hardware_splicer.product_api:app`. It carries
the engine routes from `hardware_splicer.api` (health, jobs, examples, vision,
splice, build files, project scenes), every product router (projects, digital
studies, machine and electrical design, reviews, packages), and the built UI behind
them. `hs-serve` runs it; nothing else is needed for the UI.

```bash
make splice-ui-build   # once per UI change: npm test + Vite build into apps/splice-ui/dist
make serve             # hs-serve --ui on http://127.0.0.1:8787
make serve HS_SERVE_ARGS="--port 8796"
```

With the package installed, `hs-serve` does the same. Its UI options:

- no flag: serve the UI when a build is found, else API only;
- `--ui`: require a build and refuse to start without one, listing the paths tried;
- `--no-ui`: API only.

The build is looked up in this order: `--ui-dist PATH`, `HARDWARE_SPLICER_UI_DIST`,
the packaged copy `hardware_splicer/ui_dist/` (staged by `make ui-package`, which
also writes a SHA-256 `manifest.json`), then `apps/splice-ui/dist` in a source
checkout. Re-run `make ui-package` after UI changes if you staged one, or the
packaged copy wins with stale assets. `/health` reports `ui.served`, `ui.dist` and
`ui.index_sha256`. API routes always win over the UI's catch-all, and an unknown
`/v1/...` path is a JSON 404, never `index.html`.

For a wheel that serves the UI without Node: `make ui-package`, then
`python -m build` (or `python -m pip wheel --no-deps . -w dist`). The wheel carries
the API, the UI and the package data, but registered digital cases, project scenes
and examples stay in the checkout: run `hs-serve --repo-root <checkout>` (or set
`HARDWARE_SPLICER_REPO_ROOT`) and check with `hs-doctor --repo-root <checkout>`,
whose `install` block names the checkout, UI build, state and scratch directories
in use. Registered Fielddeck and plotter studies need the `digital` extra
(`pip install 'hardware-splicer[digital]'`) or `HARDWARE_SPLICER_DIGITAL_PYTHON`.

`hs-serve` refuses a non-loopback `--host` (or `HARDWARE_SPLICER_HOST`) unless
`--allow-remote` is given; there is no in-app authentication yet, so remote access
needs the nginx front in [DEPLOY.md](../deploy/DEPLOY.md). `HARDWARE_SPLICER_PORT`
changes the default port.

The older entry points still work as aliases, not separate products:
`make splice-ui-serve` builds the UI and runs the same `hs-serve --ui`;
`uvicorn hardware_splicer.product_api:app` with `HARDWARE_SPLICER_SERVE_UI=1` (or
`auto`) is what `hs-serve` runs. `hardware_splicer.api:app` remains the engine-only
app for tests and embedding: it lacks the product routes, so the UI does not work
against it.

## Where server state lives

The job database, saved projects and API build outputs are durable state. Their
default location depends on how Hardware-Splicer runs, so separate checkouts and
worktrees never share a job database:

1. `HARDWARE_SPLICER_STATE_DIR`, `HARDWARE_SPLICER_JOB_DB`,
   `HARDWARE_SPLICER_OUTPUT_ROOT` and `HARDWARE_SPLICER_PROJECT_ROOT` win when set.
2. In a source checkout: `.cache/hardware-splicer/state/` inside that checkout
   (gitignored, next to the `HARDWARE_SPLICER_TMP_ROOT` scratch default). The job
   database is `state/jobs.sqlite3`, outputs are `state/api/`, projects are
   `state/api/projects/`.
3. For an installed package: `$XDG_STATE_HOME/hardware-splicer`, else
   `~/.local/state/hardware-splicer`, with the same layout.

Nothing defaults to `/tmp`. Setting only `HARDWARE_SPLICER_STATE_DIR` moves the job
database, outputs and projects together. Scratch trees stay under
`HARDWARE_SPLICER_TMP_ROOT` (see [TESTING.md](TESTING.md)); they are disposable,
state is not. The resolver is `hardware_splicer.state_paths`.

## 3D-Splicer (optional mechanical path)

```bash
cd apps/3d-splicer
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

The compiler auto-detects `apps/3d-splicer/.venv/bin/python` when present.

## Dashboard demo

```bash
cd apps/hardware-splicer-demo
npm install
npm run dev -- --port 5177
```

Open http://127.0.0.1:5177 — seeded from backend tier scoring snapshots.

## Vision (optional)

```bash
cp .env.example .env.local
# edit .env.local — set DASHSCOPE_API_KEY or QWEN_API_KEY
```

Live vision is **not** required for `make score-intake-tiers` when `HARDWARE_SPLICER_SKIP_VISION_LIVE=1`.

## Text LLM (optional)

```bash
cp .env.example .env.local
# DASHSCOPE_API_KEY — Singapore intl endpoint
# Default: qwen_then_agy (Qwen HTTP, fall back to agy CLI on quota errors)
```

Offline dev (no API keys):

```bash
export HARDWARE_SPLICER_OFFLINE_COMPOSE=1
export HARDWARE_SPLICER_OFFLINE_SALVAGE=1
```

Inspect usage and quota: `python3 scripts/hardware_splicer.py text-usage` and `llm-quota`. Full reference: [`LLM_OPS.md`](LLM_OPS.md).

## Verify everything

```bash
make verify
```

Runs doctor, unit tests, backend benchmark, strict functional-delivery audit, and tier scoring.
