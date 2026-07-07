# Start here (GitHub / external review)

**Repo:** [Spectating101/hardware-splicer](https://github.com/Spectating101/hardware-splicer)  
**Product:** Splice Agent **v1.1.0** — auditable hardware bring-up + design verification  
**Status:** Stable release — see [`RELEASE_v1.1.md`](RELEASE_v1.1.md)

Use this page as the **single entry** when browsing on GitHub.

---

## 1. What to read first (15 minutes)

| # | Doc | Purpose |
|---|-----|---------|
| 1 | [RELEASE_v1.1.md](RELEASE_v1.1.md) | **Install, verify, deploy** |
| 2 | [RELEASE_NOTES_v1.1.0.md](../RELEASE_NOTES_v1.1.0.md) | What shipped in v1.1.0 |
| 3 | [QUICKSTART_SPLICE_v1.md](QUICKSTART_SPLICE_v1.md) | Install → doctor → first build |
| 4 | [DEMO_5_MIN_UI.md](DEMO_5_MIN_UI.md) | Demo script |
| 5 | [RELEASE_CHECKLIST_v1.1.md](RELEASE_CHECKLIST_v1.1.md) | Sign before publish |

---

## 2. Verify

```bash
make verify-product-internal
```

CI: **Splice Agent v1** job on GitHub Actions.

---

## 3. OSS interface layer (v1.1.0)

| Doc | Purpose |
|-----|---------|
| [V1.1_INTERFACE_PREVIEW.md](V1.1_INTERFACE_PREVIEW.md) | Scope boundary |
| [OSS_INTEGRATION_STATUS.md](OSS_INTEGRATION_STATUS.md) | Wired vs planned |
| [BUILD_FILES_API_SECURITY.md](BUILD_FILES_API_SECURITY.md) | API security model |

**Try:** `make splice-ui-serve` → Quick demo → **Design verify**

---

## 4. Claims

Outbound copy: [`CLAIMS_BOUNDARY.md`](CLAIMS_BOUNDARY.md)

> Self-hosted bring-up workbench with design verification and bench gates before fabrication or power-on.

---

*Last updated: July 2026 · v1.1.0*
