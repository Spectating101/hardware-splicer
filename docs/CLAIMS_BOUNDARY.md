# Claims boundary — Splice Agent v1.0.2 (internal + outbound)

**Purpose:** What we **may** say after competitor comparison and release credibility check. Protects pilots, grants, and conversations.

**Legal detail:** [`SUPPORT_AND_LIABILITY_v1.md`](SUPPORT_AND_LIABILITY_v1.md)  
**Competitor context:** [`COMPETITOR_SCORECARD_v1.0.2.md`](COMPETITOR_SCORECARD_v1.0.2.md)

---

## Allowed claims (evidence-backed)

| Claim | Evidence |
|-------|----------|
| Self-hosted bring-up workflow | `install_splice_v1.sh`, `OPERATIONS_RUNBOOK_v1.md` |
| KiCad-backed compile truth | `verify-splice-v1`, DRC in `build_compilation/` |
| Bench gate tracking | `SPLICE_BENCH_SESSION.json`, `gates` in `PROJECT_PACKAGE` |
| `PROJECT_PACKAGE` handoff zip | Release `sample-splice-sprint-robot-repair-cafe.zip` |
| Failure debuggability | `COMPILE_CASEFILE.json` on compile failure |
| Operator-owned power-on authorization | `power_on_authorized`, `SUPPORT_AND_LIABILITY_v1.md` |
| Internal reproducibility | `make verify-product-internal` PASS dev-linux + lab WSL2; install reports |
| HTTP + MCP agent surfaces | `/v1/jobs`, `hs-mcp`, product API tests |
| Version `1.0.2` consistency | README, `/health`, OpenAPI, tag `v1.0.2` |
| Splice Sprint pilot offer (template) | `OFFER_SPLICE_BENCH_KIT_v1.md` |

### v1.1 interface preview (main branch — evidence-backed)

| Claim | Evidence |
|-------|----------|
| In-browser KiCad board preview (read-only) | splice-ui Design tab + vendored KiCanvas + `POST /v1/build-files/content` |
| circuit-json interchange into compile spine | `circuit_json_import.py`, Interface lab, `POST /v1/netlist-compile` |
| Canvas graph → same KiCad compile path | `POST /v1/compose-canvas`, Interface lab |
| Compile truth surfaced in UI | `POST /v1/build-files/design-quality`, `CompileTruthCard` |
| Artifact export / download from a build | `POST /v1/build-files/artifacts`, `download`, Design tab panel |
| circuit-json export from compile output | `POST /v1/build-files/circuit-json`, `build_compilation/circuit_json.json` |
| KiCad netlist ingest (SKiDL-class tools) | `kicad_netlist_text` on `/v1/netlist-compile`, fixture `esp32_servo_kicad` |
| atopile import via KiCad netlist paste | Interface lab paste + [`ATOPILE_IMPORT.md`](ATOPILE_IMPORT.md) |
| OSS integration map in product | `GET /v1/integrations/catalog`, Interface lab panel |
| Compile BOM surfaced in Design tab | `POST /v1/build-files/bom` |
| Fab artifact coverage vs KiBot reference | `POST /v1/build-files/fab-manifest` |
| Wiring topology diagram in package UI | Mermaid from `topology_operators` in Wiring tab |
| Opt-in FreeRouting autoroute | `POST /v1/build-files/autoroute` with `confirm=true`; never default-on |
| KiCad human edit → truth recheck | `scripts/kicad_mcp_dev_profile.sh`, `POST /v1/build-files/recheck` |

**v1.1 one-liner (interface preview):**

> Splice Agent exposes the existing KiCad compile spine through borrowed OSS layers — KiCanvas preview, circuit-json and canvas inputs, artifact export — while bench gates and `PROJECT_PACKAGE` remain the authority layer.

**Do not fold v1.1 interface claims into v1.0.2 release tag copy** until tagged and re-verified on a release branch.

**Preferred one-liner (v1.0.2 release):**

> Splice Agent v1.0.2 is a self-hosted hardware bring-up tool: donor intake → KiCad carrier with DRC truth → bench gates → `PROJECT_PACKAGE`. It passes the full internal bar on dev Linux and lab Windows/WSL2, with a sample package on the release.

---

## Forbidden or misleading claims

| Do not say | Why |
|------------|-----|
| “AI designs any board” | Bounded planners + operator gates |
| “Safer hardware automatically” | Operator authorizes power-on |
| “Production-ready routing” | Default copper is cosmetic; autoroute opt-in |
| “UL/CE/certified sign-off” | Not a cert body |
| “Flux replacement” | Different layer (greenfield ECAD) |
| “Quilter replacement” | Different layer (layout automation) |
| “Native Windows product” | WSL2 + bash for v1 |
| “GitHub Actions fully green” | Legacy `verify` job may fail; cite **Splice Agent v1 bar** |
| “Public git clone proven on all lab nodes” | One WSL pass used tarball fallback |
| “Customer-ready at scale / SaaS” | Self-hosted pilot SKU only |
| “Beats Blueprint on gallery UX” | Win on gates + truth, not presentation |

---

## Competitor mention rules

| Mention | Rule |
|---------|------|
| Flux | “Different job — greenfield vs bring-up” |
| Quilter | “Layout automation — optional integration” |
| JITX | “Enterprise code/sim — different buyer” |
| KiCad | “Substrate, not competitor” |
| Blueprint | “Similar package shape — we add compile + gate proof” |
| Manual checklist | “Actual competitor — we replace unstructured process” |

---

## Proof objects to attach

1. GitHub Release `v1.0.2` + sample zip  
2. `docs/GITHUB_START_HERE.md`  
3. `docs/COMPARISON_DEMO_CASE_robot_repair_cafe.md` (optional, internal reviewer)  
4. `docs/INSTALL_REPORT_desktop-fgedhgv-wsl_2026-07-07.md` (reproducibility)

**Do not attach:** `FLUX_TARGET.md`, raw `COMPETITIVE_PACKAGING_STRATEGY.md` to customers without editing.

---

## Reviewer ask (one conversation)

> Can you skim the release and sample zip and tell me whether this looks worth piloting on a real donor/repair/prototype case?

Not: “Are we better than Flux?”

---

*Outbound copy should pass this doc before send.*
