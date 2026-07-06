# Hardware-Splicer Splice Agent

[![Splice Agent v1](https://github.com/Spectating101/hardware-splicer/actions/workflows/hardware-splicer.yml/badge.svg)](https://github.com/Spectating101/hardware-splicer/actions/workflows/hardware-splicer.yml)

**Auditable hardware bring-up** — donor intake → KiCad carrier with DRC truth → bench measurement gates → defensible **PROJECT_PACKAGE**.

Self-hosted agent for teams who need compile honesty and a power-on checklist, not cosmetic copper or hand-wavy LLM excuses.

**Version:** `1.0.1` · **Requires:** Python 3.12+, KiCad 9+ (`kicad-cli`), Node 18+

---

## Quick start

```bash
git clone https://github.com/Spectating101/hardware-splicer.git
cd hardware-splicer
bash scripts/install_splice_v1.sh
source .venv/bin/activate
hs-doctor
make splice-ui-serve
```

Open **http://127.0.0.1:8787** → **Quick demo** → **Gates** → **Bench** → **Download zip**.

Full walkthrough: [`docs/QUICKSTART_SPLICE_v1.md`](docs/QUICKSTART_SPLICE_v1.md) · 5-min demo: [`docs/DEMO_5_MIN_UI.md`](docs/DEMO_5_MIN_UI.md)

---

## Verify (engineering bar)

```bash
make verify-product-internal   # full internal bar (engine + UI + API + live job)
# or stepwise:
make verify-product-v1
make verify-install-smoke
make verify-product-live-smoke
```

| Step | Proves |
|------|--------|
| `hs-doctor` | KiCad, Node, Python, API deps |
| `verify-splice` | S2 manifest compile (4/4) |
| `verify-splice-loop` | S3 bench closure (3/3) |
| `verify-splice-real-bench` | Real capture → `power_on_authorized` |

CI runs **Splice Agent v1** on Ubuntu: `verify-splice-v1` + UI build + product API tests.

---

## Product surfaces

| Surface | Command / path |
|---------|----------------|
| **Web UI** | `make splice-ui-serve` or `make splice-ui-dev` |
| **HTTP API** | `hs-serve --port 8787` · OpenAPI at `/docs` |
| **MCP** | `hs-mcp` · see [`docs/MCP.md`](docs/MCP.md) |
| **CLI** | `hs-doctor`, `scripts/hardware_splicer.py` |

---

## What you get (artifacts)

- `PROJECT_PACKAGE.json` — BOM, wiring, build steps, **gates**
- KiCad carrier + DRC report
- `SPLICE_BENCH_SESSION.json` — measurements before power-on
- `COMPILE_CASEFILE.json` on failure — debuggable, not vague errors
- Job bundle zip via `GET /v1/jobs/{id}/bundle`

---

## In scope / out of scope (v1)

| In | Out |
|----|-----|
| Splice intake → carrier compile | Public multi-tenant SaaS |
| Bench gates + gate verdict | Production autorouted copper (default) |
| Async jobs, MCP + HTTP parity | Flux / Blueprint-class editor |
| Optional splice-ui workbench | Certified donor harness safety |

Details: [`RELEASE_NOTES_v1.0.1.md`](RELEASE_NOTES_v1.0.1.md) · [`docs/RELEASE_V1.md`](docs/RELEASE_V1.md)

---

## Documentation

**Browsing on GitHub / ChatGPT:** start at [`docs/GITHUB_START_HERE.md`](docs/GITHUB_START_HERE.md) — one page with links to everything canonical.

| Audience | Start here |
|----------|------------|
| **Everyone** | [`docs/QUICKSTART_SPLICE_v1.md`](docs/QUICKSTART_SPLICE_v1.md) |
| **Full map** | [`docs/DOCUMENTATION_INDEX.md`](docs/DOCUMENTATION_INDEX.md) |
| **Internal maturity** | [`docs/INTERNAL_MATURITY_PLAN.md`](docs/INTERNAL_MATURITY_PLAN.md) |
| **Agents / CI** | [`docs/AGENT_HANDOFF.md`](docs/AGENT_HANDOFF.md) |
| **Deploy / ops** | [`deploy/DEPLOY.md`](deploy/DEPLOY.md) · [`docs/OPERATIONS_RUNBOOK_v1.md`](docs/OPERATIONS_RUNBOOK_v1.md) |
| **Commercial** | [`docs/DEPLOY_PRODUCT_FUNDING_PLAYBOOK.md`](docs/DEPLOY_PRODUCT_FUNDING_PLAYBOOK.md) |
| **Support & liability** | [`docs/SUPPORT_AND_LIABILITY_v1.md`](docs/SUPPORT_AND_LIABILITY_v1.md) |
| **Engine depth** | [`docs/README_MONOREPO_DEPTH.md`](docs/README_MONOREPO_DEPTH.md) |

---

## Monorepo (platform depth)

This repository also contains Circuit-AI, mecha-splicer, and 3d-splicer — **not** the v1.0 product SKU. See [`apps/README.md`](apps/README.md).

---

## License & limits

Software license: **Proprietary** (see `pyproject.toml`). Support boundaries and power-on liability: [`docs/SUPPORT_AND_LIABILITY_v1.md`](docs/SUPPORT_AND_LIABILITY_v1.md).

The engine assists compile and gate workflows; **the operator authorizes energization** after bench measurements.
