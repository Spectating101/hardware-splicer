# HS repair challenge 01 — public cases, sealed-outcome evaluation

**Status:** Executed exploratory software benchmark, **not** a professionally reviewed diagnostic product and **not** physical repair. Date: 2026-10-23.

This is the first effort to test Hardware Splicer on a documented field repair, separate from its previous repair of failed *software previews*. The prior `repair_intake.py` recorded symptoms and device context but did not rank candidate failed components. The new `repair_path_diagnostics.py` uses route-based working/failing observations and ineffective intervention outcomes to prioritize *hypotheses*, and exposes them through optional `repair_intake.path_evidence` to HS's original intake pipeline.

## Reference evidence and certainty

1. **Case A (one poster-confirmed fix).** MacBook Pro 13-inch Mid 2012, original Toshiba disk recognized, replacement Kingston SATA III SSD and another Hitachi HDD not recognized internally. After the original question, the response says a SATA-cable replacement restored function. The input carries the pre-repair differences, **never the answer or fix**. [Owner's original iFixit repair thread](https://www.ifixit.com/Answers/View/155102/SSD+not+recognized+in+system). Ref: 2013 question, 2015 reported fix.
2. **Case B (uncertain reference).** MacBook Pro 15-inch, internal boot fails with a question-mark folder; the same disk boots via USB. Two replacement cables failed to solve the original report. The chosen reply *suspects* logic-board/connector trouble. **No confirmed physical logic-board repair exists in the cited case**, so its evaluation is expert-hypothesis agreement, **not** a true known-root-cause result. [iFixit repair thread](https://www.ifixit.com/Answers/View/195252/Won't+recognize+the+hard+drive+(flashing+folder-question+mark)).
3. **Case C (synthetic negative control).** One disk fails via both independent USB and internal SATA paths while a known-good disk works internally. This was created to reject a hard-coded "replace cable" answer. It is **not a real repair**.
4. **Case D (underdetermined real symptom).** Joy-Con analogue drift without component-isolating tests. iFixit documents multiple possible causes, ranging from contamination to wear. A responsible system must request more evidence, not assert a root cause. [iFixit Joy-Con drift troubleshooting](https://www.ifixit.com/Troubleshooting/Joy-Con/Nintendo+Switch+Joy-Con+Drift/481780).

### Separation and execution

- `blind_cases.json` holds device model, supplied route components, observations and failed interventions, **not resolution or confirmed root-cause fields**.
- `sealed_evaluation.json` contains reference labels, context and classification of outcome quality.
- `run_blind_benchmark.py` imports the case observations and runs **all HS diagnostic functions first**, with no access to the label file. The label file opens only in the separate scoring phase.
- Baseline `extract_repair_context` delivers symptoms but **zero ranked physical fault hypotheses**. The new integrated `apply_repair_intake_context` returns `repair_path_diagnostic` when explicit `path_evidence` is provided. Existing plain symptom-only intake does **not** invent diagnosis.
- No model was queried; this is a **deterministic shared-path reasoning proof-of-concept**. The reasoning code knows no device names, vendor names, source URLs, known fixes, or ground truth.
- **Important experimental caveat:** The human benchmark author selected and encoded the cases while aware of reference outcomes. The scoring file is isolated from *program execution*, but these cases are not a randomized, fully held-out cohort. Structured path membership and ordinal service costs are manually supplied, not independently validated engineering measurements.

### Actual results

| Case | Current HS predicted first triage action | Reference | Responsible interpretation |
| --- | --- | --- | --- |
| A | Inspect/test internal storage flex interconnect | Poster changed the SATA cable and restored operation | **1 reference-confirmed fix matches first-ranked hypothesis**, but the cable and controller have tied path evidence; cable wins by reversible/cheaper investigation, **not unique causal proof** |
| B | Inspect board-side SATA port/path after two ineffective cable replacements | Expert suspects board / connector, no verified repaired state | **Expert opinion agreement only**; no confirmed correct root cause |
| C | Test the suspect drive independently | Synthetic failure of the disk across two paths | Synthetic negative-control success |
| D | Abstain and collect more path observations | One drift symptom cannot isolate dirt/wear/calibration | Appropriate evidence refusal |

**Measured benchmark score is NOT "4/4 real repairs fixed."** It consists of 1 source-confirmed matching repair recommendation, 1 unconfirmed expert comparison, 1 synthetic control and 1 justified abstention. Zero devices physically repaired, zero actual root cause verified by HS instrument readings, zero competitors run with the same input.

The engine deliberately uses ordinal triage evidence, not calibrated failure probabilities. Duplicate observations on identical path signatures cannot inflate failure support. A previously replaced component with unchanged behavior is deprioritized; a repeated failure never authorizes a costly board replacement without inspection. Successful repair outcomes are disallowed from blind inputs.

### Reproduce

From the repository root, after `pip install -e '.[dev]'`:

```bash
python benchmarks/real_repairs_20261023/run_blind_benchmark.py /tmp/hs_repair_01.json
pytest -q tests/test_repair_path_diagnostics.py
```

Program output includes all candidates and evidence scores, the baseline and the separate label evaluation. The focus regression suite covers the previously existing AI *software-preview* repair path to check we did not break it.

### What this cannot yet do

- Diagnose a device from unsupervised free-form descriptions, raw repair photos, PCB schematics, or unknown source topology. Someone must supply or extract the functional paths and substitution observations.
- Execute probes, electrical measurements, disassembly, component replacement, firmware changes or field repairs.
- Distinguish intermittent SATA signal-integrity defects from controller-port problems where available working/failing paths are equivalent. Case A is a **serviceability-tiebreak** outcome, not uniqueness.
- Prove how HS compares to iFixit troubleshooting, professional repair technicians, manufacturer diagnostics, or current AI competition.
- Claim any physical safety, equipment operation or release authority.

### Next competition gate

Use a **prospective unseen corpus** of independently annotated, actual repairs with confirmed post-repair operation and negative controls. Lock the diagnostic code, then run each case without the author's familiarity or manual cost tuning. Score correct top-1/top-3 fault category, cost of wrong replacements, number of additional measurements, justified abstentions, time-to-diagnosis and harm avoidance. Run at least one other diagnosis tool on identical evidence. Only then can we claim broad diagnostic competence or comparative superiority.

The longer-term HS workflow should join original symptom intake to measurements, part identification, external repair-source retrieval, a ranked investigation plan, safe human testing, and outcome confirmation. Existing AI-project failure-repair is a separate capability and is **not** the same as physical hardware fault diagnosis.
