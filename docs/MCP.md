# Hardware-Splicer MCP / Agent SDK

Expose the **compile engine** (not the legacy Circuit-AI generative stubs) to any MCP-capable model: Cursor, Claude Desktop, custom agents.

## What agents get

| Capability | Tool / API |
|------------|------------|
| **Agent handoff (start here)** | [`docs/AGENT_HANDOFF.md`](AGENT_HANDOFF.md) |
| Donor splice + carrier compile | `hs_splice_build` / `POST /v1/splice-and-build` |
| S3 golden loop (one-shot) | `hs_splice_golden_loop` / `POST /v1/splice-golden-loop` |
| S3 bench gate status | `hs_splice_bench_status` / `POST /v1/splice-bench/status` |
| S3 bench measurements | `hs_splice_bench_submit` / `POST /v1/splice-bench/submit` |
| Donor board → functional_salvage | `hs_donor_board_vision` / `POST /v1/donor-board-vision` |
| S3 bench capture template | `hs_splice_bench_capture_template` / `POST /v1/splice-bench/capture-template` |
| S3 bench capture packet | `hs_splice_bench_submit_capture` / `POST /v1/splice-bench/submit-capture` |
| Intake photo vision | `hs_vision_enrich_intake` / `POST /v1/vision/enrich-intake` |
| Vision inventory | `hs_vision_capabilities` / `GET /v1/vision/capabilities` |
| Fab package review | `hs_inspect_fab` |
| Junk-drawer parts → module IDs | `hs_resolve_parts` |
| Salvage plan (fast, no KiCad) | `hs_plan_salvage` |
| NL / modules / canvas → PCB | `hs_compose` |
| Full salvage bring-up + report | `hs_salvage_bringup` |
| Catalog KiCad DRC bar | `hs_verify_engine` |
| Runtime doctor | `hs_engine_doctor` |
| Vague goal clarifier | `hs_clarify_hardware_intent` / `POST /v1/intent/clarify` |
| Circuit synthesis plan | `hs_plan_circuit_synthesis` / `POST /v1/circuit-synthesis/plan` |
| Circuit synthesis compile | `hs_synthesize_circuit` / `POST /v1/circuit-synthesis/compile` |
| Project package refresh | `hs_render_project_package` / `POST /v1/project-package/render` |

**Truth model:** KiCad ERC/DRC is external compile truth. Default copper is **cosmetic preview** (`copper_tier: cosmetic_preview`). FreeRouting is off unless `HARDWARE_SPLICER_AUTOROUTE=1`.

**vs Flux (honest positioning):**

- **Stronger:** headless salvage/inventory path, deterministic compile, KiCad-gated quality, same engine for scratch + salvage, agent-native HTTP/MCP/SDK
- **Weaker today:** interactive editor UX, autorouted production copper, parts marketplace polish

Call `hs_sdk_info` first so the model reads capability boundaries.

## Install

```bash
make setup
pip install -r requirements-mcp.txt
make doctor
```

## MCP (stdio)

From repo root:

```bash
export PYTHONPATH=src
export HARDWARE_SPLICER_AUTOROUTE=0
python -m hardware_splicer.mcp_server
```

### Cursor

Merge into `.cursor/mcp.json` (set `HARDWARE_SPLICER_ROOT` to this repo):

```json
{
  "mcpServers": {
    "hardware-splicer": {
      "command": "python3",
      "args": ["-m", "hardware_splicer.mcp_server"],
      "env": {
        "PYTHONPATH": "/path/to/Hardware-Splicer/src",
        "HARDWARE_SPLICER_AUTOROUTE": "0",
        "HARDWARE_SPLICER_JLC_ENRICH": "0",
        "HARDWARE_SPLICER_DRC_FIX_LOOP": "1"
      }
    }
  }
}
```

Template: [`mcp/hardware-splicer.mcp.json`](../mcp/hardware-splicer.mcp.json)

### Claude Desktop

Same stdio block under `mcpServers` in `claude_desktop_config.json`.

## Python SDK (no MCP)

```python
from hardware_splicer.sdk import (
    compose_design,
    plan_salvage,
    resolve_inventory_parts,
    salvage_bringup,
    sdk_info,
    splice_build,
    splice_bench_status,
    splice_bench_submit,
    inspect_fab_build_dir,
)

print(sdk_info())

resolved = resolve_inventory_parts([
    {"name": "ESP32 devkit", "type": "microcontroller", "module_id": "esp32-devkit"},
    {"name": "DHT22", "type": "sensor", "module_id": "dht22"},
    {"name": "USB 5V wall wart", "type": "power_source", "module_id": "usb-power-5v", "voltage_v": 5},
])

result = compose_design(
    phrase="wifi temperature logger",
    constraints={"strategy_mode": "constrained", "compose_from_inventory": True},
    salvage_mode=True,
)
```

## HTTP API (alternative)

For remote agents or multi-tenant hosts:

```bash
python scripts/hardware_splicer.py serve --host 127.0.0.1 --port 8787
```

Key routes: `POST /v1/splice-and-build`, `POST /v1/splice-bench/status`, `POST /v1/splice-bench/submit`, `POST /v1/compose`, `POST /v1/engine-verify`.

Full agent flow: [`docs/AGENT_HANDOFF.md`](AGENT_HANDOFF.md).

## Suggested agent workflow

1. `hs_sdk_info` or read `docs/AGENT_HANDOFF.md`
2. `hs_engine_doctor` — abort early if KiCad/node missing
3. **Splice path:** `hs_splice_build` → `hs_splice_bench_status` → `hs_splice_bench_submit` → `hs_inspect_fab`
4. **Scratch/salvage compose path:** `hs_resolve_parts` or `hs_plan_salvage` → `hs_compose` or `hs_salvage_bringup`
5. Read `design_quality_gate` / `bench_session.power_on_authorized` — **do not claim fab-ready or power-on-safe without both**

## Environment

| Variable | Default | Meaning |
|----------|---------|---------|
| `HARDWARE_SPLICER_AUTOROUTE` | `0` | No Java FreeRouting |
| `HARDWARE_SPLICER_JLC_ENRICH` | `0` in agents | Skip slow BOM enrich |
| `HARDWARE_SPLICER_DRC_FIX_LOOP` | `1` | Geometry nudge retries |
| `HARDWARE_SPLICER_OUTPUT_ROOT` | `/tmp/hardware_splicer_api` | HTTP API output sandbox |
