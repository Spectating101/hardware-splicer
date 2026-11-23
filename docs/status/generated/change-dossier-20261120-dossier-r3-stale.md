# Engineering change dossier: digital-996558719b13454fb1724bef8f218093

Edition `d3e58c9a48049ea4` · case `fielddeck-5` · evidence level **modeled** · physical authority granted: **no**

> **STALE EDITION.** HS project is at revision 4; this edition describes revision 3 run_id changed from f35f80c0dfcb42e4b066906be52a919a to 0b05b3b8b1014fa88b8b45b75c33453b package_sha256 changed from 6591f122cea54fba525f451286596b1078317907391fbfc1e7e878fe66fadb2d to 5536cbe0883338558ab8ee9226e27ac74df0d46be49154cc98b2bd3febed39da snapshot_sha256 (declared by HS) changed from 5cbc24ce348e8cc355324823aacd640dc0ee4383ed29924b269c0aa3370e47ec to 9693acd83a2e8a3ac20cf03bd3d48777e35d69364df235479f671ce29ca9a543 seal_sha256 (declared by HS) changed from 90d2a4d1e24a288f72ca966563acf51f71713a18ce376eb918c1abdfeb00af30 to 539b448e8d9b45b22d183458b2d2afd6de78e818304a2e201a2707f5c387fbbd Do not reuse this dossier.

## Decision under review

Should revision 3 replace revision 2 under policy portable-runtime-4h-pi-load-candidate 1.0.0?

Not decided by this dossier. Revision 3 has 0 failing and 0 untested modeled check(s) and no physical evidence.

## Revisions

| | Revision | Run | Package | Requirements met | Snapshot / seal (declared by HS, not verified by Cite) |
|---|---:|---|---|---|---|
| base | 2 | `597107a7c64a` | `d4652acd9d8e` | no | `4278906014be` / `33dc96f410b5` |
| candidate | 3 | `f35f80c0dfcb` | `6591f122cea5` | yes (modeled) | `5cbc24ce348e` / `90d2a4d1e24a` |

Revision 3 change request: Apply Policy Lab modelled candidate pi-work-load-budget

## Proposal

Policy Lab policy `portable-runtime-4h-pi-load-candidate` 1.0.0 returned **BLOCKED** on revision 2.

- Unmet target `engineering.work_runtime`: HS engineering check = 3.166, required HS limit 4 h
- Unmet target `work-runtime`: metric.work_runtime_lower_h = 3.166, required >= 4 h
- Proposed `pi_work_current_a`: 1.0 → 0.697

### Modelled candidate design change `pi-work-load-budget`

- Input `pi_work_current_a`: 1 → 0.697 (model `runtime_inverse_to_work_power`).
- Formula: `E_min = (R - r/2) x (P - r/2); P_required = E_min / T; dI = (P + r/2 - P_required) / V; I_after = floor((I_before - dI) / step) x step`.
- Numbers: before = 1, export_resolution = 0.001, required_current_reduction_a = 0.302685, required_work_power_w = 5.737073, runtime_h = 3.166, supply_voltage_v = 5, target_h = 4, usable_energy_lower_bound_wh = 22.948292, work_power_w = 7.25.
- Assumption: Runtime is usable energy divided by work system power, and the adjusted input does not change usable energy.
- Assumption: Work power falls by 5 W for each ampere removed from pi_work_current_a (declared supply voltage).
- Assumption: Exported values are rounded to the declared resolution; the bound takes the least favourable rounding.
- Assumption: Other checks reading this input (for example source margin) are not predicted here; HS must rerun them.
- Physical means of reaching this load: **unknown / not tested**.
- Native rerun (revision 3): metric.work_runtime_lower_h = **4.002 h**, required >= 4 h: meets the target (modeled, not measured).

## Checks

| Check | Revision 3 result | Revision 2 result | Earlier result status |
|---|---|---|---|
| work_runtime | **pass (modeled)** 4.002 h against limit 4.0 h | FAIL 3.166 h against limit 4.0 h | stale (revision 2 result no longer counts) |
| ordinary_source_margin | **pass (modeled)** 0.48 A against limit 0.3 A | pass (modeled) 0.48 A against limit 0.3 A | stale (revision 2 result no longer counts) |
| high_keyboard_supply_limit | **pass (modeled)** 0.08 A against limit 0 A | pass (modeled) 0.08 A against limit 0 A | retained (inputs unchanged, rerun matches) |

## Candidate policy review

Policy `portable-runtime-4h-pi-load-candidate` on revision 3: **ADMIT_WITH_LIMIT**

## Unresolved

- None reported by HS.

## Not tested

- No physical build, bench measurement, power-on or field operation was performed for either revision.
- Modeled runtime and current values are calculations from declared assumptions, not observed behaviour.
- Physical means of reaching pi_work_current_a = 0.697: unknown / not tested.

## Not linked

- Nothing reported.

## Sources

| Role | File | SHA-256 |
|---|---|---|
| base_export | `r2-export.json` | `d1a5fa318d4013f11b534eb02634b7c4a6a675a3d7d307724a2758063ddd595d` |
| base_review | `r2-candidate-review/review.json` | `d61f0c57f35d36d9e819487c78e7a5024221f65a93b4ee35c3397f47e77ae6ee` |
| base_review_replay | `r2-candidate-review/replay.json` | `0cf04c152835f32f7b8bbd5719f9aaa27bb6cc3715efc75c19e6350f77d24693` |
| candidate_export | `r3-export.json` | `76d1d4d6b3ce56fbe346a6a4d1182d786ac3041dfda98e6fd31f74486fae1df0` |
| candidate_review | `r3-review/review.json` | `36e529baa084a7ef3420d8fdebf6b053d852d3cc87a78b9f453419d109a5f8ac` |
| candidate_review_replay | `r3-review/replay.json` | `2679ce0d44ed674ac6cef962d0aa0432b63636ee5186abe662baadb557fc768b` |
| proposal | `proposal-r3.json` | `e2845df3b3253b8aef91729262e89f2fcefa985bcbaf01c9c2e5c3fb5be2f498` |

Receiver checks performed:

- every covered file's bytes match its recorded SHA-256
- base and candidate exports match the packet's project, revision, run, package hash, requirements, requirements_met and checks
- each Policy Lab review has a verify receipt naming its exact bytes
- the proposal shown (policy, decision, unmet targets, requirement changes) is read from the covered files
- the Policy Lab review binds the exact base export bytes
- the HS proposal binds that review, and the candidate carries its resolved requirements
- every failing candidate check from the export is listed as unresolved
- each applied modelled candidate matches its review row, and its native outcome matches the candidate export
