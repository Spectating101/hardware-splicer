# Release notes — v1.1.0-alpha.1 (draft)

**Codename:** v1.1-interface-preview  
**Branch:** `main`  
**Predecessor:** [v1.0.2](RELEASE_NOTES_v1.0.2.md) (stable bring-up proof)

---

## Summary

Hardware-Splicer **v1.1.0-alpha.1** exposes the existing KiCad compile spine through an OSS interface layer — without replacing the authority model (DRC, gates, `PROJECT_PACKAGE`).

> Self-hosted auditable hardware bring-up + design verification workbench.

---

## Design tab

- **KiCanvas** read-only board/schematic preview
- **Compile truth** from `DESIGN_QUALITY` / `KICAD_DRC`
- **Compile BOM** table (graceful when JLC/LCSC hints absent)
- **Fab artifact coverage** vs KiBot reference (present / missing / optional / planned)
- **Human-readable exports** — PDF/SVG/PNG via `kicad-cli` on demand
- **Artifact download** — circuit-json, KiCad, fab zip, `PROJECT_PACKAGE`

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

- `artifacts`, `bom`, `fab-manifest`, `export-views`, `circuit-json`, `download`, `autoroute` (confirm required)
- Security: output-root allow-list, traversal rejection, suffix allow-list, size caps — see [`docs/BUILD_FILES_API_SECURITY.md`](docs/BUILD_FILES_API_SECURITY.md)

---

## Documentation

- [`docs/V1.1_INTERFACE_PREVIEW.md`](docs/V1.1_INTERFACE_PREVIEW.md)
- [`docs/OSS_INTEGRATION_STATUS.md`](docs/OSS_INTEGRATION_STATUS.md)
- [`docs/ATOPILE_IMPORT.md`](docs/ATOPILE_IMPORT.md)
- [`docs/KICAD_MCP_SIDECAR.md`](docs/KICAD_MCP_SIDECAR.md)

---

## Not in this alpha

- Tagged GitHub Release (draft notes only until bar is green on a release branch)
- KiCad MCP bundled workflow (documented sidecar only)
- JLC enrich UI toggle
- Native Windows installer

---

## Upgrade from v1.0.2

No breaking API changes to core splice/build endpoints. New UI panels require `make splice-ui-dev` or rebuilt static assets from `hs-serve`.

---

*Draft — do not publish as GitHub Release until `verify-product-v1` + security tests pass on release branch.*
