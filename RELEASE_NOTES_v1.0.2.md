# Release notes — Hardware-Splicer Splice Agent v1.0.2

**Date:** July 2026  
**Git tag:** `v1.0.2`  
**Type:** Internal maturity + install portability (recommended upgrade from v1.0.1)

---

## Summary

**Internally reproducible system product candidate.** Full bar `make verify-product-internal` passes on dev-linux and lab Windows/WSL2 (`DESKTOP-FGEDHGV`). Install script now generates gitignored PCB/catalog data. Sample Splice Sprint zip included for external reviewers.

---

## What's new

### Internal maturity

- **`make verify-product-internal`** — engine + UI + API + install smoke + live HTTP async job
- **`scripts/verify_product_live_smoke.py`** — product-system smoke over HTTP
- **Install reports:** dev-linux + `docs/INSTALL_REPORT_desktop-fgedhgv-wsl_2026-07-07.md`
- **`docs/GITHUB_START_HERE.md`** — single entry for GitHub / ChatGPT review
- **`docs/EXTERNAL_PROOF_CHECKLIST.md`** — post-maturity conversion kit

### Install fix

- **`scripts/install_splice_v1.sh`** runs `export-engine-pcb-data` + `export-catalog-recipes` after npm install (fixes fresh-clone `FileNotFoundError`)

### Release assets

- **`releases/sample-splice-sprint-robot-repair-cafe.zip`** — golden repair-café `PROJECT_PACKAGE` bundle for reviewers

---

## Upgrade from v1.0.1

```bash
git fetch
git checkout v1.0.2
bash scripts/install_splice_v1.sh
INSTALL_DEV=1 bash scripts/install_splice_v1.sh   # if running verify bar
make verify-product-internal   # optional full bar
```

---

## Verify

```bash
make verify-product-internal
```

CI: `.github/workflows/hardware-splicer.yml` → **Splice Agent v1 bar**

---

## Still not in scope

- Native Windows installer (WSL2 Ubuntu + bash install)
- Public SaaS, billing, in-app auth
- Mass self-serve deployment

See [`RELEASE_NOTES_v1.0.1.md`](RELEASE_NOTES_v1.0.1.md) for packaging polish; [`RELEASE_NOTES_v1.0.0.md`](RELEASE_NOTES_v1.0.0.md) for original v1.0.0 scope.
