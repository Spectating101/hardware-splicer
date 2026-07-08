# Demo script — Design Studio DRC agent loop (3–5 minutes)

**Goal:** Show a reviewer (human or AI agent operator) the **legible product moment** — compose → KiCad truth → visible fix loop → package → gates.

**Prereqs:** API on `:8787`, UI built or `npm run dev` on `:5173`/`5178`.

```bash
PYTHONPATH=src HARDWARE_SPLICER_OFFLINE_COMPOSE=1 \
  python3 scripts/hardware_splicer.py serve --host 127.0.0.1 --port 8787
```

---

## Track A — Agent / MCP (no browser, ~2 min)

**Narration:** “Agents don’t need our UI. Same spine as Design Studio.”

### 1. Module catalog

```bash
curl -s http://127.0.0.1:8787/v1/modules/catalog | jq '{count, first: .modules[0].id}'
```

Or MCP: `hs_modules_catalog`

### 2. Compose canvas

```bash
curl -s -X POST http://127.0.0.1:8787/v1/compose \
  -H 'Content-Type: application/json' \
  -d '{
    "phrase": "ESP32 temperature humidity logger demo",
    "canvas_nodes": [
      {"id":"m1","moduleId":"esp32-devkit"},
      {"id":"m2","moduleId":"dht22"}
    ],
    "export_gerber": false,
    "allow_llm_first": false
  }' | jq '{
    mode,
    out_dir,
    drc_errors: .design_quality.kicad_drc_errors,
    drc_warnings: .design_quality.kicad_drc_warnings,
    fix_attempts: (.design_quality.drc_fix_loop.attempts | length),
    fix_resolved: .design_quality.drc_fix_loop.resolved,
    copper: .design_quality.copper_tier
  }'
```

**Point out:** `drc_fix_loop.attempts` — bounded geometry retries, not black-box “AI fixed it.”

### 3. Manual retry (if errors remain)

```bash
# Add drc_fixup from last attempt or bump manually:
curl -s -X POST http://127.0.0.1:8787/v1/compose \
  -H 'Content-Type: application/json' \
  -d '{
    "phrase": "ESP32 logger retry",
    "canvas_nodes": [
      {"id":"m1","moduleId":"esp32-devkit"},
      {"id":"m2","moduleId":"dht22"}
    ],
    "drc_fixup": {"edge_pad_extra_mm": 0.35, "module_gap_extra_mm": 4.0},
    "export_gerber": false,
    "allow_llm_first": false
  }' | jq '.design_quality.kicad_drc_errors'
```

### 4. Package handoff

```bash
OUT_DIR="<out_dir from step 2>"
curl -s -X POST http://127.0.0.1:8787/v1/project-package/render \
  -H 'Content-Type: application/json' \
  -d "{\"build_dir\": \"$OUT_DIR\", \"source\": \"compose\"}" | jq '.package.info.project_name'
```

**Close:** “Agent path ends with the same `PROJECT_PACKAGE` and bench gates as splice builds.”

---

## Track B — Design Studio UI (~3 min)

**Narration:** “Same spine, but a hardware person can *see* the loop.”

1. Open app → **Design studio** (sidebar or home button).
2. Click **ESP32 DevKit** + **DHT22** in module library (or drag onto canvas).
3. Goal field: `ESP32 temperature humidity logger demo`
4. **Compile to KiCad** — watch **Agent loop** panel:
   - Compose graph → KiCad compile → DRC check → fix loop
5. Note **0 DRC errors** vs **cosmetic preview** copper in full project (honest fab posture).
6. **Open full project** → Design verify tab:
   - KiCanvas preview
   - Compile BOM (2 lines)
   - Bench gates

**If DRC errors:** click **Auto-fix & recompile** — show transparent `drc_fixup` hint text.

---

## What to say (30 seconds)

> Hardware-Splicer is an **agentic KiCad-truth workbench**. You compose a module graph — via MCP or the Design Studio — it compiles to real KiCad, runs DRC with a **visible fix loop**, and hands off an auditable project package with bench gates before power-on. We’re not claiming to be Flux’s full editor; we’re giving agents and labs **transparent compile truth plus the last mile Flux doesn’t ship**.

---

## What not to say

- “Flux replacement”
- “Fab-ready” when copper tier is `cosmetic_preview`
- “AI designs any board”

See [`CLAIMS_BOUNDARY.md`](CLAIMS_BOUNDARY.md).

---

## Automated smoke

```bash
pytest tests/test_design_studio_agent.py -q
VERIFY_UI_BASE_URL=http://127.0.0.1:8787 make verify-ui-interface-smoke
```

---

*Demo script · v1.1.0-alpha.2 candidate · 2026-07-08*
