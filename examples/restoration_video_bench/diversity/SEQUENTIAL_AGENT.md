# HS evidence-fed diagnostic revision: PS5 Pro

The previous PR #322 evaluated one pre-outcome diagnosis. This branch adds
**sequential** video-caption observations while preserving the original
model response and requiring cryptographically linked continuation receipts.

## Live result (Gemini 3.8 Flash Low through existing Antigravity CLI)

| Admitted source | First-ranked hypothesis |
| --- | --- |
| First 0-120 seconds; original sealed PR #322 | HDMI damage possibly causing a power short |
| Additional 120-300 seconds | Internal PSU failure (creator reports zero volts) |
| Additional 300-360 seconds | Mainboard 12V input rail short (creator reports 12V from isolated PSU, 2 ohms across board input and multiple low-resistance capacitor locations) |

The creator later isolated/replaced a motherboard power MOSFET, which is
**outside** the evidence windows in this experiment. The model reached the
board-short fault domain but did not isolate or name a MOSFET as a confirmed
cause at 360 seconds.

This is actual model execution, but the numbers and physical conditions
are **creator narration**, NOT independently observed measurements by HS.
The user/researcher has previously reviewed the later video outcome, so
the study is procedurally sealed at the model-input level, not fully
independent blinded science.

## Integrity and authority limits

- Original PS5 PR #322 receipt digest:
  3d6df64c63f2546711b7ac2778ecdfe8e358e2364ef9b33e3bb852347d2bc9b4
- Original caption evidence SHA is recomputed from the *unchanged* source
  WebVTT and matched against the original model's evidence/prompt hashes
  before running any follow-up.
- Later windows 120-300 and 300-360 are contiguous. The code refuses a
  skip, overlapping windows, or a substituted caption source hash.
- Each new model turn has its own source-evidence hash, prompt hash, raw
  model-response hash, receipt hash and preceding receipt hash.
- Earlier model hypotheses are explicitly marked as **guesses, not source
  evidence**. Later video reports have their own independent E IDs.
- No video frames watched by HS; no hardware repaired, powered, tested,
  probed or verified; no parts purchased. Every repair action remains
  unauthorized. Source has safety hazards including AC-powered PSUs.
- Auto-caption files remain local and uncommitted; only short, provenance-
  linked inference outputs, dates/windows and hashes are in the PR.
- No repair outcome label or postreview PR #321 is imported in model prompts.

## Reproduce locally from the video source's WebVTT

    PYTHONPATH=src python3 examples/restoration_video_bench/diversity/run_ps5_sequential.py \
      --captions-vtt /tmp/hs-restoration-video-intake-20261110/xbp8lIggbxY.en-orig.vtt \
      --model gemini-3.8-flash-low \
      --out /tmp/ps5_sequential.json

The runner uses the user's existing Antigravity CLI account. It does not
call an API key, install a paid service or use a fallback provider.
The actual live output is frozen in
evidence/ps5_sequential_measurement_live.json. Repeating live inference
may yield different natural-language details.

    PYTHONPATH=src python3 -m pytest -q tests/test_restoration_measurement_feedback.py

Tests do not call a model; synthetic captions exercise the same append-
only architecture offline, while full YouTube transcript comparison is
run only when the uncommitted local source is available.

## Next acceptance gate

Repeat precommitted evidence-fed diagnosis on **additional unseen devices
with independent instrument traces**, ideally real observed multimeter
results or schematics/boardview matched to time-coded video frames.
Measure not only whether fault-family ranking improves but also whether
the proposed next test was safe, cost-effective and discriminatory.
