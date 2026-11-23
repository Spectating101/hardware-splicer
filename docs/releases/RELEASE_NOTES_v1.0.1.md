# Release notes — Hardware-Splicer Splice Agent v1.0.1

**Date:** July 2026  
**Git tag:** `v1.0.1`  
**Type:** Packaging & documentation polish (recommended upgrade from v1.0.0)

---

## Summary

Professional product envelope for Splice Agent: trimmed README, operator quickstart, support/liability boundaries, operations runbook, demo script, and single-port UI serving. **No breaking API changes** from v1.0.0.

Use this release when presenting to pilots, grant reviewers, or external install validation.

---

## What's new

### Documentation & repo face

- **README** — product-first; monorepo depth moved to `docs/README_MONOREPO_DEPTH.md`
- **`docs/QUICKSTART_SPLICE_v1.md`** — install → doctor → UI in one page
- **`docs/SUPPORT_AND_LIABILITY_v1.md`** — power-on boundary, support tiers, security posture
- **`docs/OPERATIONS_RUNBOOK_v1.md`** — systemd, backup, upgrade, recovery
- **`docs/DEMO_5_MIN_UI.md`** — 5-minute demo script
- **`docs/INSTALL_REPORT_TEMPLATE.md`** — for Windows/Linux/WSL proof later
- **`docs/OFFER_SPLICE_BENCH_KIT_v1.md`** — pilot offer template
- **`CHANGELOG.md`** — semver history

### Deploy

- **`make splice-ui-serve`** — build UI + API on port 8787
- **`HARDWARE_SPLICER_SERVE_UI=1`** — static UI from `apps/splice-ui/dist`
- **`deploy/nginx/splice-agent.conf.example`** — LAN reverse proxy pattern
- Expanded **`deploy/DEPLOY.md`**

### UI (since v1.0.0 tag)

- Build overlay, project summary bar, tab badges
- Quick demo, recent builds, gate/bench workflow polish

---

## Upgrade from v1.0.0

```bash
git fetch
git checkout v1.0.1
bash scripts/install_splice_v1.sh
make splice-ui-build    # if using single-port UI
hs-doctor
```

Engine verify bar unchanged:

```bash
INSTALL_DEV=1 bash scripts/install_splice_v1.sh
make verify-splice-v1
```

---

## Release assets (optional)

Attach to GitHub Release:

1. This file + `CHANGELOG.md`
2. Sample job bundle — after one successful build:
   ```bash
   curl -o sample-project-package.zip \
     http://127.0.0.1:8787/v1/jobs/<job_id>/bundle
   ```
3. Screenshot of Gates tab (demo flow)

---

## Still not in scope

- Public SaaS, in-app auth, billing
- Windows native installer (use WSL2 + bash install)
- PyPI publish

See [`RELEASE_NOTES_v1.0.md`](RELEASE_NOTES_v1.0.md) for original v1.0.0 scope.

---

## Verify

- CI: `.github/workflows/hardware-splicer.yml` → **Splice Agent v1**
- Local: `make verify-splice-v1` + `make splice-ui-build`
