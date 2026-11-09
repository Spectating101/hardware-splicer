# Actual HS graph-assisted diagnosis A/B: post-freeze review

This post-review branch is stacked *on top* of the frozen prediction PR #324.
The inference PR and its model prompts remain outcome-free. This branch
carries creator-reported outcomes and transparent qualitative annotations.

## Evidence chain

- Precommitted experiment protocol/code: Git commit 77ecb648956173225a4c20370df7391d816c9666.
- Frozen 12 real Gemini inference receipts: commit
  2502fa02d20d67e6bfec376834ca7933c5e90944, file SHA256
  68124e6a091855d24ad363ac465ac4cc3976ca3c84e0f596ca0398a03c2d12d9.
- Creator-narrated outcome review: PR #321, commit
  160befae4c476dfde8b93b72c10bd0b0f6b62172; source JSON SHA256
  9bcb6910b251718afe0e5fb38c9043da426d934440134103d356ee3e1420db38.
- Copy of the exact upstream creator review is retained here to make
  deterministic CI grading reproducible. It is NOT imported by PR #324's
  inference code.
- The grade counts are manually assigned to exact predicted mechanism
  ranks; score_graph_ab_postreview.py verifies source file hashes,
  6/6 case coverage, original source fault labels, hypothesis indexes,
  and resulting counts. It cannot independently infer scientific truth.

## Results

| Metric | Plain Gemini | HS source-graph assisted Gemini |
| --- | ---: | ---: |
| Valid model outputs | 6/6 | 6/6 |
| Exact fault-family coverage | 4/8 | 3/8 |
| Broad subsystem/domain only | 4/8 | 4/8 |
| Unpredicted mechanism | 0/8 | 1/8 |
| Cases with first-ranked exact family | 3/6 | 2/6 |
| Cases covering all reported faults at exact-family specificity | 2/6 | 1/6 |
| Total inference time | 58.57s | 68.35s |

Note: galaxy tablet fault adjudication is *strictly multi-fault*:
proposing "screen assembly or flex connector" does not establish two
independent diagnoses (failed panel AND intermittently kinked ribbon).
Both arms obtain partial credit for the separate ribbon failure.

- Bosch: both arms ranked airflow restriction and neither isolated the
  specific external exhaust kink.
- DeWalt: both arms preferred battery/trigger mechanisms over the
  creator's dust-packed brushed motor; each mentioned the motor domain
  only as a later, nonspecific alternative.
- Tablet: both arms recognized the faulty display family. The HS model
  added unsourced amperage cutoffs: ">0.4A" and "<0.05A", despite the
  input having no datasheet or empirically verified healthy reference.
- PS5: both ranked visible HDMI damage first. Plain model suggested
  generic mainboard standby rail failure second, a partial power domain
  overlap with the reported MOSFET short. HS model offered no motherboard
  fault as a distinct candidate; it also suggested interpreting AC
  wattmeter behavior as confirmation of HDMI deformation, an unwarranted
  leap.
- DeLonghi: plain model explicitly named a thermal fuse among first
  ranked causes and a leaking O-ring as its third; HS model recognized
  seals but only a broad heating subsystem, missing the cutout family.
- A53: both found digitizer/flex subsystem, not exact damaged contact
  trace. Both recommended reasonable OTG check.

## Interpretation

On this tiny and non-independent sample, the graph-plus-prompt
intervention was not an improvement. Do NOT treat the numerical difference
as statistically significant or the creator's captions as laboratory
ground truth.

The immediate engineering lesson is **provenance alone cannot supply
missing measurements**. A useful next experiment should instead connect
real external engineering data to HS: source-authenticated service manuals,
boardviews, schematics and component datasheets, or safe external instrument
readings independently recorded and verified. An authority gate should
flag uncited numeric thresholds and test results. Then rerun a matched
case set with equal model/budget constraints and a separate blinded
evaluator.

No actual device repair, video-frame inspection, bench instrument
measurement, component procurement or licensed electrical action occurred.

## Reproduce

    python3 examples/restoration_video_bench/diversity/score_graph_ab_postreview.py \
      --predictions examples/restoration_video_bench/diversity/evidence/graph_ab_six_live.json \
      --review examples/restoration_video_bench/diversity/evidence/graph_ab_postreview_annotations.json \
      --creator-outcomes examples/restoration_video_bench/diversity/evidence/graph_ab_review_source_PR321.json \
      --out /tmp/graph_ab_postreview_score.json

The scorer is offline and never invokes the model.
