# Engineering change dossier: digital-996558719b13454fb1724bef8f218093

Edition `2075bf9f3479df23` · case `fielddeck-5` · evidence level **modeled** · physical authority granted: **no**

## Decision under review

Should revision 2 replace revision 1 under policy portable-runtime-4h 1.0.0?

Not decided by this dossier. Revision 2 has 1 failing and 0 untested modeled check(s) and no physical evidence.

## Revisions

| | Revision | Run | Package | Requirements met | Snapshot / seal (declared by HS, not verified by Cite) |
|---|---:|---|---|---|---|
| base | 1 | `09a597a3bd07` | `f505c76f745d` | yes (modeled) | `ec875bac0319` / `97086c9925f6` |
| candidate | 2 | `597107a7c64a` | `d4652acd9d8e` | no | `4278906014be` / `33dc96f410b5` |

Revision 2 change request: Apply Policy Lab portable-runtime-4h proposal

## Proposal

Policy Lab policy `portable-runtime-4h` 1.0.0 returned **BLOCKED** on revision 1.

- Unmet target `work-runtime`: metric.work_runtime_lower_h = 3.166, required >= 4 h
- Proposed `minimum_work_runtime_h`: 2.5 → 4.0

## Checks

| Check | Revision 2 result | Revision 1 result | Earlier result status |
|---|---|---|---|
| work_runtime | **FAIL** 3.166 h against limit 4.0 h | pass (modeled) 3.166 h against limit 2.5 h | stale (revision 1 result no longer counts) |
| ordinary_source_margin | **pass (modeled)** 0.48 A against limit 0.3 A | pass (modeled) 0.48 A against limit 0.3 A | retained (inputs unchanged, rerun matches) |
| high_keyboard_supply_limit | **pass (modeled)** 0.08 A against limit 0 A | pass (modeled) 0.08 A against limit 0 A | retained (inputs unchanged, rerun matches) |

## Candidate policy review

Policy `portable-runtime-4h` on revision 2: **BLOCKED** (unmet: engineering.work_runtime, work-runtime)

## Unresolved

- FAILING check `work_runtime` in revision 2: 3.166 h against limit 4.0 h (regressed)
- Policy target `engineering.work_runtime` unmet in revision 2: HS engineering check = 3.166, required HS limit 4 h
- Policy target `work-runtime` unmet in revision 2: metric.work_runtime_lower_h = 3.166, required >= 4 h

## Not tested

- No physical build, bench measurement, power-on or field operation was performed for either revision.
- Modeled runtime and current values are calculations from declared assumptions, not observed behaviour.

## Not linked

- Nothing reported.

## Sources

| Role | File | SHA-256 |
|---|---|---|
| base_export | `r1-export.json` | `76d039ef0ac6ed4caed5c4c3a2069fb9e2f90404d9bc473629f4c4da13bb4435` |
| base_review | `r1-review/review.json` | `aa435840af09a331002c5cd1bab06cb80515869362f9214ac17281ad03193a3a` |
| base_review_replay | `r1-review/replay.json` | `5b1f125d154f47c273624c627fd241f20de7934953d4eec89feb72b659e7d7fd` |
| candidate_export | `r2-export.json` | `d1a5fa318d4013f11b534eb02634b7c4a6a675a3d7d307724a2758063ddd595d` |
| candidate_review | `r2-review/review.json` | `40db9c451262c1aa2af578dfe7eb4ca9e5aae2b3fadd3309a7e4608c7486c79b` |
| candidate_review_replay | `r2-review/replay.json` | `c61be06794111dd6e812396ad7a115f356f3b3437e8db06c52f0f14fa0b792cb` |
| proposal | `proposal.json` | `a790892955e158792b85c82fe2e5b7c1d6f73cacf76c45f09500a6d86c767592` |

Receiver checks performed:

- every covered file's bytes match its recorded SHA-256
- base and candidate exports match the packet's project, revision, run, package hash, requirements, requirements_met and checks
- each Policy Lab review has a verify receipt naming its exact bytes
- the proposal shown (policy, decision, unmet targets, requirement changes) is read from the covered files
- the Policy Lab review binds the exact base export bytes
- the HS proposal binds that review, and the candidate carries its resolved requirements
- every failing candidate check from the export is listed as unresolved
- each applied modelled candidate matches its review row, and its native outcome matches the candidate export
