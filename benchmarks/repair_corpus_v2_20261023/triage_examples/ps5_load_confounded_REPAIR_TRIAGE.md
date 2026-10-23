# Hardware Splicer — physical repair triage

**Status: PROPOSED INVESTIGATION ONLY. NOT A VERIFIED REPAIR.**

**Device (declared):** PlayStation 5
**Fault assessment:** insufficient_discriminating_evidence
**Insufficient evidence reason:** operating_condition_confounded

## Source symptoms

- After fitting aftermarket PSU, console overheats/shuts down when playing games; cleaning fan and reseating a missing EMI piece did not resolve it.

## Evidence-quality audit

- Independent component routes declared: 1
- Observation count: 2
- Condition-confounded routes: 1
- Supported component discrimination: NO

## Unverified component hypotheses

No component ranked. Collect discriminating evidence instead of guessing.

## Proposed next observations — operator review required

1. **record_operating_condition_delta** — Separate load/temperature/time effects from actual component-path changes.
   - Evidence to collect: Review existing operator/service logs for load, time, thermal conditions and supply readings under each reported pass/fail state; confirm actual component path identity before proposing a replacement. Do not energize unknown equipment for this test.
   - What it might distinguish: If path remains identical, isolate a state-dependent mechanism; no individual component has been causally identified.
2. **independent_component_substitution** — Test a real source/path variation, not just a different load label.
   - Evidence to collect: Identify a previously performed, safely documented known-good substitution or manufacturer diagnostic that changes one path element while keeping operating conditions comparable.
   - What it might distinguish: If the originally failing behavior disappears only with the known-good path, that element becomes a stronger candidate.

## Release and safety restrictions

- Physical repair verified: **NO**
- Power-on, fabrication, disassembly or operational authority granted: **NO**
- Path membership, service-cost tiers and test reports are ...[truncated]