# Agent quickstart — 15 minutes to DRC truth

**Audience:** MCP clients, HTTP callers, Cursor/Claude agents.  
**Prereq:** Python 3.11+, KiCad CLI on PATH, repo cloned.

**Full runbook:** [`AGENT_HANDOFF.md`](AGENT_HANDOFF.md) · **Scale plan:** [`PRODUCT_SCALE_PLAN.md`](PRODUCT_SCALE_PLAN.md)

---

## 1. Start the API

```bash
cd Hardware-Splicer
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Optional: Qwen for AI-first compose (create .env.local — do not commit)
# QWEN_API_KEY=...
set -a && [ -f .env.local ] && source .env.local && set +a
export HARDWARE_SPLICER_OFFLINE_COMPOSE=0
export HARDWARE_SPLICER_QWEN_COMPOSE=1

PYTHONPATH=src python3 scripts/hardware_splicer.py serve --host 127.0.0.1 --port 8787
```

Verify:

```bash
curl -s http://127.0.0.1:8787/health | jq '{ok, version, qwen_configured, offline_compose}'
```

---

## 2. Three HTTP curls (agent spine)

### Curl 1 — Module catalog

```bash
curl -s http://127.0.0.1:8787/v1/modules/catalog \
  | jq '{count, sample: .modules[0] | {id, label, pins: (.pins | length)}}'
```

### Curl 2 — Canvas agent loop (deterministic, no LLM)

```bash
curl -s -X POST http://127.0.0.1:8787/v1/compose/agent-loop \
  -H 'Content-Type: application/json' \
  -d '{
    "phrase": "ESP32 DHT22 logger quickstart",
    "canvas_nodes": [
      {"id": "m1", "moduleId": "esp32-devkit"},
      {"id": "m2", "moduleId": "dht22"}
    ],
    "allow_llm_first": false,
    "max_manual_retries": 2,
    "finalize_package": true,
    "project_name": "agent_quickstart_canvas"
  }' | jq '{
    resolved: .agent_loop.resolved,
    drc_errors: .agent_loop.final_kicad_drc_errors,
    copper: .agent_loop.copper_tier,
    package: (.project_package != null),
    out_dir
  }'
```

### Curl 3 — AI phrase agent loop (Qwen when configured)

```bash
curl -s -X POST http://127.0.0.1:8787/v1/compose/agent-loop \
  -H 'Content-Type: application/json' \
  -d '{
    "phrase": "ESP32 soil moisture logger with OLED display",
    "allow_llm_first": true,
    "max_manual_retries": 2,
    "finalize_package": true,
    "project_name": "agent_quickstart_ai"
  }' | jq '{
    mode,
    compose_mode,
    module_ids,
    resolved: .agent_loop.resolved,
    drc_errors: .agent_loop.final_kicad_drc_errors,
    qwen_tokens: .qwen_usage.total_tokens
  }'
```

### Async job — agent loop (for long compiles / agents that poll)

```bash
JOB=$(curl -s -X POST http://127.0.0.1:8787/v1/jobs/compose-agent-loop \
  -H 'Content-Type: application/json' \
  -d '{
    "phrase": "ESP32 DHT22 async job demo",
    "canvas_nodes": [
      {"id": "m1", "moduleId": "esp32-devkit"},
      {"id": "m2", "moduleId": "dht22"}
    ],
    "allow_llm_first": false,
    "max_manual_retries": 2,
    "finalize_package": true,
    "project_name": "agent_job_demo"
  }')
echo "$JOB" | jq '{job_id, status, links}'
JOB_ID=$(echo "$JOB" | jq -r .job_id)
until [[ $(curl -s http://127.0.0.1:8787/v1/jobs/$JOB_ID | jq -r .status) =~ ^(succeeded|failed)$ ]]; do sleep 1; done
curl -s http://127.0.0.1:8787/v1/jobs/$JOB_ID/result | jq '{
  status,
  resolved: .result.agent_loop.resolved,
  drc_errors: .result.agent_loop.final_kicad_drc_errors,
  package: (.result.project_package != null)
}'
```

Repeat on alien WSL: [`scripts/agent_quickstart_verify.sh`](../scripts/agent_quickstart_verify.sh) — see [`INSTALL_REPORT_desktop-fgedhgv-wsl_2026-07-09.md`](INSTALL_REPORT_desktop-fgedhgv-wsl_2026-07-09.md).

Start MCP (separate terminal):

```bash
PYTHONPATH=src python3 -m hardware_splicer.mcp_server
```

Or configure in Cursor/Claude per [`MCP.md`](MCP.md).

### MCP 1 — `hs_modules_catalog`

```json
{}
```

Expect `count` ≈ 27 and each module has `id`, `pins`.

### MCP 2 — `hs_compose_drc_agent` (canvas)

```json
{
  "phrase": "MCP canvas quickstart",
  "canvas_nodes": [
    {"id": "m1", "moduleId": "esp32-devkit"},
    {"id": "m2", "moduleId": "dht22"}
  ],
  "allow_llm_first": false,
  "max_manual_retries": 2,
  "finalize_package": true,
  "project_name": "mcp_quickstart"
}
```

### MCP 3 — `hs_design_quality`

Use `out_dir` from compose result:

```json
{
  "build_dir": "/tmp/hardware_splicer_api/.../build"
}
```

**Path policy:** If `build_dir` is outside the API output root, set `HARDWARE_SPLICER_ALLOW_ARBITRARY_OUT_DIR=1` for local dev. See [`AGENT_BUILD_DIR_POLICY.md`](AGENT_BUILD_DIR_POLICY.md).

---

## 4. Python SDK (optional)

```python
from hardware_splicer.sdk import compose_design_agent_loop

result = compose_design_agent_loop(
    phrase="SDK quickstart",
    canvas_nodes=[
        {"id": "m1", "moduleId": "esp32-devkit"},
        {"id": "m2", "moduleId": "dht22"},
    ],
    allow_llm_first=False,
    max_manual_retries=2,
    finalize_package=True,
    project_name="sdk_quickstart",
)
print(result["agent_loop"]["resolved"], result.get("project_package") is not None)
```

---

## 5. Recommended agent flow

```text
hs_modules_catalog
  → hs_compose_drc_agent (finalize_package: true)
  → hs_design_quality (if build_dir path allowed)
  → hs_splice_bench_status
  → hs_splice_bench_submit
```

**Do not claim fab-ready** from DRC alone. Check `copper_tier`, `design_quality_gate`, and `bench_session.power_on_authorized`.

---

## 6. Troubleshooting

| Symptom | Fix |
|---------|-----|
| `404` on `/v1/modules/catalog` or `/v1/compose/agent-loop` | Restart API with latest `main` |
| `module_picker_fallback` with Qwen configured | Check `qwen_configured` in `/health`; `HARDWARE_SPLICER_QWEN_COMPOSE=1` |
| `hs_design_quality` ValueError on build_dir | Set `HARDWARE_SPLICER_ALLOW_ARBITRARY_OUT_DIR=1` or use path under output root |
| DRC 0 but `cosmetic_preview` | Expected — review before fab; not a bug |

---

Repeat on alien WSL: [`scripts/agent_quickstart_verify.sh`](../scripts/agent_quickstart_verify.sh) — see [`INSTALL_REPORT_desktop-fgedhgv-wsl_2026-07-09.md`](INSTALL_REPORT_desktop-fgedhgv-wsl_2026-07-09.md).

- Browser legibility: Design Studio → **AI phrase compose** or canvas compile  
- Demo script: [`DEMO_DESIGN_STUDIO_DRC_LOOP.md`](DEMO_DESIGN_STUDIO_DRC_LOOP.md)  
- Internal bar: `make verify-product-internal`
