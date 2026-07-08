# Changelog

All notable changes to **Hardware-Splicer Splice Agent** are documented here.

Format based on [Keep a Changelog](https://keepachangelog.com/). Versioning follows semver for the product tag.

---

## [1.1.0-alpha.7] - 2026-07-09

### Added

- Canvas module catalog expanded **27 → 50** with pin/footprint contract coverage
- `docs/AGENT_DRY_RUN_CHECKLIST.md` — zero-help external operator proof checklist

### Changed

- `scripts/agent_quickstart_verify.sh` — catalog assert `count` ≥ 50
- `docs/PRODUCT_SCALE_PLAN.md` — Phase 1 catalog milestone marked complete

---

## [1.1.0-alpha.6] - 2026-07-09

### Added

- `POST /v1/jobs/compose-agent-loop` — async agent-loop compose with poll `/v1/jobs/{id}/result`
- HTTP + job backend tests for async agent-loop path
- FGEDHGV install report: Qwen curl 3 PASS on alien WSL

### Changed

- `scripts/agent_quickstart_verify.sh` — sync + async job steps; `deploy_alien_quickstart.sh` for FGEDHGV
- `verify_product_live_smoke.py` — compose-agent-loop in live bar
- Canvas pin contract: fixed `dht22` / `mini-pump-5v` footprint pad ids

---

### Added

- `docs/PRODUCT_SCALE_PLAN.md` — phased product scale plan (Phase 0–3)
- `docs/AGENT_QUICKSTART.md` — 15-minute agent path (3 curls + 3 MCP tools)
- `docs/AGENT_BUILD_DIR_POLICY.md` — MCP `hs_design_quality` build_dir rules
- Phrase-only `POST /v1/compose/agent-loop` test coverage

### Changed

- Design Studio: agent-loop emits `PROJECT_PACKAGE` when project goal set; DRC panel shows picked modules
- Design Studio: stable React Flow `onSelectionChange` (no infinite re-render)

### Documentation

- `DOCUMENTATION_INDEX.md`, `AGENT_HANDOFF.md` — links to scale plan and quickstart

---

## [1.1.0] - 2026-07-08

### Added

- **Design verify** tab — KiCanvas preview, compile truth, BOM, fab manifest, exports
- **Readiness verdict** hero — blockers before fab / power-on
- `/v1/build-files/*` API — secured artifact, BOM, fab-manifest, recheck, export-views
- **Interface lab** — canvas, circuit-json, KiCad netlist paste; OSS integration catalog
- `make verify-ui-interface-smoke` — v1.1 interface HTTP smoke
- `docs/RELEASE_v1.1.md`, `docs/RELEASE_CHECKLIST_v1.1.md`

### Changed

- Home hero and pipeline — design verification as first-class flow
- CI **Splice Agent v1** job — v1.1 security/interface tests + live HTTP smoke
- Product version **1.1.0** aligned across pyproject, `/health`, OpenAPI

### Documentation

- Stable release notes: `RELEASE_NOTES_v1.1.0.md`
- Supersedes v1.1.0-alpha tags for production deploy references

---

## [1.0.2] - 2026-07-07

### Added

- `make verify-product-internal` — full internal maturity command chain
- `scripts/verify_product_live_smoke.py` — live HTTP async job smoke
- `docs/GITHUB_START_HERE.md`, `docs/EXTERNAL_PROOF_CHECKLIST.md`
- `docs/INSTALL_REPORT_dev-linux_2026-07-06.md`, `docs/INSTALL_REPORT_desktop-fgedhgv-wsl_2026-07-07.md`
- `releases/sample-splice-sprint-robot-repair-cafe.zip` — reviewer sample bundle

### Fixed

- `scripts/install_splice_v1.sh` — export `engine_pcb_data.json` and `catalog_recipes.json` on fresh install

### Changed

- Internal maturity Tier III: alien-machine pass on lab Windows/WSL2

---

## [1.0.1] - 2026-07-06

### Added

- Product-first `README.md` with CI badge and quick start
- `docs/QUICKSTART_SPLICE_v1.md` — single operator install path
- `docs/SUPPORT_AND_LIABILITY_v1.md` — support tiers and power-on boundary
- `docs/OPERATIONS_RUNBOOK_v1.md` — lab deploy, backup, upgrade, recovery
- `docs/DEMO_5_MIN_UI.md` — repeatable auditor/pilot demo script
- `docs/INSTALL_REPORT_TEMPLATE.md` — external machine proof template
- `docs/OFFER_SPLICE_BENCH_KIT_v1.md` — pilot offer template
- `docs/README_MONOREPO_DEPTH.md` — engine/intake/API depth moved from README
- `apps/README.md` — monorepo vs v1 product boundary
- `deploy/nginx/splice-agent.conf.example` — LAN TLS + API key pattern
- `make splice-ui-serve` — single-port API + built UI
- `HARDWARE_SPLICER_SERVE_UI` — serve `apps/splice-ui/dist` from API

### Changed

- Splice UI: build overlay, summary bar, tab badges, quick demo, toasts
- `deploy/DEPLOY.md` expanded with UI serve and nginx pointer
- `docs/DOCUMENTATION_INDEX.md` updated for v1.0.1 doc set

### Documentation

- Professional packaging polish release — no engine behavior change required for upgrade from 1.0.0
- Internal: [`docs/COMPETITIVE_PACKAGING_STRATEGY.md`](docs/COMPETITIVE_PACKAGING_STRATEGY.md) — competitor map and completion priorities

---

## [1.0.0] - 2026-07

### Added

- Splice Agent v1.0 product layer: PROJECT_PACKAGE, intent clarifier, async jobs
- Slim install: `scripts/install_splice_v1.sh`, `hs-doctor`, `hs-serve`, `hs-mcp`
- `apps/splice-ui/` consumer workbench
- CI job `splice-v1`: `make verify-splice-v1` + UI build
- Release notes, deploy stub, funding/deploy playbooks

See [`RELEASE_NOTES_v1.0.md`](RELEASE_NOTES_v1.0.md) for full v1.0.0 scope.

[1.1.0]: https://github.com/Spectating101/hardware-splicer/releases/tag/v1.1.0
[1.0.2]: https://github.com/Spectating101/hardware-splicer/releases/tag/v1.0.2
[1.0.1]: https://github.com/Spectating101/hardware-splicer/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/Spectating101/hardware-splicer/releases/tag/v1.0.0
