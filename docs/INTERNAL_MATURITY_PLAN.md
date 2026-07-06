# Internal maturity plan — Splice Agent v1

**Purpose:** Define what **thoroughly solid and mature** means **before any external pilot, outreach, or funding push**. This is an **engineering and product-system** bar — not marketing docs.

**Audience:** Founder, agents, future contributors.  
**Status:** July 2026 · Active  
**Related:** [`ENGINE_DONE.md`](ENGINE_DONE.md) · [`RELEASE_V1.md`](RELEASE_V1.md) · [`COMPETITIVE_PACKAGING_STRATEGY.md`](COMPETITIVE_PACKAGING_STRATEGY.md)

---

## 1. Principle

```text
External proof validates maturity.
It does not create maturity.
```

**Internal maturity** = the system behaves predictably, verifiably, and maintainably when **you** are the only user — across clean install, engine, API, UI, jobs, and ops paths.

**External activity** (outreach, pilots, grants) starts only when **Tier I–III** below are green.

---

## 2. Maturity tiers (internal)

### Tier I — Engine truth (must not regress)

| Gate | Command | Status |
|------|---------|--------|
| Doctor | `hs-doctor` | Required |
| S2 compile | `make verify-splice` | Required |
| S3 bench loop | `make verify-splice-loop` | Required |
| S3 real bench | `make verify-splice-real-bench` | Required |
| Project package | `make test-project-package` | Required |
| Combined | `make verify-splice-v1` | **Tier I bar** |

**Meaning:** KiCad compile, gates, and package emission are CI-backed facts.

---

### Tier II — Product system (API + jobs + UI spine)

| Gate | What it proves |
|------|----------------|
| Version single source | `pyproject.toml` = `_version.py` = `/health` = OpenAPI |
| HTTP product routes | examples, clarify, jobs, bench — tested without manual curl |
| Async job lifecycle | submit → poll → result shape for splice-build |
| UI production build | `make splice-ui-build` exit 0 |
| UI static serve | `HARDWARE_SPLICER_SERVE_UI=1` serves `/` + `/assets` when `dist/` exists |
| Product pytest | `tests/test_splice_product_v1.py` |
| Combined | `make verify-product-v1` |

**Meaning:** The **shippable SKU** (not just engine library) is wired and tested.

---

### Tier III — Install & ops reproducibility (internal)

| Gate | What it proves |
|------|----------------|
| Slim install script | `bash scripts/install_splice_v1.sh` on **this** machine after `rm -rf .venv` |
| Dev install | `INSTALL_DEV=1` + `make verify-product-v1` |
| Single-port run | `make splice-ui-serve` → health + UI + quick demo path (manual once per release) |
| Ops docs match code | `OPERATIONS_RUNBOOK_v1.md` env vars = `INTEGRATION.md` |
| Alien machine (optional internal) | `INSTALL_REPORT_TEMPLATE.md` filled — **your** Windows/Linux box, not a customer |

**Meaning:** You can reinstall and operate without tribal knowledge.

---

### Tier IV — Professional envelope (done at v1.0.1)

| Item | Doc / artifact |
|------|----------------|
| Product README | `README.md` |
| Quickstart | `QUICKSTART_SPLICE_v1.md` |
| Support boundary | `SUPPORT_AND_LIABILITY_v1.md` |
| Ops runbook | `OPERATIONS_RUNBOOK_v1.md` |
| Changelog / semver | `CHANGELOG.md`, tags |

**Meaning:** When you *do* go external, the repo does not embarrass you. **Not sufficient alone for maturity.**

---

### Tier V — Field maturity (defer until Tier I–III green)

| Item | Why deferred |
|------|--------------|
| Paid pilot | Needs Tier III on 2+ environments |
| Grant application | Needs partner letter + Tier I–III |
| Hosted SaaS | Different product |
| Windows native installer | WSL2 sufficient for v1 internal bar |

---

## 3. Single internal completion command

```bash
make verify-product-v1
```

Runs:

1. `verify-splice-v1` (Tier I)  
2. `pytest tests/test_splice_product_v1.py` (Tier II)  
3. `make splice-ui-build` (Tier II)

**Release discipline:** No tag `v1.0.x` without local `make verify-product-v1` green.

---

## 4. Known internal gaps (honest backlog)

Prioritized for **maturity**, not competitor parity.

| Priority | Gap | Tier | Notes |
|----------|-----|------|-------|
| **P0** | Version drift (`api.py` hardcoded) | II | Fix — use `_version` |
| **P0** | No product-layer API tests | II | `test_splice_product_v1.py` |
| **P0** | CI runs engine bar only | II | Add product tests to `splice-v1` job |
| **P1** | No automated install smoke | III | `scripts/verify_install_smoke.sh` |
| **P1** | Job error messages → UI | II | User-visible failure copy |
| **P1** | Bench instrument auto-fill | II | DMM path — after internal demo works |
| **P2** | BOM LCSC enrich in UI | II | Engine hooks exist |
| **P2** | Wiring Mermaid render | II | Package has data |
| **P2** | API key middleware | III | nginx sufficient until site license |
| **P3** | E2E Playwright in CI | II | Heavy; manual demo ok for now |

**Explicitly not internal maturity:** more strategy docs, competitor essays, outreach templates.

---

## 5. Definition of done (internal product)

You may call the internal product **mature enough for external** when:

| # | Criterion |
|---|-----------|
| 1 | `make verify-product-v1` green locally and on GitHub Actions |
| 2 | Reinstall from `install_splice_v1.sh` on clean venv without manual fixes |
| 3 | `make splice-ui-serve` → full demo path once without code edits |
| 4 | Version tag matches all surfaces (`health`, OpenAPI, README) |
| 5 | One `INSTALL_REPORT` filled on non-dev machine (your spare box — still internal) |
| 6 | No P0 items open in §4 |

**Not required for internal done:** paid pilot, grant, sample zip on GitHub Release, demo video for strangers.

---

## 6. Work allocation (internal phase)

```text
70%  Tier II–III engineering (tests, version, install smoke, UI/API hardening)
20%  Tier I maintenance (KiCad bumps, regressions)
10%  Tier IV doc fixes only when code changes
 0%  external outreach, competitive docs, pitch PDFs
```

---

## 7. Relationship to competitors

Competitive positioning matters **after** Tier I–III. See [`COMPETITIVE_PACKAGING_STRATEGY.md`](COMPETITIVE_PACKAGING_STRATEGY.md) — **external chapter**, not internal gate.

Internal maturity question is not "beat Flux?" It is:

> Does the splice agent **reliably** do intake → compile → package → gates on a reproducible install?

---

## 8. Changelog

| Date | Change |
|------|--------|
| 2026-07 | Initial internal maturity plan; `verify-product-v1` |
