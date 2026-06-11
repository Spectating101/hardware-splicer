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
- **Qwen/Gemini API key** — live vision intake only (offline tier scoring works without keys)

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

## Verify everything

```bash
make verify
```

Runs doctor, unit tests, backend benchmark, strict functional-delivery audit, and tier scoring.
