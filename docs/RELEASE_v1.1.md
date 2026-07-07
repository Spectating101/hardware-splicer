# Release v1.1.0 — serious launch

**Product:** Hardware-Splicer Splice Agent **v1.1.0**  
**Tag:** `v1.1.0`  
**One-liner:** Makes prototype handoff inspectable before fabrication or power-on.

This document is the **authoritative launch bar** — not a pilot or alpha checklist.

---

## 1. What v1.1.0 is

```text
v1.0.2  →  bring-up engine + gates + PROJECT_PACKAGE (proven)
v1.1.0  →  + design verification UI + build-files API + readiness verdict
```

**Not:** Flux replacement, SaaS, native Windows product, certified safety sign-off.

---

## 2. Install (clean machine)

```bash
git clone https://github.com/Spectating101/hardware-splicer.git
cd hardware-splicer
git checkout v1.1.0
bash scripts/install_splice_v1.sh
source .venv/bin/activate
hs-doctor
```

**Requires:** Python 3.12+, KiCad 9+ (`kicad-cli` on PATH), Node 18+.

**Windows:** WSL2 Ubuntu — same commands inside WSL.

---

## 3. Verify (must pass before you trust the release)

### Automated

```bash
make verify-product-internal
```

Runs:

| Step | Proves |
|------|--------|
| `verify-product-v1` | Engine S2/S3, UI build, product API tests |
| `verify-install-smoke` | Slim install + API import |
| `verify-product-live-smoke` | HTTP health, UI root, async splice-build job |

Additional v1.1 tests (also in CI):

```bash
PYTHONPATH=src pytest tests/test_build_files_security.py tests/test_oss_integrations_api.py tests/test_build_files_api.py -q
```

### Manual (once per release — sign checklist)

See [`RELEASE_CHECKLIST_v1.1.md`](RELEASE_CHECKLIST_v1.1.md).

Minimum path:

```text
make splice-ui-serve → http://127.0.0.1:8787
Quick demo → Readiness verdict → Design verify → Gates → Download zip
```

---

## 4. Deploy

### Demo / lab (single port)

```bash
make splice-ui-serve
```

### Production-style (systemd)

1. `make splice-ui-build`  
2. Enable `deploy/systemd/hardware-splicer.service.example` with `HARDWARE_SPLICER_SERVE_UI=1`  
3. Optional: `deploy/nginx/splice-agent.conf.example` for TLS + API key on LAN  

Details: [`deploy/DEPLOY.md`](../deploy/DEPLOY.md), [`OPERATIONS_RUNBOOK_v1.md`](OPERATIONS_RUNBOOK_v1.md).

---

## 5. GitHub Release

```bash
gh release create v1.1.0 \
  --title "v1.1.0 — Design Verification Workbench" \
  --notes-file RELEASE_NOTES_v1.1.0.md
```

Attach: `releases/sample-splice-sprint-robot-repair-cafe.zip` (gates + package proof).

---

## 6. Version surfaces (must align on tag)

| Surface | Expected |
|---------|----------|
| `pyproject.toml` | `1.1.0` |
| `src/hardware_splicer/_version.py` | `1.1.0` |
| `GET /health` | `"version": "1.1.0"` |
| OpenAPI `info.version` | `1.1.0` |
| Git tag | `v1.1.0` |

---

## 7. Support boundary

Power-on authorization remains **operator-owned**. See [`SUPPORT_AND_LIABILITY_v1.md`](SUPPORT_AND_LIABILITY_v1.md).

---

## 8. Claims

Outbound copy must match [`CLAIMS_BOUNDARY.md`](CLAIMS_BOUNDARY.md). Preferred sentence:

> Self-hosted bring-up workbench with design verification and bench gates before fabrication or power-on.

---

*July 2026 · v1.1.0 stable release*
