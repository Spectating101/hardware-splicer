# Release notes — Hardware-Splicer Splice Agent v1.0.0

**Date:** July 2026  
**Git tag:** `v1.0.0`  
**Product:** Self-hosted **Splice Agent** — donor intake → KiCad carrier compile → bench gates → PROJECT_PACKAGE.

---

## Summary

First bounded **product release** of the splice spine: installable Python package, console entrypoints, HTTP/MCP surfaces, async splice jobs, Blueprint-shaped project packages with **GATES**, optional consumer UI, and CI-backed verification targets.

This is the release where Hardware-Splicer stops being “engine + demos only” and becomes an operable agent you can install, run on a bench machine, and hand artifacts to a customer or partner.

---

## What’s in v1.0

### Engine & verification

- Splice manifest cases: **S2 compile** (`make verify-splice`, 4/4)
- Golden bench loop: **S3 simulated** (`make verify-splice-loop`, 3/3)
- Golden real bench replay: **S3 real capture** (`make verify-splice-real-bench`)
- Combined bar: `make verify-splice-v1` (doctor + package tests + S2/S3)

### Project package layer

- `PROJECT_PACKAGE.json` — INFO, BOM, wiring, instructions, **gates**
- `PROJECT_PAGE.md`, `WIRING_GUIDE.md`, `ASSEMBLY_GUIDE.md`
- Gate verdicts: `BLOCKED`, `COMPILE_READY_REVIEW_BENCH`, `POWER_ON_AUTHORIZED`, etc.
- Emitted on splice build and synthesis bridge paths

### Install & packaging

- `pyproject.toml` — version `1.0.0`, `pip install -e .`
- `requirements-splice-v1.txt` — pinned slim runtime
- `scripts/install_splice_v1.sh` — customer install (no dev deps by default)
- Console: `hs-doctor`, `hs-serve`, `hs-mcp`
- `deploy/DEPLOY.md` + systemd example unit

### APIs & agents

- HTTP: `/v1/splice-and-build`, `/v1/jobs/splice-build`, bench status/submit, examples, intent clarify
- SQLite-backed async jobs with result/bundle download
- MCP tools including `hs_splice_build`, `hs_render_project_package`, synthesis planners
- CORS for local splice-ui dev

### UI (optional)

- `apps/splice-ui/` — home, wizard, examples, async builds, package tabs, bench submit, zip download
- Not required for headless/agent deployments

### Documentation

- `docs/RELEASE_V1.md`, `PACKAGING_AND_DEPLOYMENT.md`, `DEPLOY_PRODUCT_FUNDING_PLAYBOOK.md`
- `docs/DOCUMENTATION_INDEX.md` — canonical doc map

---

## What’s not in v1.0

- Public multi-tenant SaaS, auth, or billing
- Production autorouted copper (default cosmetic preview)
- Full Circuit-AI canvas / Flux-class editor
- Mechanical splice product (mecha-splicer as primary SKU)
- Donor photo → vision in consumer UI (API exists; UI not wired)
- Guaranteed “any English sentence → any PCB”
- PyPI publish (install from git checkout)

---

## Upgrade / install

```bash
git checkout v1.0.0
bash scripts/install_splice_v1.sh          # customer
INSTALL_DEV=1 bash scripts/install_splice_v1.sh   # developers + pytest
hs-doctor
make verify-splice-v1                      # requires KiCad 9+, Node 18+, INSTALL_DEV=1
```

**Prerequisites:** Python 3.12+, `kicad-cli` 9+, Node 18+ (KiCad graph compiler).

---

## Known limitations

- KiCad must run on the same machine as compile (no serverless KiCad).
- `splice_and_build` may return `ok: false` when bench gates are open — that is honest gate semantics, not necessarily compile failure.
- GitHub Actions runs the **splice-v1** job on pushes that touch product paths; full monorepo `verify` remains a separate heavier workflow.
- Fresh Ubuntu VM install is recommended before production pilots; document any drift in an issue.

---

## Contributors & proof

- Engine: ~37k LOC Python, 576+ tests at release time
- Verify locally: `make verify-splice-v1`
- CI: `.github/workflows/hardware-splicer.yml` → job `splice-v1`

---

## v1.1+ (not committed)

- One-page offer + liability boundary docs for commercial pilots
- Pilot case study from first paid splice customer
- `hs-serve` static hosting of built splice-ui
- Donor vision upload in UI
