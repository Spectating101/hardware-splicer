# Start here (GitHub / external review)

**Repo:** [Spectating101/hardware-splicer](https://github.com/Spectating101/hardware-splicer)  
**Product:** Splice Agent v1 — auditable hardware bring-up (donor intake → KiCad carrier → bench gates → `PROJECT_PACKAGE`)  
**Version:** `1.0.1` · **Status:** Internal maturity phase (Tier I–II green on dev-linux; Tier III alien-machine install pending)

Use this page as the **single entry** when browsing on GitHub or pasting links into ChatGPT.

---

## 1. What to read first (15 minutes)

| # | Doc | Purpose |
|---|-----|---------|
| 1 | [README.md](https://github.com/Spectating101/hardware-splicer/blob/main/README.md) | Product pitch, quick start, verify commands |
| 2 | [QUICKSTART_SPLICE_v1.md](https://github.com/Spectating101/hardware-splicer/blob/main/docs/QUICKSTART_SPLICE_v1.md) | Install → doctor → UI → first build |
| 3 | [INTERNAL_MATURITY_PLAN.md](https://github.com/Spectating101/hardware-splicer/blob/main/docs/INTERNAL_MATURITY_PLAN.md) | **Current engineering bar** — what “done” means before external pilots |
| 4 | [SPLICE_PRODUCT.md](https://github.com/Spectating101/hardware-splicer/blob/main/docs/SPLICE_PRODUCT.md) | Product tiers S0–S5, scope |
| 5 | [DEMO_5_MIN_UI.md](https://github.com/Spectating101/hardware-splicer/blob/main/docs/DEMO_5_MIN_UI.md) | 5-minute demo script |

---

## 2. Product & operations (v1.0.1 envelope)

| Doc | Purpose |
|-----|---------|
| [RELEASE_NOTES_v1.0.1.md](https://github.com/Spectating101/hardware-splicer/blob/main/RELEASE_NOTES_v1.0.1.md) | What shipped in v1.0.1 |
| [RELEASE_V1.md](https://github.com/Spectating101/hardware-splicer/blob/main/docs/RELEASE_V1.md) | Release checklist and tag discipline |
| [SUPPORT_AND_LIABILITY_v1.md](https://github.com/Spectating101/hardware-splicer/blob/main/docs/SUPPORT_AND_LIABILITY_v1.md) | Support boundary, power-on liability |
| [OPERATIONS_RUNBOOK_v1.md](https://github.com/Spectating101/hardware-splicer/blob/main/docs/OPERATIONS_RUNBOOK_v1.md) | Lab ops, env vars, single-port serve |
| [UI_V1.md](https://github.com/Spectating101/hardware-splicer/blob/main/docs/UI_V1.md) | splice-ui scope and architecture |
| [INSTALL_REPORT_TEMPLATE.md](https://github.com/Spectating101/hardware-splicer/blob/main/docs/INSTALL_REPORT_TEMPLATE.md) | Alien-machine install proof template |
| [INSTALL_REPORT_dev-linux_2026-07-06.md](https://github.com/Spectating101/hardware-splicer/blob/main/docs/INSTALL_REPORT_dev-linux_2026-07-06.md) | Dev machine validation log (Tier III partial) |

---

## 3. Verification (how we know it works)

**Single command (local):**

```bash
make verify-product-internal
```

| Layer | Makefile target | What it proves |
|-------|-----------------|----------------|
| Engine | `verify-splice-v1` | S2 compile 4/4, S3 loop 3/3, real bench, project package |
| Product | `verify-product-v1` | Above + UI build + `tests/test_splice_product_v1.py` |
| Install | `verify-install-smoke` | `install_splice_v1.sh` + prerequisites |
| Live HTTP | `verify-product-live-smoke` | uvicorn + async `splice-build` job over HTTP |

CI: [`.github/workflows/hardware-splicer.yml`](https://github.com/Spectating101/hardware-splicer/blob/main/.github/workflows/hardware-splicer.yml) — `verify-splice-v1` + UI build + product API tests on Ubuntu.

---

## 4. Engine & agent depth

| Doc | Purpose |
|-----|---------|
| [ENGINE_DONE.md](https://github.com/Spectating101/hardware-splicer/blob/main/docs/ENGINE_DONE.md) | Canonical engine completion gates |
| [AGENT_HANDOFF.md](https://github.com/Spectating101/hardware-splicer/blob/main/docs/AGENT_HANDOFF.md) | Agent / automation runbook |
| [INTEGRATION.md](https://github.com/Spectating101/hardware-splicer/blob/main/docs/INTEGRATION.md) | Runtime flow, environment variables |
| [MCP.md](https://github.com/Spectating101/hardware-splicer/blob/main/docs/MCP.md) | MCP server and tools |
| [DOCUMENTATION_INDEX.md](https://github.com/Spectating101/hardware-splicer/blob/main/docs/DOCUMENTATION_INDEX.md) | Full map of all docs |

---

## 5. Strategy (internal reference — not blocking ship)

| Doc | Purpose |
|-----|---------|
| [COMPETITIVE_PACKAGING_STRATEGY.md](https://github.com/Spectating101/hardware-splicer/blob/main/docs/COMPETITIVE_PACKAGING_STRATEGY.md) | vs Flux / Blueprint / unstructured checklists |
| [MONETIZATION_AND_PRODUCT_ASSESSMENT.md](https://github.com/Spectating101/hardware-splicer/blob/main/docs/MONETIZATION_AND_PRODUCT_ASSESSMENT.md) | Buyers, pricing, risks |
| [DEPLOY_PRODUCT_FUNDING_PLAYBOOK.md](https://github.com/Spectating101/hardware-splicer/blob/main/docs/DEPLOY_PRODUCT_FUNDING_PLAYBOOK.md) | Deploy → product → funding sequence |
| [OFFER_SPLICE_BENCH_KIT_v1.md](https://github.com/Spectating101/hardware-splicer/blob/main/docs/OFFER_SPLICE_BENCH_KIT_v1.md) | Pilot offer template (deferred until Tier III) |

---

## 6. Monorepo boundary (read only if asked)

v1.0 **product SKU** = `src/hardware_splicer/` + `apps/splice-ui/` + splice examples/fixtures.

**Not** the v1 install path:

- [`apps/circuit-ai/`](https://github.com/Spectating101/hardware-splicer/tree/main/apps/circuit-ai) — vision/salvage modules (imported)
- [`apps/mecha-splicer/`](https://github.com/Spectating101/hardware-splicer/tree/main/apps/mecha-splicer) — mechanical (future S4)
- [`apps/3d-splicer/`](https://github.com/Spectating101/hardware-splicer/tree/main/apps/3d-splicer) — 3D (future)

See [apps/README.md](https://github.com/Spectating101/hardware-splicer/blob/main/apps/README.md) and [README_MONOREPO_DEPTH.md](https://github.com/Spectating101/hardware-splicer/blob/main/docs/README_MONOREPO_DEPTH.md).

---

## 7. Key code paths

| Path | Role |
|------|------|
| [`src/hardware_splicer/api.py`](https://github.com/Spectating101/hardware-splicer/blob/main/src/hardware_splicer/api.py) | HTTP API + optional UI static mount |
| [`apps/splice-ui/`](https://github.com/Spectating101/hardware-splicer/tree/main/apps/splice-ui) | Consumer web UI (Vite + React) |
| [`scripts/install_splice_v1.sh`](https://github.com/Spectating101/hardware-splicer/blob/main/scripts/install_splice_v1.sh) | Slim v1 install |
| [`scripts/verify_product_live_smoke.py`](https://github.com/Spectating101/hardware-splicer/blob/main/scripts/verify_product_live_smoke.py) | Live HTTP job smoke |
| [`tests/test_splice_product_v1.py`](https://github.com/Spectating101/hardware-splicer/blob/main/tests/test_splice_product_v1.py) | Product-layer API tests |
| [`Makefile`](https://github.com/Spectating101/hardware-splicer/blob/main/Makefile) | `verify-product-internal` and related targets |

---

## 8. Principle (current phase)

```text
External proof validates maturity.
It does not create maturity.
```

**Sequence:** Tier I–III internal green → alien-machine install report → then pilots, releases page, outreach.

---

*Last updated: July 2026 · v1.0.1*
