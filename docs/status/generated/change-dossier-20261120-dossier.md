# Engineering change dossier: digital-ad6d77eab00448cd9eb3c07e2691ddeb

Edition `e4c64c1113d79581` · case `fielddeck-5` · evidence level **modeled** · physical authority granted: **no**

## Decision under review

Should revision 2 replace revision 1 under policy portable-runtime-4h 1.0.0?

Not decided by this dossier. Revision 2 has 1 failing modeled check(s) and no physical evidence.

## Revisions

| | Revision | Run | Snapshot | Package | Requirements met |
|---|---:|---|---|---|---|
| base | 1 | `6d65be486885` | `e3fe20fc51cf` | `a9a0c1aac9c3` | yes (modeled) |
| candidate | 2 | `df70f6a5008b` | `dfa3a253f6fc` | `9f05656fe028` | no |

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
| base_export | `r1-export.json` | `df3cbb1ceffb6a8de1fd53010e68472ce68af33aed817f9533682d86d8d963f6` |
| base_review | `r1-review/review.json` | `fb8d50bfccbfcc5d07293768b812e4fad64788b5ac2a5c3f2d1361aedddf5101` |
| candidate_export | `r2-export.json` | `634a91e17cacc190075593339cafa7126aaf3b843e04181c44d5d1a22be2f861` |
| candidate_review | `r2-review/review.json` | `5e0bf55b05c4d7f60e5ce2d079b674dc45dc8706a83c95909e81053b022aff39` |
| proposal | `proposal.json` | `01984116c31b51653b83ee398e145bfaacf8e14ca39d9e15193d1b22bf9063cc` |

Receiver checks performed:

- every covered file's bytes match its recorded SHA-256
- base and candidate exports match the packet's project, revision, run, package hash, requirements and checks
- the Policy Lab review binds the exact base export bytes
- the HS proposal binds that review, and the candidate carries its resolved requirements
- every failing candidate check from the export is listed as unresolved
- each applied modelled candidate matches its review row, and its native outcome matches the candidate export
