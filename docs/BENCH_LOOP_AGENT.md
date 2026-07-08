# Bench loop — agent path (Phase 2 kickoff)

**Purpose:** Close the loop from compose → **bench gates** → `power_on_authorized` on the **same spine** as `hs_compose_drc_agent`.

**Related:** [`AGENT_HANDOFF.md`](AGENT_HANDOFF.md) · [`SPLICE_BEST_PRACTICES.md`](SPLICE_BEST_PRACTICES.md)

---

## Spine

```text
hs_compose_drc_agent (finalize_package: true)
  → SPLICE_BENCH_SESSION.json + BENCH_CAPTURE_TEMPLATE.json
  → fill capture (instrument or camera-assisted packet)
  → hs_splice_bench_submit_capture
  → bench_session.power_on_authorized
```

**One-shot (CI / demo):** `hs_compose_bench_loop` with `simulate_bench: true`.

**Production:** `simulate_bench: false` + real `bench_topology_capture.v1` in `capture`.

---

## HTTP

### Compose + simulated bench (salvage example)

```bash
curl -s -X POST http://127.0.0.1:8787/v1/compose/bench-loop \
  -H 'Content-Type: application/json' \
  -d "$(PYTHONPATH=src python3 scripts/salvage_agent_loop_payload.py | python3 -c 'import json,sys; p=json.load(sys.stdin); p["simulate_bench"]=True; print(json.dumps(p))')" \
  | jq '{
    drc: .agent_loop.final_kicad_drc_errors,
    power_on: .bench_session.power_on_authorized,
    bench_loop_passed: .bench_loop.passed
  }'
```

### Incremental (compose first, bench second)

1. `POST /v1/compose/agent-loop` with `finalize_package: true`
2. `POST /v1/splice-bench/capture-template` with `build_dir`
3. Fill `BENCH_CAPTURE_TEMPLATE.json` or POST capture packet
4. `POST /v1/splice-bench/submit-capture`

---

## MCP

| Tool | Role |
|------|------|
| `hs_compose_bench_loop` | Compose + package + optional simulated closure |
| `hs_splice_bench_capture_template` | Refresh template from open gates |
| `hs_splice_bench_submit_capture` | Submit `bench_topology_capture.v1` |
| `hs_splice_bench_status` | Read gate verdict |

---

## Artifacts

| File | Meaning |
|------|---------|
| `SPLICE_BENCH_SESSION.json` | Gate open/closed state |
| `BENCH_CAPTURE_TEMPLATE.json` | Operator fill sheet from open gates |
| `BENCH_LOOP_REPORT.json` | Compose+bench loop summary |

---

## Claims boundary

- **DRC 0 errors** ≠ power-on safe
- **`simulate_bench: true`** is for CI/demo only — do not cite as field evidence
- Use `power_on_authorized` from **real** capture for bring-up claims
