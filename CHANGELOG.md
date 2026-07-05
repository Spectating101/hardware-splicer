# Changelog

All notable changes to **Hardware-Splicer Splice Agent** are documented here.

Format based on [Keep a Changelog](https://keepachangelog.com/). Versioning follows semver for the product tag.

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

---

## [1.0.0] - 2026-07

### Added

- Splice Agent v1.0 product layer: PROJECT_PACKAGE, intent clarifier, async jobs
- Slim install: `scripts/install_splice_v1.sh`, `hs-doctor`, `hs-serve`, `hs-mcp`
- `apps/splice-ui/` consumer workbench
- CI job `splice-v1`: `make verify-splice-v1` + UI build
- Release notes, deploy stub, funding/deploy playbooks

See [`RELEASE_NOTES_v1.0.md`](RELEASE_NOTES_v1.0.md) for full v1.0.0 scope.

[1.0.1]: https://github.com/Spectating101/hardware-splicer/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/Spectating101/hardware-splicer/releases/tag/v1.0.0
