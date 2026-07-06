# Install report — dev machine (internal)

Copy of `INSTALL_REPORT_TEMPLATE.md` — **internal validation**, not external pilot.

---

## Report metadata

| Field | Value |
|-------|-------|
| **Tester** | automated + maintainer |
| **Date** | 2026-07-06 |
| **Git tag / commit** | `main` post internal-maturity hardening |
| **Machine name** | dev-linux (primary workstation) |
| **OS** | Linux (Debian-based) |
| **KiCad version** | 9.0.2 (`kicad-cli --version`) |
| **Python** | 3.13.5 |
| **Node** | v22.21.1 |

---

## Install steps followed

- [x] `git clone` / existing checkout at repo root
- [x] `bash scripts/install_splice_v1.sh`
- [x] `source .venv/bin/activate`
- [x] `hs-doctor`

**Install script modifications required?** No

---

## Doctor output

```
ok=True demo_ready=True fab_export_ready=True
dependencies: kicad_cli:ok, node:ok, npm:ok, fastapi:ok, pytest:ok
cadquery:missing (optional — not required for splice v1)
```

| Check | Pass / Fail |
|-------|-------------|
| Python venv | Pass |
| KiCad CLI | Pass |
| Node / npm | Pass |
| API import | Pass |

---

## Verification (hard bar)

- [x] `make verify-product-v1` — **PASS** (exit 0)
  - `verify-splice-v1`: S2 4/4, S3 loop 3/3, real bench PASS
  - `splice-ui-build`: PASS
  - `test_splice_product_v1.py`: 8 passed
- [x] `make verify-install-smoke` — **PASS**
- [x] `make verify-product-live-smoke` — **PASS**
  - health, examples, UI `/`, async `splice-build` job → `project_package`

---

## UI demo

- [x] `HARDWARE_SPLICER_SERVE_UI=1` + uvicorn — health + UI root
- [x] Live smoke validates full HTTP job path

---

## API smoke

- [x] `GET /health` → 200, `ok: true`, `version: 1.0.1`
- [x] `POST /v1/jobs/splice-build` → poll → `project_package` with gates

---

## Manual fixes required

None on this machine for current `main`.

---

## Verdict

| | |
|--|--|
| **Install: PASS** | |
| **Engine bar: PASS** | |
| **Product bar: PASS** | |
| **Live job smoke: PASS** | |
| **Ready for external pilot?** | **No** — Tier III alien machine (spare Windows/Linux) still open |

**Notes:** Internal maturity Tier I–II green on dev machine. Next internal step: repeat this report on non-dev hardware.

---

## Commands to reproduce

```bash
make verify-product-internal
```
