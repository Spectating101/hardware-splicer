# HS Recovery / Restoration — YouTube-Based Differential Diagnosis Pilot

**Date:** 2026-11-10. **Status:** retrospective repair triage research; no video frames consumed, no device fixed, no parts bought.

## What “recovery” actually means inside HS

The goal is NOT to watch a restoration video, copy the final repair, and call that a solved engineering problem.

The legitimate process is:

1. **Intake** — record the device, failure symptoms, conditions, known-damaged subsystems, and actual observations. This invokes HS's native `repair_intake` normalization, so notes are not arbitrary human prose in the downstream workflow.
2. **Differential** — rank plausible fault mechanisms *without* accessing the video creator's eventual solution. The rule-based diagnostic baseline uses evidence codes and returns at most three hypotheses, each with confirmatory tests. It does not output a guessed replacement PCB.
3. **Measured branch** — obtain actual independent observations: contact voltage/continuity, connector visual evidence, charging input path, verified disc mechanism, etc. These measurements change the rank. A hypothesis without physical confirmation does NOT authorize hot air, conductive bridging, Li-ion repair or part purchases.
4. **Repair (future)** — perform a validated, safe intervention for that specific verified defect, using proper specialist tools when appropriate. **None was performed here.**
5. **Post-repair acceptance (future)** — confirm restored function, no shorts/unsafe power, reliable use, correct parts, and separate cosmetic restoration. There is no video-based substitute for tests on the real device.

### Cases retrieved from YouTube descriptions

| Case | Published creator/video | Initial user-facing symptom | Creator-reported eventual outcome |
|---|---|---|---|
| Game Boy Color, 2020 | [Odd Tinkering — $2 junk GBC](https://www.youtube.com/watch?v=2BmGMi0IEx4) | no power, corroded contacts, damaged LCD appearance | broken battery-to-board connection bridged; screen polarizer separately restored |
| Original Game Boy, 2016 | [Retro Sales — DMG no power](https://www.youtube.com/watch?v=mMjNzPR7nVE) | no power, battery-contact corrosion | battery-contact corrosion/power fix is described, but detailed electrical verification unavailable |
| Nintendo Switch, 2024 | [Odd Tinkering — no power](https://www.youtube.com/watch?v=0HZSA8nZd_k) | dead/no charging response via USB-C | visibly damaged USB-C charging port replaced; scratched digitizer separately replaced |
| PS2 Slim, 2021 | [Odd Tinkering — $7 junk PS2](https://www.youtube.com/watch?v=8hGGVW_mGEI) | boots but fails to read game discs | optical drive/laser replacement followed by mechanical adjustment |

**Provenance limitation:** Source evidence comes from the author-provided YouTube descriptions/public search records, not a full video stream, timestamped still-image analysis, transcript, instrument logs or independent repair. The DMG case has especially weak outcome detail. Each creator-reported fix is a label, not a proven independently measured ground truth.

### Actual pilot result

- **4 cases** prepared as two-stage structured observations and a separately stored answer record.
- At *initial* symptom stage the generic HS triage ranks the eventual reported fault **#1 in 3/4**, and within its top three in **4/4**.
- After additional observations (only where described by creator), the eventual fault is ranked **#1 in 4/4**.
- The key differentiation is the two corroded Game Boys: identical initial appearance can mean either actual contact failure or **an open power trace**, so HS must demand battery-path continuity evidence before selecting invasive copper rework.
- **All repair actions are conditional and blocked** until independently verified. The program does not authorize batteries, powered tests, lasers with interlocks defeated, hot air on charging ports, or fabricating arbitrary replacement boards.
- **This is not an independent blind test.** The taxonomy and some symptom coding were hand-authored after reading the published outcomes, creating clear selection and design bias. The algorithm reads cases without gold results, but the *researcher* had already seen gold. **No claim of AI autonomous video reasoning or generalization is justified.**

The result is useful because it gives HS a source-linked, inspectable *repair-intake-to-diagnostic-tree* API and a benchmark methodology that is not fooled into declaring a finished repair.

### Inspectable artifacts

- [Blind symptom fixtures](cases/) — each is a typed `repair_intake` plus observable codes; no final repair.
- [Held-out creator outcome descriptions](hidden_outcomes/) — separate test-only records; the triage module cannot read these.
- [Two-stage predicted tests/hypotheses](evidence/blind_predictions.json).
- [Creator-outcome comparison](evidence/evaluation.json).
- `src/hardware_splicer/restoration_video_triage.py` — small deterministic differential/measurement planner, not an LLM.
- `tests/test_restoration_video_bench.py` — evidence separation, adversarial input, two similar Game Boys, deterministic replay, and safety gates.

### Reproduce on Optiplex

```bash
python3 examples/restoration_video_bench/make_cases.py

# Run on *symptom-only* intake; never touches held-out creator outcomes:
PYTHONPATH=src python3 -m hardware_splicer.restoration_video_triage \
  --case examples/restoration_video_bench/cases/gbc_2020_broken_power_path.json \
  --stage initial --out /tmp/hs_gbc_initial.json

# Retrospective harness first writes predictions and ONLY THEN loads outcome files:
PYTHONPATH=src python3 examples/restoration_video_bench/run_trial.py

PYTHONPATH=src python3 -m pytest -q tests/test_restoration_video_bench.py
```

### Most important next step

Do NOT tune the rule engine further against the four cases until it scores perfectly—it's already fitted to the examples. Find genuinely *unseen* cases with independently verifiable repair observations, gather timestamped screenshots/schematics if usage permits, and have an HS agent produce a written diagnostic plan **before** a reviewer opens the actual repair. Ideally use a technician or hardware fixture for independent voltage/continuity evidence and final bench acceptance.

To establish commercial/research value, compare the repair success rate, diagnostic time, cost, false positive part replacement, and evidence provenance against (a) plain search + manual reasoning, and (b) an ordinary AI assistant, on a fresh set of devices.
