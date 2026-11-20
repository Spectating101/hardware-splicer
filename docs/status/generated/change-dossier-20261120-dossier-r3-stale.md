# Engineering change dossier: digital-9fa33a1ccc9c4c4aa677de4bcbb84317

Edition `596a6fd85ac2b583` · case `fielddeck-5` · evidence level **modeled** · physical authority granted: **no**

> **STALE EDITION.** HS project is at revision 4; this edition describes revision 3 run_id changed from 78ea06aa03b241fe921cb102a8423442 to 1cef04ad3bdc4f29bf69d98610f2bacf package_sha256 changed from 7234517b8267886f0b6ed7a69b027fbf61061187e97bf9b2456c3fd5038f737c to 3c4854d05d8dd0c4c92febf75025412527d2c40f81b521a1b574357c0a0db64a snapshot_sha256 (declared by HS) changed from b06b165100d1cf1ae65ed38e5aa39fe38fa6583e4f20ac20ad792c872d39c872 to ea7ffdd732bf2d77ecd0463d1e57ce49752df4b2cf8833dd3958f1cab0e316bf seal_sha256 (declared by HS) changed from 61c8e4d525dfffe42e05f92a719e52b3f98d675389b38d77826cf2f62108c996 to 11f8304aa7706af94d0c160b5a2e44a753c856d6d109df6880b36d281d5403e7 Do not reuse this dossier.

## Decision under review

Should revision 3 replace revision 2 under policy portable-runtime-4h-pi-load-candidate 1.0.0?

Not decided by this dossier. Revision 3 has 0 failing and 0 untested modeled check(s) and no physical evidence.

## Revisions

| | Revision | Run | Package | Requirements met | Snapshot / seal (declared by HS, not verified by Cite) |
|---|---:|---|---|---|---|
| base | 2 | `73a17dbce241` | `b630c5ded559` | no | `d2ecf433e7ba` / `50c6b86ae659` |
| candidate | 3 | `78ea06aa03b2` | `7234517b8267` | yes (modeled) | `b06b165100d1` / `61c8e4d525df` |

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
| base_export | `r2-export.json` | `f3050ab7eb3f0b93c85b639336630aa5aeed8d6c24006cc3eb02bff1ccdef0c6` |
| base_review | `r2-candidate-review/review.json` | `256edd2bdd0a1cd9476747af9b42047e714d7c471e3233ea6e1692e9dd0e672c` |
| base_review_replay | `r2-candidate-review/replay.json` | `7acce6adc92c24041ca5b0f16b596d3d41c418d332f4594de3e975e9f71e3414` |
| candidate_export | `r3-export.json` | `5832d9562c0dd9f5d76f2cd9f0d956560fedadbb67628c9620e3e23b77e21f82` |
| candidate_review | `r3-review/review.json` | `218265963f91fad81bd557645dc167e95a78e2617e819f92b7c174d152e60fec` |
| candidate_review_replay | `r3-review/replay.json` | `21215d8d2141b09164fe869a6e8e06c71a6caf72fc73220475baff97f5594b75` |
| proposal | `proposal-r3.json` | `b58617290d2dc4f8966eab309e68f576769928bd3dc40b5d2e9b5f1526cfcaea` |

Receiver checks performed:

- every covered file's bytes match its recorded SHA-256
- base and candidate exports match the packet's project, revision, run, package hash, requirements, requirements_met and checks
- each Policy Lab review has a verify receipt naming its exact bytes
- the proposal shown (policy, decision, unmet targets, requirement changes) is read from the covered files
- the Policy Lab review binds the exact base export bytes
- the HS proposal binds that review, and the candidate carries its resolved requirements
- every failing candidate check from the export is listed as unresolved
- each applied modelled candidate matches its review row, and its native outcome matches the candidate export
