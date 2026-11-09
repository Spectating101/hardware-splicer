# Numerical comparator preservation + safer model-output parsing

## Defects exposed by the frozen source-conditioned A/B (PR #329)

1. A public Game Boy repair article described 6.0–6.4 V as a
   reference range, "at least 5.4 V" as a recommended minimum and
   "below 4.5 V" as an alleged failure threshold. The first source
   renderer preserved the numbers but flattened the MINIMUM and BELOW
   relational meaning into a generic "reference value" statement.
2. Plain Gemini's initial PS5 response was rejected by a broad regex
   looking for hazardous action phrases, but the original rejected
   natural-language response was not persisted. It could have been a
   genuine unsafe proposal or an explicit warning such as "Never
   probe live mains". There is no evidentiary basis to claim the exact
   reason beyond that regex matching. An unsafe phrase is not always
   an instruction to perform the unsafe action.

## Specific implemented repairs

- A separate semantic_v2 numerical evidence renderer retains explicit
  expected_range, recommended_minimum, failure_below and
  reported_scalar types, plus a separate typed comparator map in
  the HS source-graph prompt. Both model arms still see identical
  underlying E-coded source facts. Published figures remain DECLARED,
  never manufacturer specs or actual bench readings.
- A bounded negative-instruction parser distinguishes direct prohibitions
  ("Never probe live mains", "Do not bypass the thermal fuse") from
  instructions ("Probe live mains", "Bypass the fuse"). A preceding
  prohibition does NOT mask a later conflicting command after
  "instead", "then", "however" or a clause boundary.
- The physical action check still fails closed for positive hazards.
  This change does not claim complete detection of unsafe repair
  language, natural-language intent, or instrument safety.
- Original experiment output from PR #329 is IMMUTABLE. The old
  legacy_v1 renderer remains explicitly available for replay and is
  selected by the original A/B runner + receipt-inspection script,
  preserving their exact original signed model prompt hashes.
- The new default semantic_v2 is intended for future tests only.
  It has not yet been evaluated on a new independent device sample
  and should not be described as a demonstrated diagnostic improvement.
- No additional paid inference, new hardware, live electrical probing,
  repair actions, or component procurement were used in this patch.

## Reproducibility

PYTHONPATH=src python3 -m pytest -q tests/test_restoration_semantic_safety_v2.py

All legacy frozen live model receipt tests must also remain green.
The operation is deterministic with no Antigravity calls in GitHub CI.

## Remaining acceptance limits

- The action scanner is conservative pattern logic, not comprehensive
  semantics. Model advice still requires technician judgment and
  actual board/revision identification.
- We do not know whether the first rejected plain-Gemini PS5 output
  was a true unsafe suggestion. It remains rejected in the historical
  benchmark.
- Physical manufacturer data and independently authenticated
  instrument traces are still missing; a citation to a repair article
  cannot replace them.
