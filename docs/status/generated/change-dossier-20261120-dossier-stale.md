# Engineering change dossier: digital-9fa33a1ccc9c4c4aa677de4bcbb84317

Edition `7e2edb6b950a2c25` · case `fielddeck-5` · evidence level **modeled** · physical authority granted: **no**

> **STALE EDITION.** HS project is at revision 3; this edition describes revision 2 run_id changed from 73a17dbce2414d46883a61f8dd974ced to 78ea06aa03b241fe921cb102a8423442 package_sha256 changed from b630c5ded559584a91c57211db0f8263bc2e6ba49ea20b26b2fc83927b1b688b to 7234517b8267886f0b6ed7a69b027fbf61061187e97bf9b2456c3fd5038f737c snapshot_sha256 (declared by HS) changed from d2ecf433e7ba5b6b80da8c667b141347fc125486f9b57ba3071f337b5e816451 to b06b165100d1cf1ae65ed38e5aa39fe38fa6583e4f20ac20ad792c872d39c872 seal_sha256 (declared by HS) changed from 50c6b86ae6597ce2a70dce4842933a02b618d596ca1c42a9a8e016779c7957c7 to 61c8e4d525dfffe42e05f92a719e52b3f98d675389b38d77826cf2f62108c996 Do not reuse this dossier.

## Decision under review

Should revision 2 replace revision 1 under policy portable-runtime-4h 1.0.0?

Not decided by this dossier. Revision 2 has 1 failing and 0 untested modeled check(s) and no physical evidence.

## Revisions

| | Revision | Run | Package | Requirements met | Snapshot / seal (declared by HS, not verified by Cite) |
|---|---:|---|---|---|---|
| base | 1 | `d5d2aa184887` | `e9c99154500a` | yes (modeled) | `36178ffeae03` / `248a09784317` |
| candidate | 2 | `73a17dbce241` | `b630c5ded559` | no | `d2ecf433e7ba` / `50c6b86ae659` |

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
| base_export | `r1-export.json` | `91272ded76ee6dc7ea682f19167c74dd0d1f43d5e109588168978db71628f776` |
| base_review | `r1-review/review.json` | `10230b9120c5736f87cd00800e52cfc78857fc2fbfa67b22c1bca8fe891a4577` |
| base_review_replay | `r1-review/replay.json` | `e2f70e0e1c2903e736726252ef910031136cbdd51934e0f3b71171329ef29427` |
| candidate_export | `r2-export.json` | `f3050ab7eb3f0b93c85b639336630aa5aeed8d6c24006cc3eb02bff1ccdef0c6` |
| candidate_review | `r2-review/review.json` | `16cb6d662fedb1558879a86cf7a2bc60e8ac22773d300c99d367c4f3e0ee5bc6` |
| candidate_review_replay | `r2-review/replay.json` | `a824b9bdc4bfba5a36a9521c559d9cd4271b4c5d60843e9cb64f2ed86e3055c8` |
| proposal | `proposal.json` | `deb21e3dc1bee2f3e586f5c69e7580bda1e2bb4cae0e6cedc48808a75cfb253c` |

Receiver checks performed:

- every covered file's bytes match its recorded SHA-256
- base and candidate exports match the packet's project, revision, run, package hash, requirements, requirements_met and checks
- each Policy Lab review has a verify receipt naming its exact bytes
- the proposal shown (policy, decision, unmet targets, requirement changes) is read from the covered files
- the Policy Lab review binds the exact base export bytes
- the HS proposal binds that review, and the candidate carries its resolved requirements
- every failing candidate check from the export is listed as unresolved
- each applied modelled candidate matches its review row, and its native outcome matches the candidate export
