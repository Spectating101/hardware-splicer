# Hardware-Splicer Splice Agent

[![Splice Agent v1](https://github.com/Spectating101/hardware-splicer/actions/workflows/hardware-splicer.yml/badge.svg)](https://github.com/Spectating101/hardware-splicer/actions/workflows/hardware-splicer.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Auditable hardware bring-up + design verification** — donor intake → KiCad carrier with DRC truth → preview/BOM/fab readiness → bench gates → defensible **PROJECT_PACKAGE**.

Self-hosted agent for teams who need compile honesty and a power-on checklist, not cosmetic copper or hand-wavy LLM excuses.

**Version:** [`v1.1.0-alpha.16`](docs/COLD_INTERNAL_EXIT.md) (cold-internal exit) · **Requires:** Python 3.12+, KiCad 9+ (`kicad-cli`), Node 18+

**Status:** Seeking **3 design partners** this quarter (repair / prototype / lab bring-up). Not a multi-tenant SaaS. Not a chat-to-PCB generator.

**Release:** [`docs/RELEASE_v1.1.md`](docs/RELEASE_v1.1.md) · **Deploy:** [`deploy/DEPLOY.md`](deploy/DEPLOY.md) · **Verify:** `make verify-product-internal`  
**Pilots:** [`docs/DESIGN_PARTNER.md`](docs/DESIGN_PARTNER.md) · [`docs/OFFER_SPLICE_BENCH_KIT_v1.md`](docs/OFFER_SPLICE_BENCH_KIT_v1.md) · [`docs/PROOF_PACK_CONTENTS.md`](docs/PROOF_PACK_CONTENTS.md)  
**Start here:** [`docs/GITHUB_START_HERE.md`](docs/GITHUB_START_HERE.md)

---

## Design partners (open)

We are filling **three** partner slots for real next-board bring-up (salvage/donor, prototype, or lab):

1. Open [`docs/DESIGN_PARTNER.md`](docs/DESIGN_PARTNER.md)
2. Open a GitHub Issue titled `[Design partner] <lab or project>` **or** contact the maintainer via the GitHub profile
3. Include: what board/donor, target date, Linux/WSL2 + KiCad 9 availability

In exchange: Splice Sprint (discounted or case-rights) → `PROJECT_PACKAGE` + gate review → optional redacted public case note.

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

Open **http://127.0.0.1:8787** → **Quick demo** → **Design verify** (KiCanvas, BOM, fab) → **Gates** → **Bench** → **Download zip**.

**v1.1 on `main`:** Design verify tab (KiCanvas, BOM, fab readiness). See [`docs/V1.1_INTERFACE_PREVIEW.md`](docs/V1.1_INTERFACE_PREVIEW.md).

Full walkthrough: [`docs/QUICKSTART_SPLICE_v1.md`](docs/QUICKSTART_SPLICE_v1.md) · 5-min demo: [`docs/DEMO_5_MIN_UI.md`](docs/DEMO_5_MIN_UI.md)

---

## What this is / is not (honesty)

| Is | Is not |
|----|--------|
| Cold-internal proven on two machines ([`COLD_INTERNAL_EXIT.md`](docs/COLD_INTERNAL_EXIT.md)) | Claim that strangers have completed zero-help dry-run |
| KiCad CLI DRC as compile truth | Default fab-ready autoroute |
| Bench **gates** before power-on | UL/CE certification or operator replacement |
| Optional Architon `rv` after compose ([docs](docs/integrations/ARCHITON_GATE.md)) | Bundled Architon dependency |

---

## Verify (engineering bar)

```bash
make verify-product-internal   # full internal bar (engine + UI + API + live job)
# or stepwise:
make verify-product-v1
make verify-ui-interface-smoke
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

Details: [`RELEASE_NOTES_v1.1.0.md`](RELEASE_NOTES_v1.1.0.md) · [`docs/RELEASE_V1.md`](docs/RELEASE_V1.md)

---

## Documentation

**Browsing on GitHub:** start at [`docs/GITHUB_START_HERE.md`](docs/GITHUB_START_HERE.md).

| Audience | Start here |
|----------|------------|
| **Everyone** | [`docs/QUICKSTART_SPLICE_v1.md`](docs/QUICKSTART_SPLICE_v1.md) |
| **Design partners / pilots** | [`docs/DESIGN_PARTNER.md`](docs/DESIGN_PARTNER.md) |
| **Launch v1.1** | [`docs/RELEASE_v1.1.md`](docs/RELEASE_v1.1.md) |
| **Conversion doctrine** | [`docs/CONVERSION_DOCTRINE.md`](docs/CONVERSION_DOCTRINE.md) |
| **Support & liability** | [`docs/SUPPORT_AND_LIABILITY_v1.md`](docs/SUPPORT_AND_LIABILITY_v1.md) |
| **Security** | [`SECURITY.md`](SECURITY.md) |

---

## Monorepo (platform depth)

This repository also contains Circuit-AI, mecha-splicer, and 3d-splicer — **not** the v1 product SKU. See [`apps/README.md`](apps/README.md).

---

## License & limits

Software license: **MIT** ([`LICENSE`](LICENSE)). Support boundaries and power-on liability: [`docs/SUPPORT_AND_LIABILITY_v1.md`](docs/SUPPORT_AND_LIABILITY_v1.md).

The engine assists compile and gate workflows; **the operator authorizes energization** after bench measurements.
