# Diagnostic discrimination: blinded synthetic pilot

This benchmark scores which *proposed offline inspection* is likely to separate
competing hardware faults. The test choice is scored on a synthetic conditional
outcome table using uniform-prior information gain. Unsafe actions are rejected
regardless of any claimed information gain. The case seen by the model includes
only the problem, hypotheses, and available test descriptions; the oracle matrix
and best-test identities are withheld by `public_case_prompt`.

## Scope and formula

For a deterministic outcome table, test information gain = prior entropy of
hypotheses minus expected posterior entropy after the test. Three perfectly
separated equal-prior hypotheses yield approximately 1.585 bits. Partial splits
receive proportionally less credit; irrelevant tests yield zero. These outcome
matrices are **synthetic assumptions**, not manufacturer or empirical fault
statistics. They do not validate the real-world diagnostic power of a test.

The primary result `passed` means that the operator selected a listed safe
inspection attaining the highest gain in the **scenario's hypothetical oracle**.
The auxiliary `predicted_outcome_accuracy` is reported separately only when
the operator supplies a mapping of hypothesis to canonical outcome codes; it is
zero/unevaluated for natural-language-only responses. It is not an accuracy
percentage for real engineering predictions.

## Running on Optiplex

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_hypothesis_discrimination.py
PYTHONPATH=src .venv/bin/python scripts/run_discrimination_operator.py
```

The live script invokes a replaceable read-only operator through the existing
Copilot adapter; neither the agent nor HS operates hardware or writes files.
Operator transcripts and output stay under `/tmp` and are not committed.

## Initial live run, October 20, 2026

The `copilot-spectator26` wrapper selected the maximum-gain safe inspection in
**5 of 5** synthetic scenarios (three initial easy cases and two harder cases
with partially discriminating safe alternatives). No physical tests were run,
and the model did not claim measurements. This is a narrow test-selection
benchmark: the cases are authored, oracle partitions are idealized, and several
inspectability assumptions are deliberately favorable. A correct choice here
does not prove actual electronic fault identification or autonomous engineering.

Future versions should require independent evidence-backed fault cases,
uncertainty over test reliability, expected testing cost, real negative controls,
source hashes, calibrated confidence, and distinction between partial and
conclusive diagnosis. Do not promote model-selected tests to physical-action
permission or treat an unpowered inspection as proof of a hidden defect.
