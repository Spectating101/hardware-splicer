# Agent build_dir policy — MCP and HTTP

**Audience:** Agents calling `hs_design_quality`, `hs_render_project_package`, or any tool that reads `build_dir` / `out_dir`.

**Related:** [`BUILD_FILES_API_SECURITY.md`](BUILD_FILES_API_SECURITY.md) · [`AGENT_QUICKSTART.md`](AGENT_QUICKSTART.md)

---

## 1. Why this exists

Compose writes KiCad artifacts to disk. Follow-up tools (`hs_design_quality`, BOM fetch, package render) must read those paths **without exposing arbitrary filesystem access** on shared hosts.

---

## 2. Default (production / pilot)

| Env | Default | Meaning |
|-----|---------|---------|
| `HARDWARE_SPLICER_OUTPUT_ROOT` | `/tmp/hardware_splicer_api` | API-owned compose output |
| `HARDWARE_SPLICER_ALLOW_ARBITRARY_OUT_DIR` | unset / `0` | **Only** paths under output root are readable |

**Agent rule:** After `hs_compose_drc_agent`, pass the returned `out_dir` (or `build_dir`) directly to `hs_design_quality`. Do not invent paths.

---

## 3. Local development

When MCP runs **in-process** (Python `call_tool`) or compose used a custom `out_dir` outside the output root:

```bash
export HARDWARE_SPLICER_ALLOW_ARBITRARY_OUT_DIR=1
```

Same for HTTP API if the UI or tests point at ad-hoc directories.

**Never** set this on internet-facing multi-tenant hosts.

---

## 4. Symptom → fix

| Error | Cause | Fix |
|-------|-------|-----|
| `build_dir must be under HARDWARE_SPLICER_OUTPUT_ROOT` | Path outside allowed root | Use compose `out_dir`; or set `ALLOW_ARBITRARY_OUT_DIR=1` locally |
| `build_dir does not exist` | Stale path or cleaned temp | Re-run compose; copy `out_dir` from latest result |
| HTTP 403 on `/v1/build-files/*` | Same root policy | Align `build_dir` with compose output |

---

## 5. MCP vs HTTP

| Surface | Typical `out_dir` | Policy |
|---------|-------------------|--------|
| `POST /v1/compose/agent-loop` | Under `OUTPUT_ROOT` when `out_dir` omitted | ✅ `hs_design_quality` works |
| MCP `hs_compose_drc_agent` (stdio) | May use SDK default outside root | Set `ALLOW_ARBITRARY_OUT_DIR=1` for step 3 |
| Tests / CI | `tmp_path` | `conftest.py` sets `ALLOW_ARBITRARY_OUT_DIR=1` |

---

## 6. Agent sequence (safe)

```text
1. result = hs_compose_drc_agent({..., finalize_package: true})
2. build_dir = result.out_dir
3. hs_design_quality({ build_dir })   # only if path policy allows
4. hs_splice_bench_status({ build_dir })  # same policy
```

If step 3 fails on path policy, read DRC from step 1 payload: `result.design_quality` and `result.agent_loop` already contain truth.

---

## 7. Changelog

| Date | Change |
|------|--------|
| 2026-07-08 | Initial agent-focused build_dir policy (alpha.5) |
