# Hardware Splicer: independent adversarial acceptance audit

Date: 2026-10-20. The operator challenged the prior PR #153 passing tests
as sufficient evidence of engineering capability. This audit deliberately
attempts to falsify the code's claimed software behavior, including
contradictory summaries and intentionally broken code variants.

## Negative results reproduced against original PR #153

1. **Forged completion events:** synthetic motion-complete and barcode-scan
   messages incremented the virtual completed_count with no hardware.
   These messages were never authenticated sensor/actuator evidence.
2. **Barcode replay:** repeating one barcode in two synthetic cycles
   incremented the counter twice. In a real machine distinct item
   identities need independent observations. Legitimate physical items
   can have matching codes; rejecting identical barcode text alone
   would not solve the issue.
3. **Reset during motion:** reset while indexing returned directly to
   ready, without proven motion cessation. Fixed in the virtual model.
4. **No autonomous timeout:** after 100 unrelated events without external
   timeout delivery, indexing remained active. A bounded *synthetic
   tick* budget has now been added. It does NOT represent a trusted
   clock or a physical stop circuit.
5. **False-green evaluator:** an injected report claimed 0 successful
   scenarios but also advertised software_reference_logic_passed=true.
   The prior evaluator accepted it. Another report contained recorded
   violations alongside passed=true, and was accepted.
6. **Source redirect policy:** the public-source observer checked its
   final URL after urllib's automatic redirect-following. This could
   fetch an unapproved destination before the check. A no-redirect
   handler now refuses the request before following any redirect.

These are observed counterexamples, not conclusions inferred from
passing regression tests.

## Independently evaluated after changes

A separate module defines acceptance rules outside the original
scenario-runner's pass/fail flags, recomputes expected counts and
trace-level properties, checks event continuity, premature completions,
stop handling, and refusal to claim physical operations.

A fresh Optiplex execution verified:
- 10 of 10 targeted software simulations passed.
- 11,110 bounded synthetic event sequences were checked, covering
  43,210 virtual transitions. No specified software invariant was
  violated within this bounded sequence set.
- Four deliberately introduced code faults were independently detected:
  ignoring stop, ignoring virtual ticks, clearing active motion via
  reset, and counting an out-of-order barcode.
- Two contradictory or fabricated passing reports were rejected.
- A separate deterministic randomized event test exercised additional
  event orderings outside the original example scenarios.
- Seven allowlisted public source pages were re-observed using the
  updated redirect behavior.
- Focused regression suite: 173 passed, 1 skipped, 1 warning.

These tests support only the precise synthetic and adversarial
assertions described. Four of four mutation detections do not
establish that the oracle catches every possible regression.
Tests with finite depth do not establish liveness under all timings.

## Three unresolved physical-operation blockers

**HIGH: unauthenticated motion and scanner events.** The abstract state
machine accepts event messages that are not independently linked to
real physical observation. A synthetic completion is not evidence that
an object moved, or a barcode was read by a working device.

**MEDIUM: no independent item identity.** A duplicate code can count
as an additional virtual cycle without a verified new physical item
or real item-presence observation.

**HIGH: no independently enforced elapsed-time or hardware watchdog.**
The eight-tick software limit is effective only if the simulation or a
future external source delivers the tick events. A stopped/hung agent
can fail to deliver ticks. A real machine requires independent fail-safe
motion/power behavior and safety engineering.

The general hardware blockers remain:
- No physical scanner from a listing verified or repaired.
- No motor type, current, winding, travel, limit switch, dimensions or
  actual mechanical assembly established from a damaged printer.
- No verified power, driver rating, PCB-to-donor interface or
  independent hardware safety stop.
- No actual assembled new product, bench validation, or production
  process completion.

## Acceptance verdict

Software controller bounded invariants: supported for the specified
synthetic test scope.

Independent report integrity: improved; tested contradictions rejected.

Physical data/event provenance: not established.

Physical electrical and motion functionality: not established.

Repair original device: not demonstrated.

New spliced product: not demonstrated.

**Release authorization for physical control: BLOCKED.**

Reproduce the independent mutation and adversarial audit:

    PYTHONPATH=src python -m scripts.run_independent_splice_redteam --out /tmp/hs-redteam.json

Machine-readable audit:
INDEPENDENT_HS_ADVERSARIAL_AUDIT_2026-10-20.json.

No hardware was purchased, powered, manipulated, or made available for
manual inspection in this exercise.
