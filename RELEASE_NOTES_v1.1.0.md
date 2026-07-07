# Release notes — v1.1.0

**Product:** Hardware-Splicer Splice Agent  
**Predecessor:** [v1.0.2](RELEASE_NOTES_v1.0.2.md)  
**Date:** July 2026

---

## Summary

**v1.1.0** is the first **stable interface release**: auditable hardware bring-up plus **design verification** in the product UI — KiCanvas preview, compile BOM, fab readiness, and bench gates — on the same KiCad compile spine as v1.0.2.

> Self-hosted hardware bring-up workbench: inspect handoff **before** fabrication or power-on.

---

## What ships

### Core (unchanged authority from v1.0.2)

- Donor intake → KiCad carrier with DRC truth  
- Bench measurement gates + power-on boundary  
- `PROJECT_PACKAGE` zip handoff  
- HTTP API + MCP + async jobs  

### New in v1.1.0 — Design verification

- **Readiness verdict** — blockers before fab / power-on on every project  
- **Design verify tab** — flow stepper, KiCanvas, compile truth, BOM, fab manifest  
- **Human-readable exports** — PDF/SVG via `kicad-cli` on demand  
- **Recheck after KiCad edit** — DRC/ERC refresh (`/v1/build-files/recheck`)  

### Interface lab (adapter surface)

- Canvas compose, circuit-json, KiCad netlist fixtures + paste  
- OSS integration catalog  

### API (`/v1/build-files/*`)

Bounded, secured endpoints: list, content, design-quality, artifacts, bom, fab-manifest, export-views, circuit-json, download, autoroute (confirm), recheck.

See [`docs/BUILD_FILES_API_SECURITY.md`](docs/BUILD_FILES_API_SECURITY.md).

---

## Verify bar (release)

```bash
make verify-product-internal
make verify-ui-interface-smoke   # with API on :8787
```

CI **Splice Agent v1** job runs engine bar, UI build, product tests, v1.1 security/interface tests, and live HTTP smoke.

---

## Deploy

```bash
git checkout v1.1.0
bash scripts/install_splice_v1.sh
source .venv/bin/activate
make splice-ui-serve
```

See [`docs/RELEASE_v1.1.md`](docs/RELEASE_v1.1.md) and [`deploy/DEPLOY.md`](deploy/DEPLOY.md).

---

## Out of scope (unchanged)

- Public SaaS / multi-tenant  
- Native Windows installer (use WSL2)  
- Flux-class browser ECAD  
- Production autoroute as default  
- Electrical certification sign-off  

---

## Upgrade from v1.0.2

No breaking changes to core splice/build endpoints. Rebuild UI (`make splice-ui-build`) or use `make splice-ui-serve`.

---

## Documentation

- [`docs/RELEASE_v1.1.md`](docs/RELEASE_v1.1.md) — install, verify, deploy  
- [`docs/V1.1_INTERFACE_PREVIEW.md`](docs/V1.1_INTERFACE_PREVIEW.md) — scope boundary  
- [`docs/CLAIMS_BOUNDARY.md`](docs/CLAIMS_BOUNDARY.md) — allowed claims  
