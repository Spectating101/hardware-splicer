# HS prospective restoration challenge: Xbox Series S

Date: 2026-11-10. Status: PRE-OUTCOME, source-blind PROCEDURE only.
No full YouTube video, transcript, circuit measurement, final fix or repair
result has been inspected for this fifth case. No physical repair performed.

Source: https://www.youtube.com/watch?v=yXFmSrgb0xI
Creator: Rosales Super Tech, "Purchased Xbox Series S from e-Bay - No Power Repair".
The only case-specific observation admitted is "no power".

Independent architecture: Microsoft explicitly documents an internal AC mains
power supply and a button board, not user-replaceable battery terminals.
https://learn.microsoft.com/en-us/xbox/service-guides/series-s-console/series-s-device-id-and-disassembly

## Why this test is different

The four older video cases were curated after their outcomes were known. The
original HS rule engine therefore gives evidence of structured triage, not
unseen diagnostic skill. This new case is held at its public symptom stage.
The original ranking is preserved rather than optimized to the case's solution.

Unmodified HS ranks battery-terminal corrosion first for the Xbox, with
battery-path and slide-switch hypotheses in the top three. This is an observed
model deficiency: generic "no power" rules ignore power architecture. The
architecture gate rejects these incompatible mechanisms and ABSTAINS rather
than guessing an internal PSU fix or directing dangerous mains probing.

Abstaining on an incompatible taxonomy is useful but is neither a correct
root-cause diagnosis nor evidence of video-processing autonomy.

## Reproduce, seal, then adjudicate

1. Without reading the actual fix, use the video title/description only and
   independently documented device architecture to define an intake.
2. Execute this code against the old triage engine and record both raw
   differential and relevance-gated abstention.
3. Preserve Git SHA, input SHA, engine SHA, and published receipt SHA-256.
4. Only AFTER that, have a separate reviewer examine video evidence; store
   its observations/outcome EXTERNALLY, not in this prediction branch.
5. Score with the exact external preregistered receipt digest; do not modify
   the initial hypothesis after seeing the outcome.

    PYTHONPATH=src python3 examples/restoration_video_bench/prospective/predict.py \
      --case examples/restoration_video_bench/prospective/cases/xbox_series_s_2021_no_power.json \
      --out /tmp/hs_xbox_pre_outcome.json

    PYTHONPATH=src python3 -m pytest -q tests/test_restoration_prospective.py

Post-outcome ONLY, with a separate human-reviewed label file:

    PYTHONPATH=src python3 examples/restoration_video_bench/prospective/score.py \
      --receipt /tmp/hs_xbox_pre_outcome.json \
      --external-outcome /secure/external_review.json \
      --expected-receipt-sha256 DIGEST_FROM_PRE_OUTCOME_CI \
      --out /tmp/hs_xbox_review_score.json

External outcome schema: case_id, source_url, reviewer,
evidence_description, adjudication_status (resolved/unresolved/ambiguous),
optional quality, and root_cause only when resolved.

No published result should say the repair was solved by HS: the benchmark
measures the diagnostic method. The creator's account remains weaker evidence
than independent measurements on the device.

## Limitations and safety

This is a procedural split, NOT double-blind science. A human could learn the
published answer elsewhere. Hashing establishes integrity of the submitted
prediction, not clinical or engineering correctness. Microsoft's service
guide warns of lethal shock hazards from the internal AC power supply. No
internal powered probing, PSU rework, or unqualified repair is authorized.
