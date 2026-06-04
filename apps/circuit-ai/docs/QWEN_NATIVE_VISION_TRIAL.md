# Qwen Native Vision Trial

Circuit-AI can use Qwen as the paid native vision path for board photos. This is
intended as a small, measurable trial, not an always-on default.

## Why this exists

The current Copilot image path is an evidence bridge:

```text
board image -> local CV/OCR -> text evidence -> Copilot reasoning
```

Qwen adds a direct image path:

```text
board image -> Qwen VL pixels + local evidence -> structured board evidence
```

The goal is to find out whether native vision materially improves component
markings, package/region recognition, damage notes, connectors, test points, and
salvage planning.

## $5 trial configuration

Keep the default provider on Copilot until you are ready to spend credit. Then
set these in the frontend environment:

```env
QWEN_DISABLED=false
QWEN_OUT_OF_QUOTA=false
JARVIS_VISION_PROVIDER=qwen
QWEN_API_KEY=...
QWEN_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
QWEN_VISION_MODEL=qwen3-vl-flash
QWEN_VISION_MODEL_ROTATION=qwen3-vl-flash,qwen3-vl-30b-a3b-thinking,qwen-vl-ocr-2025-11-20
QWEN_LOW_QUOTA_MODELS=qwen-plus,qwen-plus-2025-07-28

VISION_MONTHLY_USD_LIMIT=5
VISION_DAILY_USD_LIMIT=1
VISION_MAX_USD_PER_CALL=0.05
VISION_REQUIRE_CACHE=true
VISION_MAX_CROPS_PER_SCAN=3
VISION_ESCALATE_ONLY_ON_UNCERTAIN=true
```

The provider will not run unless:

- `QWEN_DISABLED` and `QWEN_OUT_OF_QUOTA` are both unset/false
- `JARVIS_VISION_PROVIDER=qwen`
- `QWEN_API_KEY` or `DASHSCOPE_API_KEY` is present
- `VISION_MONTHLY_USD_LIMIT` is greater than zero
- a cache key is available when `VISION_REQUIRE_CACHE=true`

## Emergency quota stop

If Alibaba reports that Model Studio quota/resources are exhausted, stop Qwen at
the repo boundary before doing more tests:

```env
QWEN_DISABLED=true
QWEN_OUT_OF_QUOTA=true
JARVIS_VISION_PROVIDER=copilot
VISION_MONTHLY_USD_LIMIT=0
```

With either `QWEN_DISABLED` or `QWEN_OUT_OF_QUOTA` enabled:

- `POST /vision/qwen/board-evidence?live=true` returns `blocked_disabled`
  before any provider HTTP request.
- Jarvis refuses `JARVIS_VISION_PROVIDER=qwen`.
- Backend text reasoning refuses `LLM_PROVIDER=qwen`.
- Dry-run request previews remain available for shape/debug work without
  sending images or text to Qwen.

## Free-quota rotation

Do not use `qwen-plus` as the default trial path once its free quota is low.
Circuit-AI now routes Qwen calls through an explicit low-quota block list and
model rotation:

```env
QWEN_MODEL=qwen3.5-122b-a10b
QWEN_MODEL_ROTATION=qwen3.5-122b-a10b,qwen3-max,qwen3.5-plus-2026-02-15
QWEN_VISION_MODEL=qwen3-vl-flash
QWEN_VISION_MODEL_ROTATION=qwen3-vl-flash,qwen3-vl-30b-a3b-thinking,qwen-vl-ocr-2025-11-20
QWEN_LOW_QUOTA_MODELS=qwen-plus,qwen-plus-2025-07-28
```

The router filters low-quota models before a call and retries the next candidate
only for quota/billing-style 403/429 errors such as
`AllocationQuota.FreeTierOnly`. Auth failures are not retried across models.

## Budget tracking

Backend paid vision calls are recorded in:

```text
data/vision/qwen-spend-ledger.json
```

Frontend Jarvis calls may also keep their own UI cache ledger in:

```text
.next/cache/jarvis/vision-spend-ledger.json
```

Override with:

```env
VISION_SPEND_LEDGER=/absolute/path/to/vision-spend-ledger.json
```

The status endpoint reports the selected provider and budget snapshot:

```text
GET /api/jarvis/status
```

The backend status endpoint reports Qwen key/budget readiness without exposing
secrets:

```text
GET /vision/qwen/status
```

## Backend adapter

The reusable backend adapter lives at:

```text
src/vision/qwen_board_vision.py
```

It provides the explicit board-evidence endpoint:

```text
POST /vision/qwen/board-evidence
```

Default mode is dry-run. It redacts image data, estimates cost, and returns the
request preview without calling Qwen. Live mode requires `live=true`,
`QWEN_API_KEY` or `DASHSCOPE_API_KEY`, and `VISION_MONTHLY_USD_LIMIT > 0`.
The default output cap is 4096 tokens because live Qwen board evidence can
otherwise truncate JSON and leave the deterministic parser with no usable
`board_evidence`.

The endpoint returns:

- `qwen_board_vision`: provider status, preflight, usage, parsed response
- `board_evidence`: normalized `board_evidence.v1`
- `vision_evidence_bridge`: deterministic candidate resources and hazards
- `hardware_plan`: optional downstream plan showing gates, trust, and blocked
  power/splice authority

## Multi-photo reconstruction

The production workflow is not "one board photo decides everything." Treat each
photo as one observation from a physical board-in-hand session:

```text
many board photos -> per-photo evidence -> fused board evidence -> canonical board map -> hardware plan
```

Photos do not need fixed slots such as top/bottom/left/right. Wide shots,
angled shots, connector closeups, marking closeups, damaged-area closeups, and
manual/model observations can all be submitted as a `board_photo_set` or
`photo_observations` bundle.

The fusion endpoint is:

```text
POST /vision/board-evidence/fuse
```

Minimal payload shape:

```json
{
  "goal": "inspect this physical board for salvage and reuse options",
  "board_photo_set": {
    "photo_observations": [
      {
        "photo_id": "wide_angle_1",
        "view_hint": "wide angled board photo",
        "provider": "qwen",
        "parse_diagnostics": {"json_valid": true, "truncated": false},
        "board_evidence": {"schema_version": "board_evidence.v1", "components": [], "connectors": []}
      },
      {
        "photo_id": "closeup_marking_1",
        "view_hint": "closeup of IC marking",
        "board_evidence": {"schema_version": "board_evidence.v1", "markings": []}
      }
    ]
  }
}
```

The fused result includes:

- `multiview_board_reconstruction`: photo count, usable observations, source refs,
  contradictions, and next capture requests
- `board_evidence`: one fused `board_evidence.v1` candidate dossier
- `canonical_board_map`: normalized evidence-map items, approximate board zones,
  mapped/unmapped counts, and layout confidence
- `identity_links`: candidate links such as a closeup marking resolving an IC seen
  in a wider photo
- `vision_evidence_bridge`: deterministic resource/hazard candidates
- `hardware_plan`: optional repair/reuse/splice plan with evidence gates

Every fused item keeps `source_refs`, so later UI and review flows can show which
photo supported a component, marking, connector, damage item, or salvage
candidate. Multi-photo agreement raises candidate confidence, but it still does
not authorize first power, pin-level splice, or production repair without the
measurement/authority lanes.

The board map is deliberately an evidence index, not CAD or photogrammetry. It
is useful for capture guidance, review, rough component placement, and planner
context. Metric cut geometry, net reconstruction, and first-power authority
still require topology/measurement evidence.

## Visual topology hypotheses

The backend now derives `visual_topology_hypothesis.v1` after board-evidence
fusion. This does not promote photos into measured topology. It converts the
visual dossier into:

- component anchors, such as a marking-linked CH340C bridge candidate
- connector hypotheses, such as USB connector, UART header, I2C/GPIO header, or
  power entry candidates
- candidate component-to-connector paths, such as USB connector to USB bridge or
  USB/UART bridge to UART header
- a measurement queue for pinout, continuity, no-short resistance, voltage,
  logic level, first-power, current, and thermal evidence

The hardware plan exposes this under `analysis.visual_topology_hypothesis` and
adds its tasks to `analysis.next_evidence_tasks`. The API endpoint
`POST /vision/board-evidence/visual-topology` can be used directly for a
candidate-only topology workup. The trust boundary stays explicit:
`can_power_or_splice=false` until `topology_evidence.v1`, repair authority, and
outcome/release gates close.

## Dry-run harness

Before spending credit, generate crops and request previews:

```bash
python3 scripts/vision_baseline_from_artifacts.py
python3 scripts/qwen_vision_trial.py --limit 6 --max-crops 3
```

This writes:

```text
eval/qwen_trial/latest_report.json
eval/qwen_trial/latest_report.md
eval/qwen_trial/crops/
eval/qwen_trial/requests/*.preview.json
```

The dry-run report estimates the current 6-case sample at roughly fractions of
a cent for `qwen3-vl-flash`, but treat that only as a preflight estimate. The
live response usage is recorded after each call.

Cached live responses can be replayed through the planner without spending more:

```bash
python3 scripts/evaluate_qwen_pipeline_assessment.py
```

This writes:

```text
eval/qwen_trial/live_pipeline_assessment.json
```

Run live only when ready:

```bash
VISION_MONTHLY_USD_LIMIT=5 \
VISION_DAILY_USD_LIMIT=1 \
VISION_MAX_USD_PER_CALL=0.05 \
QWEN_API_KEY=... \
python3 scripts/qwen_vision_trial.py --live --limit 6 --max-crops 3
```

Then verify cached live outputs with DeepSeek:

```bash
python3 scripts/deepseek_verify_qwen_trial.py
DEEPSEEK_API_KEY=... python3 scripts/deepseek_verify_qwen_trial.py --live
```

The scan UI also exposes a manual **Verify evidence** action that calls
`/api/jarvis/verify-board-evidence`. Without a DeepSeek key, it returns an
offline deterministic gate report instead of spending.

## Current cached live result

The first curated Qwen live run used `qwen3-vl-flash` with three images and
then replayed the cached responses locally:

- Trial report: `eval/qwen_trial/latest_report.json`
- Pipeline assessment: `eval/qwen_trial/live_pipeline_assessment.json`
- Live calls: 3
- Cached replay calls: 0
- Recorded actual total: `$0.000498`
- Valid JSON rows: 3/3
- Rows with selected planner resources: 2/3
- Rows with full selected capability coverage: 2/3
- Rows authorized for power/splice from vision alone: 0/3

Observed behavior:

- Raspberry Pi photo now normalizes connector-like component rows into six
  connectors, classifies the board as `single_board_computer_module`, and
  selects evidence-gated controller/power/connector/network/display resources.
- Generic toy PCB photo stays an `unknown_low_voltage_module` and becomes an
  identification/bench-test target instead of inventing BLE/RF from the word
  "reusable".
- Bare trace/defect image remains evidence-poor and correctly asks for more
  evidence instead of selecting resources.

## Evidence contract

Vision responses now include a normalized `board_evidence` object:

```json
{
  "schema_version": "board_evidence.v1",
  "components": [],
  "markings": [],
  "regions": [],
  "damage": [],
  "connectors": [],
  "test_points": [],
  "salvage_candidates": [],
  "recommended_checks": [],
  "uncertainty": {
    "level": "medium",
    "reasons": [],
    "missing_evidence": [],
    "next_actions": []
  }
}
```

This lets local CV, Copilot bridge, Qwen, and later DeepSeek verification work
against one evidence shape.

## Official API notes

Alibaba Model Studio documents Qwen through an OpenAI-compatible chat completion
API. The international endpoint is:

```text
https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions
```

Virginia and Beijing endpoints are region-specific. Image inputs use OpenAI-style
`image_url` content blocks, including data URLs for uploaded images.

References:

- https://www.alibabacloud.com/help/en/model-studio/qwen-vl-compatible-with-openai
- https://www.alibabacloud.com/help/en/model-studio/vision/
- https://www.alibabacloud.com/help/en/model-studio/models
