# Hardware-Splicer MCP / Agent SDK

Hardware-Splicer currently has two MCP-facing concepts. Do not confuse them.

## Recommended: canonical whole-backend MCP

Use **`hs-backend-mcp`** when the goal is to let an arbitrary MCP agent discover and exercise the same canonical backend used by the Hardware-Splicer product.

It derives its operation catalog from `hardware_splicer.product_api` OpenAPI, so durable project state, source ingestion/storage/parsing, AI orchestration/repair, source-blind cleanroom evaluation, capability reuse/economics, manufacturing/mechanical closure, status/revision/review, physical-evidence surfaces, and the older engine routes stay mechanically discoverable without maintaining a second list of wrappers.

Start here: [`MCP_CANONICAL_BACKEND.md`](MCP_CANONICAL_BACKEND.md)

```bash
python -m pip install -e '.[mcp]'
hs-backend-mcp
```

The canonical MCP gateway is authority-neutral: it re-enters the same FastAPI handlers and cannot bypass revision, evidence, deterministic-verification, physical-evidence, or human-authorization requirements.

## Compatibility: historical compile-engine MCP

The older **`hs-mcp`** / `hardware_splicer.mcp_server` surface exposes the compile/salvage engine directly through `hardware_splicer.sdk`. It remains useful for compatibility and focused engine workflows, but it must not be treated as a complete map of the current product backend.

### What the historical engine surface exposes

| Capability | Tool / API |
|------------|------------|
| **Agent handoff** | [`docs/AGENT_HANDOFF.md`](AGENT_HANDOFF.md) |
| Donor splice + carrier compile | `hs_splice_build` / `POST /v1/splice-and-build` |
| S3 golden loop (one-shot compatibility surface) | `hs_splice_golden_loop` / `POST /v1/splice-golden-loop` |
| S3 bench gate status | `hs_splice_bench_status` / `POST /v1/splice-bench/status` |
| S3 bench measurements | `hs_splice_bench_submit` / `POST /v1/splice-bench/submit` |
| Donor board → functional_salvage | `hs_donor_board_vision` / `POST /v1/donor-board-vision` |
| S3 bench capture template | `hs_splice_bench_capture_template` / `POST /v1/splice-bench/capture-template` |
| S3 bench capture packet | `hs_splice_bench_submit_capture` / `POST /v1/splice-bench/submit-capture` |
| Intake photo vision | `hs_vision_enrich_intake` / `POST /v1/vision/enrich-intake` |
| Vision inventory | `hs_vision_capabilities` / `GET /v1/vision/capabilities` |
| Fab package review | `hs_inspect_fab` |
| Junk-drawer parts → module IDs | `hs_resolve_parts` |
| Salvage plan | `hs_plan_salvage` |
| NL / modules / canvas → PCB | `hs_compose` |
| Full salvage bring-up + report | `hs_salvage_bringup` |
| Catalog KiCad DRC bar | `hs_verify_engine` |
| Runtime doctor | `hs_engine_doctor` |
| Vague goal clarifier | `hs_clarify_hardware_intent` / `POST /v1/intent/clarify` |
| Circuit synthesis plan | `hs_plan_circuit_synthesis` / `POST /v1/circuit-synthesis/plan` |
| Circuit synthesis compile | `hs_synthesize_circuit` / `POST /v1/circuit-synthesis/compile` |
| Project package refresh | `hs_render_project_package` / `POST /v1/project-package/render` |

The historical tool list predates the canonical project/product API and therefore is not used as the coverage oracle for whole-backend MCP testing.

### Run historical engine MCP

```bash
export PYTHONPATH=src
export HARDWARE_SPLICER_AUTOROUTE=0
python -m hardware_splicer.mcp_server
```

Example local client block:

```json
{
  "mcpServers": {
    "hardware-splicer-engine": {
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

## Python SDK (no MCP)

The SDK remains appropriate when the caller is Python-native and intentionally wants direct engine functions instead of the canonical product API.

```python
from hardware_splicer.sdk import compose_design, resolve_inventory_parts, sdk_info

print(sdk_info())
resolved = resolve_inventory_parts([
    {"name": "ESP32 devkit", "type": "microcontroller", "module_id": "esp32-devkit"},
])
result = compose_design(
    phrase="wifi temperature logger",
    constraints={"strategy_mode": "constrained", "compose_from_inventory": True},
    salvage_mode=True,
)
```

## HTTP API

The canonical HTTP product backend remains available independently of MCP:

```bash
hs-serve --host 127.0.0.1 --port 8787
```

For a complete agent-facing backend test, prefer `hs-backend-mcp` because its discovery contract is generated from that canonical API rather than from a manually curated engine tool list.
