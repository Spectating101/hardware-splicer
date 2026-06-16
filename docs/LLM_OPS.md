# LLM operations — wrap-up (2026-06)

Reference for text + vision LLM usage in Hardware-Splicer: quota, caching, providers, benchmarks, and what is / is not solved.

Cross-project model picking guide: [`../../../docs/DASHSCOPE_MODEL_GUIDE.md`](../../../docs/DASHSCOPE_MODEL_GUIDE.md) (llm_automation repo).

---

## Status at cutoff

| Area | State |
|------|--------|
| Salvage + compose (golden harness) | **7/7** build picks, **100%** compose DRC (offline and online after fixes) |
| Offline heuristics | Hybrid regex compose + keyword build-pick reconciliation |
| Per-stage Qwen policy | `qwen_model_policy.py` — Flash for picks, Coder for netlist JSON |
| Text disk cache | **On by default** — repeat prompts skip API |
| Text usage ledger | `data/llm/hardware-splicer-text-usage.json` |
| Vision usage ledger | `data/vision/hardware-splicer-vision-usage.json` |
| Provider fallback | **Qwen → agy** on quota/403 (`qwen_then_agy` default) |
| Authoritative DashScope quota | **Console only** — no public API |

**Stopped here on purpose.** Further golden-suite tuning has diminishing returns. Reopen when a real intake fails, quota blocks daily dev, or you unify Circuit-AI spend.

---

## Architecture (text)

```
User goal / intake
       │
       ▼
┌──────────────────┐     cache hit? ──► return cached JSON
│  call_llm_chat   │◄──── .cache/hardware-splicer/llm-responses/
│  (llm_text_client)│
└────────┬─────────┘
         │ miss
         ▼
   qwen_then_agy (default)
         │
    ┌────┴────┐
    ▼         ▼
 Qwen HTTP   agy CLI (--print)
 DashScope   Antigravity / Gemini sub quota
         │
         ▼
   text_usage_ledger.json
```

**Truth layer** (always deterministic): module graph → KiCad compile → ERC/DRC/safety. LLM advises routing and novel phrases; it does not override DRC.

**Key modules**

| File | Role |
|------|------|
| `integrations/llm_text_client.py` | Cache, ledger, provider chain |
| `integrations/qwen_text_client.py` | Raw Qwen HTTP + `call_qwen_chat` alias |
| `integrations/agy_text_client.py` | `agy --print` subprocess backend |
| `integrations/qwen_model_policy.py` | Per-stage model + rotation |
| `integrations/build_id_hints.py` | Keyword build pick + LLM reconcile |
| `module_picker.py` | Regex-first compose; LLM for novel phrases |
| `llm_response_cache.py` | Disk cache |
| `text_usage_ledger.py` | Local token accounting |

---

## Quick setup

```bash
cp .env.example .env.local
# Set DASHSCOPE_API_KEY or QWEN_API_KEY (Singapore intl endpoint)
# Optional: agy on PATH for fallback (Antigravity CLI)
```

Recommended `.env.local` for ongoing dev:

```bash
HARDWARE_SPLICER_LLM_PROVIDER=qwen_then_agy
HARDWARE_SPLICER_LLM_CACHE=1
HARDWARE_SPLICER_AGY_TIMEOUT_S=600
```

**Offline-first dev** (no API spend):

```bash
export HARDWARE_SPLICER_OFFLINE_COMPOSE=1
export HARDWARE_SPLICER_OFFLINE_SALVAGE=1
```

**Qwen-only when pools are healthy:**

```bash
export HARDWARE_SPLICER_LLM_PROVIDER=qwen
```

**agy-only** (slow, separate quota):

```bash
export HARDWARE_SPLICER_LLM_PROVIDER=agy
```

---

## CLI commands

```bash
# Active per-stage Qwen models and rotations
python3 scripts/hardware_splicer.py qwen-models

# Local text LLM spend (Qwen + agy, cache hits)
python3 scripts/hardware_splicer.py text-usage
python3 scripts/hardware_splicer.py text-usage --json

# Local vision spend
python3 scripts/hardware_splicer.py vision-usage --provider qwen

# Quota audit (local ledgers + optional live probe)
python3 scripts/hardware_splicer.py llm-quota
python3 scripts/hardware_splicer.py llm-quota --probe --probe-limit 10 --json

# Benchmark: offline baseline only (fast, no API)
python3 scripts/benchmark_llm_gain.py --offline-only

# Standalone audit script (same as llm-quota)
python3 scripts/qwen_quota_audit.py --json
```

---

## Environment variables

### Provider + cache

| Variable | Default | Meaning |
|----------|---------|---------|
| `HARDWARE_SPLICER_LLM_PROVIDER` | `qwen_then_agy` | `qwen` \| `agy` \| `qwen_then_agy` \| `agy_then_qwen` |
| `HARDWARE_SPLICER_LLM_CACHE` | `1` | Disk cache on/off |
| `HARDWARE_SPLICER_LLM_CACHE_DIR` | `.cache/.../llm-responses` | Cache directory |
| `HARDWARE_SPLICER_LLM_CACHE_BYPASS` | off | Force fresh API calls |
| `HARDWARE_SPLICER_TEXT_LEDGER` | `data/llm/...` | Text usage log path |
| `HARDWARE_SPLICER_AGY_MODEL` | `gemini-2.5-flash` | Model passed to `agy --model` |
| `HARDWARE_SPLICER_AGY_TIMEOUT_S` | `600` | agy print timeout (seconds) |
| `HARDWARE_SPLICER_AGY_DISABLED` | off | Skip agy even if on PATH |
| `HARDWARE_SPLICER_AGY_BIN` | `agy` | agy binary name/path |

### Offline / LLM-first

| Variable | Effect |
|----------|--------|
| `HARDWARE_SPLICER_OFFLINE_COMPOSE=1` | Regex/hybrid module pick only |
| `HARDWARE_SPLICER_OFFLINE_SALVAGE=1` | Keyword build pick + heuristic resolve |
| `HARDWARE_SPLICER_LLM_FIRST=0` | Disable LLM-first policy |
| `HARDWARE_SPLICER_QWEN_*=0` | Per-stage Qwen disable (see `.env.example`) |

### DashScope

| Variable | Meaning |
|----------|---------|
| `DASHSCOPE_API_KEY` / `QWEN_API_KEY` | Singapore intl API key |
| `DASHSCOPE_BASE_URL` | Default `https://dashscope-intl.aliyuncs.com/compatible-mode/v1` |
| Per-stage `HARDWARE_SPLICER_QWEN_*_MODEL` | Override primary model per stage |

See `.env.example` for full per-stage list.

---

## DashScope quota (console)

Alibaba does **not** expose remaining free quota via API.

1. Open [Model Studio console](https://modelstudio.console.alibabacloud.com/)
2. Region: **Singapore** (top-right)
3. **Model Usage → Free Quota** tab
4. Optional: enable **Free Quota Only** per model to block paid overage

Free tier: ~**1M tokens per model** (separate pools), ~90 days. Emails at ~20% and exhaustion **per model**.

---

## Benchmarks (2026-06)

| Metric | Offline | Online (post-fix) |
|--------|---------|-------------------|
| Golden build_id match | 7/7 | 7/7 |
| Compose graph DRC (56 phrases) | 100% | 100% |
| Salvage DRC pass | 100% | 100% |
| Wall time (offline) | ~0.1s | — |

Run offline baseline anytime:

```bash
python3 scripts/benchmark_llm_gain.py --offline-only
```

Full online benchmark is intentional and costly — use rarely.

---

## What we can do

- Salvage → module graph → DRC-clean compile on golden + trained phrases (offline or online)
- Spread Qwen load across per-stage model pools + rotation
- Survive Qwen 403 with agy fallback (slow)
- Avoid repeat API cost via disk cache
- Track local text + vision spend
- Probe rotation models for exhaustion (`llm-quota --probe`)
- Develop offline indefinitely with `OFFLINE_*` flags

## What we cannot do (yet)

| Gap | Notes |
|-----|-------|
| Authoritative account quota in code | Console only |
| Fast agy calls | CLI subprocess; minutes per call is normal |
| Exact agy token metering | Estimated from character count |
| agy for vision / photos | Use Qwen VL or `GEMINI_API_KEY` |
| Unlimited anything | agy has its own weekly cap |
| Arbitrary user prompts offline | Need LLM or more `MODULE_HINTS` / golden cases |
| Unified quota with Circuit-AI | Separate Qwen rotation and ledgers |
| Flux-class interactive PCB UI | Out of scope for this push |

---

## When to reopen this work

1. **Real intake fails** → add case to golden set, fix root cause (not more rotation tuning)
2. **Quota emails block dev** → `LLM_PROVIDER=agy`, console Free Quota Only, check `text-usage`
3. **Circuit-AI + HS daily** → unify provider policy and ledgers
4. **Product pivot to interactive design** → new scope, not salvage tuning

---

## Regression fixes landed (this arc)

- `build_id_hints.py` — keyword wins over generic LLM build pick (e.g. fan → fume extractor)
- Hybrid `pick_modules_for_goal()` — regex for trained phrases, Qwen only for novel
- `_deterministic_fixup()` runs online (MOSFET / level-shifter)
- Workshop `suggested_build_id` reconciled
- `benchmark_llm_gain.py --offline-only` flag
- Dual JSON benchmark output fixed

---

## Salvage intelligence (bench-facing)

Every salvage package now includes:

| Artifact | Meaning |
|----------|---------|
| `SALVAGE_GAP_ANALYSIS.json` | What you have, what was auto-filled, what to buy |
| `SALVAGE_BOM.json` | Catalog MPN hints + USD estimates (on-hand vs to-buy) |
| `SALVAGE_BOM.csv` | Same BOM in spreadsheet-friendly CSV |
| `BRINGUP_CARD.json` / `BRINGUP_CARD.md` | Pin-level hookup + pre-power checklist |
| `firmware/*.ino` + `FIRMWARE_SCAFFOLD.json` | Starter sketch from bring-up GPIO assignments |
| `SALVAGE_REVISION.json` | Diff after `salvage-edit` CLI incremental changes |
| Offline `attachments` | Filename/meta/OCR → `available_parts` before salvage (no vision API) |
| Vision `identified_parts` | Photo → merged into `available_parts` when vision runs |

CLI: `python3 scripts/hardware_splicer.py salvage-edit --brief … --edits edits.json --out /tmp/rev`

Offline OCR: set `HARDWARE_SPLICER_OFFLINE_OCR=0` to disable; requires `pytesseract` + Pillow when enabled.

Salvage BOM pricing: catalog `priceUsd` → prototype fallbacks → optional JLC `price1` when `HARDWARE_SPLICER_JLC_ENRICH=1` (same client as fab BOM).

Demo dashboard (`apps/hardware-splicer-demo`) shows gap/BOM/bring-up/firmware panels for the plant watering brief.

Emitted on `intake`, `splice-build`, and `salvage-edit` runs.

---

| Date | Change |
|------|--------|
| 2026-06-11 | Per-stage Qwen policy, model guide, golden regression fixes |
| 2026-06-15 | Text cache, text ledger, agy fallback, `text-usage` / `llm-quota` CLI, wrap-up doc |
| 2026-06-15 | Salvage gap analysis, shopping list, bring-up card, vision→inventory merge |
