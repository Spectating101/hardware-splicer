# Adaptive diagnostic simulation benchmark

This evaluation exercises a bounded sequence of **model test selection → hidden synthetic observation → hypothesis elimination → model decision to continue or stop**. The model sees the scenario, candidate tests and its own prior simulated observations, but not the hidden fault or the full outcome table. HS controls the synthetic observation lookup and removes inconsistent hypotheses. Only predeclared low-risk simulated inspections are accepted, and model-claimed real measurements are rejected.

## Repeat on Optiplex

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_adaptive_diagnosis.py
PYTHONPATH=src .venv/bin/python scripts/run_adaptive_diagnosis.py
PYTHONPATH=src .venv/bin/python scripts/run_adaptive_diagnosis.py --case-id printer_layer_shift --hidden-fault belt_slack
```

The Copilot adapter is **replaceable** by any callable accepting a prompt and returning a JSON mapping. Outputs are stored under `/tmp`. A successful simulation never grants power-on, motion, fabrication, physical testing or release authority.

## Live Optiplex results, 2026-10-20

- `rover_brownout`, hidden `connector_drop`: first attempt made a correct initial test selection but requested an invalid second test; safely failed. After tightening the stop-condition prompt, Copilot selected archived voltage/reset correlation, received synthetic `intermittent_open_spike` and stopped with `connector_drop`. Completed.
- `printer_layer_shift`, hidden `belt_slack`: selected unpowered mechanical inspection, received synthetic `belt_loose`, stopped with `belt_slack`. Completed.

**2/2 completed on the revised protocol.** Both final conclusions are correct *under these authored deterministic synthetic oracles*. This is not independent diagnosis accuracy, not an evaluation against real hardware measurements, and not a proof that the assumed tests actually distinguish those faults in the field. Neither case requires multiple successive inspections. A later benchmark should add ambiguous outcomes, noisy tests, finite diagnostic cost, genuinely held-out evidence and review of model calibration when multiple hypotheses remain.
