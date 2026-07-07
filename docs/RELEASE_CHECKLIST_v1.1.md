# Release checklist — v1.1.0 (sign before publish)

**Release:** v1.1.0  
**Date:** ___________  
**Signer:** ___________

Check each item. Do not publish GitHub Release until all automated items are green.

---

## Automated (CI + local)

- [ ] `make verify-product-v1` — PASS locally  
- [ ] `make verify-product-internal` — PASS locally  
- [ ] GitHub Actions **Splice Agent v1** job — green on release commit  
- [ ] `PYTHONPATH=src pytest tests/test_build_files_security.py tests/test_oss_integrations_api.py -q` — PASS  

---

## Version alignment

- [ ] `pyproject.toml` version = `1.1.0`  
- [ ] `_version.py` = `1.1.0`  
- [ ] `curl -s localhost:8787/health` shows `"version":"1.1.0"` after install  
- [ ] Git tag `v1.1.0` points to release commit  

---

## Manual UI (5 min)

On `make splice-ui-serve` build:

- [ ] Engine: Online  
- [ ] Quick demo completes  
- [ ] **Readiness verdict** shows hold or OK with blocker list  
- [ ] **Design verify** — KiCanvas + BOM + fab manifest load  
- [ ] **Gates** tab — verdict visible  
- [ ] Download zip works  

---

## Deploy smoke

- [ ] Fresh `install_splice_v1.sh` on clean venv (or alien machine report filed)  
- [ ] `hs-doctor` — demo_ready acceptable  

---

## Publish

- [ ] `RELEASE_NOTES_v1.1.0.md` reviewed  
- [ ] GitHub Release `v1.1.0` created (stable, not prerelease)  
- [ ] Sample zip attached if available  

---

## Signed

All items checked: ___________  Date: ___________
