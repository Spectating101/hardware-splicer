# Release notes — v1.1.0-alpha.1 (draft)

**Codename:** v1.1-interface-preview  
**Branch:** `main`  
**Predecessor:** [v1.0.2](RELEASE_NOTES_v1.0.2.md) (stable bring-up proof)  
**Release-candidate commit:** `e4e75f5` — interface UX polish + UI smoke target

---

## Summary

Hardware-Splicer **v1.1.0-alpha.1** exposes the existing KiCad compile spine through an OSS interface layer — without replacing the authority model (DRC, gates, `PROJECT_PACKAGE`).

> Self-hosted auditable hardware bring-up + **design verification** workbench.

---

## Design verify tab (first-class flow)

- **Design flow stepper** — Visual → Truth → Readiness → Exports
- **KiCanvas** read-only board/schematic preview
- **Compile truth** from `DESIGN_QUALITY` / `KICAD_DRC`
- **Compile BOM** table (graceful when JLC/LCSC hints absent)
- **Fab artifact coverage** vs KiBot reference (present / missing / optional / planned)
- **Human-readable exports** — PDF/SVG/PNG via `kicad-cli` on demand
- **Recheck after KiCad edit** — DRC/ERC refresh via `/v1/build-files/recheck`
- **Artifact download** — circuit-json, KiCad, fab zip, `PROJECT_PACKAGE`

---

## Home + project UX (e4e75f5)

- v1.1 positioning on home hero and 5-step pipeline (includes **Verify**)
- **Design verify** tab highlight in project navigation
- Sidebar recent builds deduped + human-readable project names
- Interface lab path-help cards; fixture labels from module IDs
- OSS integration catalog with friendly fallback when API is stale
- Favicon + `make verify-ui-interface-smoke` HTTP smoke target

---

## Wiring tab

- **Mermaid topology** diagram from synthesis operators (CDN; operator cards remain fallback)

---

## Interface lab (adapter proving ground)

- Canvas → `/v1/compose-canvas`
- circuit-json fixtures → `/v1/netlist-compile`
- KiCad netlist fixtures + **paste box** (SKiDL / atopile / Eeschema)
- OSS integration catalog (`GET /v1/integrations/catalog`)

Explicitly **not** the main product wizard path.

---

## API

New bounded endpoints under `/v1/build-files/*`:

- `list`, `content`, `design-quality`, `artifacts`, `bom`, `fab-manifest`, `export-views`, `circuit-json`, `download`, `autoroute` (confirm required), `recheck`
- Security: output-root allow-list, traversal rejection, suffix allow-list, size caps — see [`docs/BUILD_FILES_API_SECURITY.md`](docs/BUILD_FILES_API_SECURITY.md)

---

## Verification bar (before GitHub Release tag)

```bash
make verify-product-v1
make verify-ui-interface-smoke    # API on :8787
pytest tests/test_build_files_security.py tests/test_oss_integrations_api.py -q
```

Manual: Home → Quick demo → **Design verify** (KiCanvas + BOM + fab) → Interface lab compile → recent build reload.

---

## Documentation

- [`docs/V1.1_INTERFACE_PREVIEW.md`](docs/V1.1_INTERFACE_PREVIEW.md)
- [`docs/OSS_INTEGRATION_STATUS.md`](docs/OSS_INTEGRATION_STATUS.md)
- [`docs/ATOPILE_IMPORT.md`](docs/ATOPILE_IMPORT.md)
- [`docs/KICAD_MCP_SIDECAR.md`](docs/KICAD_MCP_SIDECAR.md)

---

## Not in this alpha

- GitHub Release asset (draft notes only until manual UI pass is green)
- KiCad MCP bundled workflow (documented sidecar + dev profile only)
- JLC enrich UI toggle
- Native Windows installer
- Mermaid offline fallback

---

## Upgrade from v1.0.2

No breaking API changes to core splice/build endpoints. New UI panels require `make splice-ui-dev` or rebuilt static assets from `make splice-ui-serve`.

---

*Draft — tag `v1.1.0-alpha.1` only after release-candidate verify + manual UI pass on `main`.*
