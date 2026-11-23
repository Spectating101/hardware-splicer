# Comparison demo case — `robot_repair_cafe` (v1.0.2)

**Purpose:** Artifact-to-artifact comparison using the **real** release sample — not slogans.

**Proof object:** [`releases/sample-splice-sprint-robot-repair-cafe.zip`](../releases/sample-splice-sprint-robot-repair-cafe.zip) (GitHub Release `v1.0.2`)

**Case:** Repair-café S3 golden — salvaged robot drive donor → carrier compile → bench closure → `POWER_ON_AUTHORIZED`

---

## What Hardware-Splicer actually shipped (verified)

From the release zip (`PROJECT_PACKAGE.json`):

| Field | Value |
|-------|-------|
| `schema_version` | `hardware_splicer.project_package.v1` |
| `source` | `splice_build` |
| `gates.verdict` | `POWER_ON_AUTHORIZED` |
| `gates.power_on_authorized` | `true` |
| `gates.bench_readiness` | `bench_complete` |

**Bundled artifacts (package + zip root):**

| Artifact | Role |
|----------|------|
| `PROJECT_PACKAGE.json` | Machine-readable BOM, wiring, instructions, gates |
| `PROJECT_PAGE.md` | Human summary |
| `SPLICE_PLAN.json` | Donor/splice plan |
| `SPLICE_BENCH_SESSION.json` | Measurement session |
| `BRINGUP_CARD.md` / `.json` | Operator bring-up |
| `WIRING_GUIDE.md` | Wiring narrative |
| `SALVAGE_BOM.*` | Parts from donor context |
| `build_compilation/` | KiCad PCB, DRC, ERC, BOM, fab outputs |
| `COMPILE_CASEFILE` (in package refs) | Failure-debug path when compile fails |

**Internal bar that produced this:** `make verify-product-internal` (dev-linux + lab WSL2).

---

## Same job — what each category likely produces

**Scenario:** “I have a donor motor board from a junk robot. I want a safe carrier + checklist before I power a new build.”

| Category | Typical output | Bench gates? | Donor/splice? | Power-on boundary? |
|----------|----------------|--------------|---------------|-------------------|
| **Flux** | New browser project, schematic, layout, BOM, Gerbers | No productized bench gate JSON | No — greenfield | No — operator owns safety |
| **EasyEDA / JLC** | Schematic, PCB, BOM tied to fab order | No | No | No |
| **Quilter** | Routed PCB candidate(s) from constraints | No | No — expects clean schematic | No |
| **JITX** | Python design code, simulation-validated layout | Enterprise QA workflows | No salvage path | Process-dependent |
| **KiCad manual** | `.kicad_pcb`, notes in README or wiki | Ad hoc | Manual | Tribal knowledge |
| **Notion / PDF checklist** | Human checklist rows | Manual only | Manual | Paper sign-off |
| **Blueprint.am** | Pretty project page, BOM/wiring tabs | Weak vs our gate semantics | Inspiration-first | Unclear machine verdict |
| **HS Splice v1.0.2** | **`PROJECT_PACKAGE` zip above** | **Yes — `SPLICE_BENCH_SESSION` + gate verdict** | **Yes — splice plan + salvage BOM** | **Yes — explicit `power_on_authorized`** |

---

## Artifact diff (the comparison that matters)

| Proof type | Flux-class | Quilter | KiCad/manual | HS sample zip |
|------------|------------|---------|--------------|---------------|
| Fab-ready Gerbers | ✅ | ✅ | ✅ if skilled | ✅ in `build_compilation/` |
| Live collaboration | ✅ | ❌ | ❌ | ❌ (not the job) |
| Autorouted dense PCB | partial | ✅ | manual | ❌ cosmetic carrier default |
| Donor vision / salvage report | ❌ | ❌ | ❌ | ✅ `DONOR_BOARD_VISION_REPORT.json` |
| Splice plan with extractability | ❌ | ❌ | ❌ | ✅ `SPLICE_PLAN.json` |
| Bench session JSON | ❌ | ❌ | ❌ | ✅ `SPLICE_BENCH_SESSION.json` |
| Machine gate verdict | ❌ | ❌ | ❌ | ✅ `gates.verdict` |
| Compile failure casefile | partial DRC | partial | ad hoc | ✅ `compile_casefile` in package |
| Self-hosted agent/API | ❌ SaaS | on-prem option | N/A | ✅ HTTP + MCP |
| One-command internal verify | ❌ | ❌ | ❌ | ✅ `make verify-product-internal` |

---

## Sentences to use internally

> **Flux** gives you a new board design. **Hardware-Splicer** gives you a **defensible bring-up package** around hardware you already have.

> **Quilter** shrinks layout time. **Hardware-Splicer** shrinks **“can I energize this?”** ambiguity.

> The sample zip is the product. If a competitor category cannot produce **`gates.verdict` + bench session + splice plan** in one zip, it is not the same category.

---

## What this case does *not* prove

- Native Windows install (WSL2 path only)
- Production autoroute quality
- Certification / UL / CE
- That every intake succeeds (failures should emit casefiles)

---

*Attach this doc + sample zip when asking one trusted reviewer: “Is this worth a Splice Sprint pilot?”*
