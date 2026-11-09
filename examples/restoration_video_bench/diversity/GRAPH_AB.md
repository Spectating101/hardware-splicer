# Matched A/B pilot: plain Gemini vs HS source-graph assisted Gemini

This is a precommitted six-video test design, before A/B responses are collected.

## Question

Does actual HS engineering source-graph provenance and discriminating-test
guidance improve the initial diagnostic plan compared with the SAME Gemini
3.8 Flash Low model on identical first-120-second video captions?

CONTROL: native repair_intake + normal Gemini model prompt.
TREATMENT: exact same repair_intake evidence, plus a real call to
hardware_splicer.engineering_source_graph.build_engineering_source_graph,
which records source ID, video hash, individual evidence IDs, timecodes,
and authority DECLARED. Treatment adds the source graph's ledger and
asks the same model to choose a low-risk check that distinguishes two
plausible faults.

Neither arm sees any later video outcomes, schematics, boardviews, video
frames, direct hardware measurements, or physical tests. The graph gives
no technical claims beyond the source material. Both arms have the same
output schema, model and one model call.

CRITICAL CONFOUND: treatment has a longer prompt with additional instructions
and provenance; this is a graph-plus-prompt intervention, NOT evidence
that adding the source graph by itself makes Gemini smarter. Track cost,
latency and response changes.

Frozen case and arm order:
1. Bosch dryer: HS then plain
2. DeWalt blower: plain then HS
3. Galaxy Tab S6 Lite: HS then plain
4. PS5 Pro: plain then HS
5. DeLonghi Eletta: HS then plain
6. Galaxy A53: plain then HS

Accuracy is NOT scored by the inference runner. Human post-review scoring
must be separated from the source-limited prediction data, distinguishing
top-one fault-family matches, multi-fault coverage, safe next tests,
premature parts replacement, and unknown/unscorable repairs. All captions
and narrated measurements have DECLARED authority, not MEASURED by HS.

Small sample, human case-selection bias, prior experimenter knowledge of
repairs, nonidentical prompt length and no independent hardware validation
are important limitations.

## Run
PYTHONPATH=src python3 examples/restoration_video_bench/diversity/run_graph_ab.py --captions-dir /tmp/hs-restoration-video-intake-20261110 --out /tmp/hs-graph-ab-six-cases.json

Writes an inspectable file after every model call. Refuses to overwrite
previous A/B results so model failures cannot silently be rerolled.
Uses existing Antigravity CLI subscription, not a new paid API.
