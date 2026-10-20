# Engineering correctness benchmark — initial numerical/safety tranche

These six **synthetic, independently specified** adversarial cases exercise
current-limit margins, bounded battery-runtime arithmetic, and correctly
withheld decisions when measurements are missing. They score output values,
PASS/FAIL/UNKNOWN, and whether unknown or unsafe conditions block acceptance.
They also ensure no physical release is claimed.

Run from repository root:

```bash
.venv/bin/python scripts/run_engineering_verification_benchmark.py
.venv/bin/python -m pytest -q tests/test_engineering_verification_benchmark.py
```

**Scope restriction:** these checks exercise `engineering_analysis` and
`robot_topology`, not an LLM or real bench instrumentation. No evaluation
prompts, vendor facts, or answers are sent to an external model. Six checks
passing is not a measure of general electronics design competence.

These are formula cases: estimated runtime = energy (Wh) × usable fraction /
continuous load (W) × 60, and current margin = supply limit − peak draw.
The relevant margins are simplified declared-input models, not substitute
checks for battery chemistry, motor-driver thermal behavior, pulse peaks,
or wire/fuse ratings.

**Follow-on:** evaluate live model proposal quality independently of the
numerical authority gates, including unseen vendor schematics, netlists,
mechanical clearances, proposed tests, and safety abstentions. Model output
must never generate fictitious measured evidence or authorize power-on.
