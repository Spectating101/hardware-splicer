# Design Studio + DRC agent loop (v1.1.0-alpha.2 candidate)

**Audience:** AI agents (MCP/HTTP/SDK), human operators using Splice Agent UI, and reviewers asking “what does this product *do*?”

**Commit anchor:** `4775e1c` on `main` — pin-level React Flow compose, module catalog API, in-studio DRC fix feedback.

---

## Product moment (one sentence)

> Sketch or describe a hardware graph → KiCad compile → **visible DRC truth** → bounded geometry fixups → `PROJECT_PACKAGE` → bench gates.

Agents and humans use the **same spine**. The browser Design Studio is not a separate product — it is a legible front-end on `compose_dispatch` + `drc_fix_loop`.

---

## Architecture

```text
                    ┌─────────────────────────────────────┐
                    │  Agent (MCP / HTTP / Python SDK)    │
                    │  or Human (Design Studio UI)        │
                    └─────────────────┬───────────────────┘
                                      │
              canvas_nodes / phrase / module_ids / drc_fixup
                                      ▼
                         POST /v1/compose  or  hs_compose
                                      │
                                      ▼
                         compose_dispatch (canvas | scratch | llm_first)
                                      │
                                      ▼
                    compile_with_drc_fixup_loop (KiCad CLI DRC)
                                      │
                    ┌─────────────────┴───────────────────┐
                    │ design_quality.drc_fix_loop           │
                    │ design_quality_gate                   │
                    │ KICAD_DRC.json / DESIGN_QUALITY.json  │
                    └─────────────────┬───────────────────┘
                                      │
              finalize → PROJECT_PACKAGE + bench_session
                                      ▼
                    gates · BOM · KiCanvas preview · zip handoff
```

---

## Agent surfaces (primary)

### MCP tools

| Tool | Purpose |
|------|---------|
| `hs_modules_catalog` | Module library for canvas compose (27+ KiCad-footprinted modules) |
| `hs_compose` | NL phrase, `module_ids`, or `canvas_nodes`/`canvas_wires` → KiCad + DRC loop |
| `hs_render_project_package` | Refresh `PROJECT_PACKAGE` after compose |
| `hs_splice_bench_status` / `hs_splice_bench_submit` | Bench gates after compile |

**`hs_compose` agent-relevant fields:**

```json
{
  "phrase": "ESP32 soil logger with DHT22",
  "canvas_nodes": [
    {"id": "m1", "moduleId": "esp32-devkit"},
    {"id": "m2", "moduleId": "dht22"}
  ],
  "canvas_wires": [],
  "allow_llm_first": true,
  "drc_fixup": {
    "edge_pad_extra_mm": 0.35,
    "module_gap_extra_mm": 4.0,
    "via_clearance_mm": 0.27
  },
  "export_gerber": false
}
```

Read `design_quality.drc_fix_loop.attempts` after each call. If `kicad_drc_errors > 0`, bump `drc_fixup` (same deltas as UI: +0.35 edge pad, +4 module gap, +0.06 via clearance) and re-call `hs_compose`.

### HTTP (same contract)

| Route | Purpose |
|-------|---------|
| `GET /v1/modules/catalog` | Module library |
| `POST /v1/compose` | Sync compose + DRC loop (Design Studio uses this) |
| `POST /v1/jobs/compose` | Async compose job → `PROJECT_PACKAGE` |
| `POST /v1/build-files/design-quality` | DRC summary + violations for `build_dir` |
| `POST /v1/project-package/render` | Package hydration |

### Python SDK

```python
from hardware_splicer.sdk import compose_design, finalize_compose_job_result
from hardware_splicer.pcb.module_registry import list_canvas_modules

modules = list_canvas_modules()
result = compose_design(
    phrase="agent demo",
    canvas_nodes=[
        {"id": "m1", "moduleId": "esp32-devkit"},
        {"id": "m2", "moduleId": "dht22"},
    ],
    allow_llm_first=False,
    export_gerber=False,
)
loop = (result.get("design_quality") or {}).get("drc_fix_loop") or {}
errors = (result.get("design_quality") or {}).get("kicad_drc_errors")

if errors:
    result = compose_design(
        canvas_nodes=[...],
        drc_fixup={"edge_pad_extra_mm": 0.35, "module_gap_extra_mm": 4.0},
        allow_llm_first=False,
        export_gerber=False,
    )

package = finalize_compose_job_result(result, goal="agent demo", project_name="agent_demo")
```

---

## Human surface (Design Studio)

Splice Agent → **Design studio** — same flow as agents, with:

- React Flow pin-level canvas
- Agent loop panel (compose → compile → DRC → fix → done)
- **Auto-fix & recompile** (bounded `drc_fixup` bumps)
- **Open full project** → `PROJECT_PACKAGE` shell

---

## Honest pass bars

| Signal | Meaning |
|--------|---------|
| `kicad_drc_errors == 0` | KiCad DRC clean (errors) |
| `drc_fix_loop.resolved` | Engine auto-fix loop cleared errors |
| `copper_tier == cosmetic_preview` | **Not** production-routed copper — fab still “review required” |
| `design_quality_gate.fabrication_ready` | Stricter gate — read before claiming fab-ready |
| `bench_session.power_on_authorized` | Operator closed measurement gates |

**Do not tell users or agents:** “order from JLC now” when copper is cosmetic preview.

---

## Agent loop (recommended)

```text
1. hs_modules_catalog          → pick moduleIds
2. hs_compose (canvas + phrase) → read design_quality
3. If kicad_drc_errors > 0:
     bump drc_fixup → hs_compose again (max 2–3 manual retries)
4. hs_render_project_package
5. hs_splice_bench_status      → report open gates
6. hs_splice_bench_submit      → when measurements exist
```

For salvage/donor workflows, branch to `hs_splice_build` / `hs_salvage_bringup` — Design Studio is the **greenfield / canvas** path.

---

## Verification

```bash
make test-splice-product-v1
pytest tests/test_design_studio_agent.py -q
# With API running:
make verify-ui-interface-smoke
```

---

## Related docs

- [`AGENT_HANDOFF.md`](AGENT_HANDOFF.md) — full MCP flow
- [`DEMO_DESIGN_STUDIO_DRC_LOOP.md`](DEMO_DESIGN_STUDIO_DRC_LOOP.md) — 3–5 min demo script (agent + UI)
- [`CLAIMS_BOUNDARY.md`](CLAIMS_BOUNDARY.md) — what not to claim publicly

---

*Internal + agent-facing. Last updated: 2026-07-08 · post `4775e1c`*
