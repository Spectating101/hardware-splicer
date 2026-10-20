# Bounded engineering hypothesis cycle

`hardware_splicer.operator_hypothesis_cycle.investigate_hypotheses` is provider-neutral: a callable operator proposes 2–5 competing explanations and discriminating tests, receives an independent HS critique, and returns a revised set. HS computes analysis and source conflicts without trusting the model to create measurement evidence.

## Live Optiplex run — October 20, 2026

Input: `eval/source_agnostic_pilot/public_drv8833_donor_motion_repair.json`. Provider: configured `copilot-spectator26` wrapper. First response: four hypotheses. Second response: five revised hypotheses. The revision distinguished torque insufficiency from friction/binding, while preserving motor-current and controller-compatibility concerns. HS blockers: `analysis-current-margin`, `analysis-actuator-torque`, and unresolved source conflict `motor_stall_current`. Final decision HOLD; zero physical tests executed. Local output: `/tmp/hs_hypothesis_cycle_live_20261020.json` on Optiplex, not committed.

This proves a model response to engineering feedback, not independent hypothesis accuracy or tool execution. Predicted observations remain hypothetical, not measured evidence. The operator has no release, shell, file, instrument, or motion authority. Physical diagnostic procedures require separate review and appropriate safeguards before anyone performs them.

## Regression

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_operator_hypothesis_cycle.py
```

Next: score whether tests actually distinguish hypotheses; use blinded reference cases, numerical invariants, independent technical reviews and a stricter separation between safe offline examination and physical-test proposals.
