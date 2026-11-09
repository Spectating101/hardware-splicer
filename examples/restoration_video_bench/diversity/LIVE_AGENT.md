# HS native restoration reasoning agent: live nine-domain experiment

This branch starts from the frozen pre-outcome PR #320, NOT from the post-outcome
PR #321. Neither live model prompts nor prediction files contain creator fixes.

## Implemented

- Native repair_intake free text into a real Antigravity Gemini inference turn,
  using HS's existing agy_text_client. The existing command needed a real fix:
  the prompt must be passed as --print=CONTENT rather than a bare --print
  before --model, otherwise --model is accidentally treated as the prompt.
- Explicit option for local Ollama loopback only, with NO fallback to paid APIs.
- A strictly typed differential (up to three hypotheses), evidence IDs,
  a safe next diagnostic check, uncertainty and explicit abstention.
- Hard rejection for unknown evidence references, missing model fields,
  unsafe requests to bypass protections or probe live mains, or attempted
  outcome leakage. Physical repair, procurement and power authority are
  always false.
- An optional incremental observation flow requiring an earlier signed receipt,
  a named observer, and explicit source type; no silent edits to the prior step.
- Direct early-caption intake from locally provided WebVTT with timestamps,
  source SHA, a strict cutoff (default first 120 seconds), and deduplication.
  Caption text remains unverified creator speech, NOT a direct video-frame
  or instrument measurement.

## Optiplex live results

Gemini 3.8 Flash Low through the user's existing Antigravity CLI:
- Nine of nine source-separated cases produced valid model differential plans.
- Approximately 79 seconds total inference across the nine trials.
- Not nine correct repairs; accuracy against independently reported faults
  must be scored separately after freezing these receipts.
- Prior baseline: 0/9 raw inputs accepted by HS's hardcoded rule engine.
- Hardware reparability, source video frames, actual diagnosis measurements,
  experimental device repairs and physical outcomes are NOT claimed.

Preserved full nine-case inference:
evidence/agy_gemini38_flash_low_nine_live.json

If a direct source caption experiment is present, its receipt is saved as
evidence/bosch_raw_vtt_first120_live.json; the full transcript is NOT stored
in this repository.

## Reproduce without any paid API fallback

Nine cases (pass multiple case IDs as needed):
    PYTHONPATH=src python3 examples/restoration_video_bench/diversity/run_live_agent.py \
      --provider agy --model gemini-3.8-flash-low \
      --case-id bosch_dryer_slow_heat --out /tmp/hs_bosch.json

Direct first 120 seconds of a locally available auto-caption VTT:
    PYTHONPATH=src python3 examples/restoration_video_bench/diversity/run_live_agent.py \
      --provider agy --case-id bosch_dryer_slow_heat \
      --captions-vtt /tmp/RxgjyTRtKZs.en-orig.vtt \
      --cutoff-seconds 120 --out /tmp/hs_caption_result.json

Optional local-only baseline:
    PYTHONPATH=src python3 examples/restoration_video_bench/diversity/run_live_agent.py \
      --provider ollama --model qwen2.5:1.5b-instruct \
      --case-id bosch_dryer_slow_heat --out /tmp/hs_ollama_result.json

A bounded CPU Ollama trial timed out previously and is not counted as a fault
classification. No automatic model substitution or silent fee is authorized.

## Limits

Model-generated differential hypotheses are unverified. Structural validation
does not establish diagnostic precision or test safety in all circumstances.
The model is not authorized to tell a user to solder a board or intervene in
mains/battery circuitry. The nine input examples were previously curated by
a human with knowledge of published videos; they are not a fresh, independent
scientifically blind sample. Inference only sees initial pre-outcome evidence,
but outcome evaluation must remain on a separate branch.

The next meaningful proof requires creator outcome adjudication per specific
failure mechanism, source-linked follow-up measurements, and eventual bench
validation on actual hardware. CI never makes live model calls.
