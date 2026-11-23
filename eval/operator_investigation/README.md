# Hardware Splicer bounded read-only operator investigation

The provider-neutral entry point is `hardware_splicer.operator_investigation.investigate_case(case, operator=..., max_steps=4)`. The `operator` function accepts a string and returns a JSON-like mapping. Optiplex Copilot currently supplies this interface through `copilot_text_operator`, but the investigation engine is not Copilot-specific.

## What the operator can do

- Request `source_graph`: an HS-generated source/claim/conflict graph including authority ceilings and unresolved claims
- Request `engineering_checks`: HS-generated electrical, power, mechanical and authority findings, with their missing inputs
- Finish with an advisory `hold` or `propose_review`, plus next tests

Every inspection is computed from the input by HS. No model can read arbitrary files, run shell commands, fetch URLs, issue physical control actions, set measurement evidence, change the graph, or award release authority. The model must inspect at least one tool before finishing. Premature final answers are rejected with feedback; unknown/repeated tool calls are rejected. All model/provider failures leave the decision at HOLD, while retaining completed inspections as evidence of partial progress. The loop is bounded to at most six operator turns.

## October 20, 2026 live Optiplex results

Case: `eval/source_agnostic_pilot/public_drv8833_donor_motion_repair.json`.

- Initial one-shot model response: correctly withheld authorization, but requested **zero** tools. This is not evidence of tool-using intelligence.
- Stricter first attempt: model prematurely finished and failed the mandatory-inspection protocol, safely held.
- With protocol feedback: Copilot **requested both `source_graph` and `engineering_checks`**. HS returned both. The final model response failed (operator error), so investigation was **incomplete** and remained HOLD. Blocking HS findings were `analysis-current-margin` and `analysis-actuator-torque`; source conflict `motor_stall_current` was blocking. No verified physical measurements or release were recorded.

This is a genuine two-step read-only tool-invocation proof, not a successful end-to-end autonomous engineering review. The live partial trace is stored under `/tmp/hs_operator_investigation_live_v3_20261020.json` on Optiplex, not committed. Unit tests cover completed investigations with simulated operators and fail-closed behavior.

## Next

Make response/error telemetry explicit (without recording account secrets), include actual source-content snapshots with hashes, and build a rigorous model-vs-deterministic engineering benchmark where valid and unsafe hypotheses both appear. Read-only tool access is a precursor to agent reasoning, not proof of engineering correctness.
