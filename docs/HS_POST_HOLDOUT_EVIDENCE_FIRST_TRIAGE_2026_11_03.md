# HS evidence-first repair triage — post-holdout development changes

**Status: development regression, NOT new out-of-sample diagnostic accuracy.**
Original evaluation: PR #268, immutable corpus blob b2441fb0fbdeb594e33a4f8f01deda25b3b3096a, original engine eb60037fb16e4b3696c4ad8197e5202606855caf.

## Why we changed the software

The first untouched 7-case/14-checkpoint evaluation got **6/8** predeclared exact product-class comparisons, **6/6** predeclared broad diagnostic-family comparisons and **14/14** weak keyword occurrences. Those numbers do **not** demonstrate correct component diagnosis or repair success. The report showed a no-power diagnosis on an audio-only Game Boy Color, motor-driver hypotheses on non-lifting drones, two wrong laptop market classifications, and no fault candidates on the jammed printer. Five of seven public story owners did not confirm complete repairs. No hardware was repaired or operated by HS.

The next software change is *not* a claim that HS can now fix those devices*. It adds an evidence-first differential and refuses a repair-ready verdict where a hypothesis remains unverified.

## Development implementation

- A centralized, product-intake-only contradiction layer distinguishes **audio-only failure with working headphone audio**, **reported missing external laptop charger voltage**, **motor spin without drone lift**, **printer carriage mechanical jam**, and **charge-port flex failures dependent on final assembly**.
- Product identity is prioritized from the explicit device hint (e.g. a non-Mac laptop) rather than commercial market score or loose symptom overlap.
- The fault ranking is explicitly an **uncalibrated heuristic**, not a confidence interval or actual root-cause posterior. Each tailored hypothesis requires model-specific observations or physical measurements and sets repair_ready=false, hypothesis_verified=false.
- Original generic power tests and parts-replacement playbooks are suppressed while an unresolved differential is being investigated. Mains printer and drone routes explicitly reject live-carriage, flight, spin, and unguarded powered tests.
- RepairCaseEvaluator propagates triage_state and refuses solvable_now for these evidence-missing cases, regardless of commercial coverage or task-count score.
- Existing generic and original model-specific routes are retained except where evidence conflicts.

## Testing and independence

Run python -m scripts.verify_hs_evidence_first_differential_001. Its synthetic fixtures are *development tests*, not independently held-out cases. The new CI job also checks that the #268 source case blob and original holdout benchmark/verification files remain untouched.

**Do not** re-run these seven cases under changed code and present improved numbers as fresh generalization. A new, separately frozen selection of previously unused source records and, ultimately, real hardware measurements are required to validate this change.

## Remaining issues

1. No board photo, recorded multimeter values, original verified service repair or complete functional test entered this implementation.
2. The public source narratives can contain bias, missing follow-up, and incorrect owner hypotheses.
3. Mechanical drones, printers, and speaker audio still require broader domain coverage, parts/service documentation, and qualified bench procedures.
4. Independence and calibration of any apparent diagnostic accuracy require a fresh pre-registered holdout with masked interventions and explicit unknown-cause categories.

No autonomous battery power, drone flight, energizing jammed equipment, board-level rework, physical repair approval, product certification, or resale claim is authorized.
