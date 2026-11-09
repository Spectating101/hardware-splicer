# HS evidence-calibrated numeric test gate: source-bound correction

The preceding matched A/B (PR #324) revealed an engineering failure:
HS source-graph assisted Gemini invented exact tablet current cutoffs
>0.4A and <0.05A, despite having no manufacturer reference curve,
service specification or verified baseline measurement.

This new branch **does not change** the previously frozen A/B and does
not load outcomes from PR #321 or the postreview PR #325.

## Actual implementation

- restoration_numeric_truth_gate.py detects *directional numeric limits*
  expressed with electrical/physical units in proposed test instructions
  where the HS ledger explicitly records missing source documentation.
  Examples: above 12V, <0.05A, >0.4A, below 45°C.
- Device-reported numeric measurements are NOT promoted to verified
  manufacturer cutoffs by the source graph. An actual observed "12V"
  is not automatically a recommended or safe 12V diagnostic threshold.
- HS-assisted model output that recommends unsupported numeric cutoffs
  fails validation. The old A/B control model is untouched.
- restoration_quality_correction.py verifies original frozen prediction
  hash, exact first-window source evidence hash, prompt hash, graph hash,
  model identity, and only admits one explicit correction turn with
  source evidence unchanged. It records both parent and correction hashes.
- The correction prompt explains the known epistemic violation rather
  than supplying outcome labels, service diagrams or fake instruments.
  It requests qualitative externally observable checks instead.
- Original model failures are NEVER silently overwritten or rerolled.
- The gate is NOT a proof of engineering correctness. It is regex
  based and cannot catch every unsafe or unfounded quantitative claim.

## Real Samsung Tab S6 Lite trial

Prior frozen HS-assisted response in PR #324 had diagnostic cutoffs
>0.4A and <0.05A for supposedly normal/abnormal USB current. The
tool detected both from the saved source-bounded real model receipt.

One new live Gemini 3.8 Flash Low correction (14.83 seconds) produced
a structurally valid plan with no comparator-type unsourced numeric
thresholds. It suggested a non-invasive USB host/charging interaction
check and observational physical response to a forced restart.

The new plan is still a **hypothesis**, not a verified diagnosis.
Combined model latency in this tablet example is approximately
12.19 + 14.83 = 27.02 seconds, compared to 9.27 seconds for
the original plain Gemini trial. So the stronger evidence discipline
costs additional time and model budget.

Stored outcome-free receipt:
evidence/tab_s6_numeric_correction_live.json

## Reproduce from the *original* uncommitted source captions

PYTHONPATH=src python3 examples/restoration_video_bench/diversity/run_tablet_quality_repair.py --captions-vtt /tmp/hs-restoration-video-intake-20261110/CrOf4SmyGvE.en-orig.vtt --out /tmp/tab_quality_correction.json

It refuses to overwrite output, uses the existing Antigravity CLI,
makes one correction call, and does not invoke any paid API fallback.

## Next real engineering advantage

A human-verifiable good repair assistant needs:
- factual external source retrieval (real manufacturer schematic,
  service bulletin, boardview and exact component datasheet with
  provenance) rather than simply retelling video narration;
- calibrated safe instrument checks and a distinction between
  manufacturer spec, narrated number and actual technician measurement;
- candidate tests that discriminate faults at known risk/cost;
- independent holdout evaluation beyond these six curated videos.

No repairs, parts procurement, physical measurements, powered internal
PSU testing, video-frame analysis or claims of functional restoration
have been performed here.
