# Engineering change dossier: digital-278ce63f5bb5427795e172920cefa95b

Edition `ba12b22711425655` · case `fielddeck-5` · evidence level **modeled** · physical authority granted: **no**

## Decision under review

Should revision 2 replace revision 1 under policy portable-runtime-4h 1.0.0?

Not decided by this dossier. Revision 2 has 1 failing modeled check(s) and no physical evidence.

## Revisions

| | Revision | Run | Snapshot | Package | Requirements met |
|---|---:|---|---|---|---|
| base | 1 | `765e60c3a0b2` | `403d4a4b4e29` | `c8352f6c9a15` | yes (modeled) |
| candidate | 2 | `22f91786d726` | `f368826ad623` | `7e53b5f7385b` | no |

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
| base_export | `r1-export.json` | `dbb752ec7360981cb19e5b2fc8265588b0ce1d8f0dfab22b8d5980b555ec92c2` |
| base_review | `r1-review/review.json` | `5f6f18eb75d0d302a0a9cfe5cb32a229d17ebb13bc254b7e8c62ebb99475a6d0` |
| candidate_export | `r2-export.json` | `6ca25453faa1cd29a7f97a44a2665f82ab0f9c7900665b5383e1e3797df43371` |
| candidate_review | `r2-review/review.json` | `862fcbc8685abca98bd3307ed9564c86abb361acec30005b2dfeaf79dab22221` |
| proposal | `proposal.json` | `9099777ed1fd2ad954166eb056c67213d670321fcf63e18ac86b808c05b4fef0` |

Receiver checks performed:

- every covered file's bytes match its recorded SHA-256
- base and candidate exports match the packet's project, revision, run, package hash, requirements and checks
- the Policy Lab review binds the exact base export bytes
- the HS proposal binds that review, and the candidate carries its resolved requirements
- every failing candidate check from the export is listed as unresolved
