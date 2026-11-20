# Engineering change dossier: digital-ad6d77eab00448cd9eb3c07e2691ddeb

Edition `180dcbc2fc314170` · case `fielddeck-5` · evidence level **modeled** · physical authority granted: **no**

> **STALE EDITION.** HS project is at revision 4; this edition describes revision 3 run_id changed from 7fbc1add497d47ba94b4de021bd2e2ef to 3782cabc69364820a1c20b71abf35e36 snapshot_sha256 changed from 4591bf4cefc077a19ac362d606b3d1cd48df77cf5dfd299efd20932ed8185a85 to 25bf241869ad988270d9bf48ad88c63094c9ee5ba65a8660317cb373db97a745 seal_sha256 changed from 1e8c3f7a93338db720f6ff857e81e3911e48729992d2c2d0bd966010499b1141 to bfe0487733e70d25aa0252fd14696e7dff02d87bb36e1e05e72b1d514337aead package_sha256 changed from 27e330d6fc826822ca1b7112561e450a43cc24582d81078272325a4dda6c3d2c to d56014ebc09e95f5a34e1fcc913be268c0e1d8d1ac4f081eb499048c8f67fb81 Do not reuse this dossier.

## Decision under review

Should revision 3 replace revision 2 under policy portable-runtime-4h-pi-load-candidate 1.0.0?

Not decided by this dossier. Revision 3 has 0 failing modeled check(s) and no physical evidence.

## Revisions

| | Revision | Run | Snapshot | Package | Requirements met |
|---|---:|---|---|---|---|
| base | 2 | `df70f6a5008b` | `dfa3a253f6fc` | `9f05656fe028` | no |
| candidate | 3 | `7fbc1add497d` | `4591bf4cefc0` | `27e330d6fc82` | yes (modeled) |

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
| base_export | `r2-export.json` | `634a91e17cacc190075593339cafa7126aaf3b843e04181c44d5d1a22be2f861` |
| base_review | `r2-candidate-review/review.json` | `c5d4e62b229bcf10cf1a69ebd65ee3656377ffbac4365f554ff94e1030b218cf` |
| candidate_export | `r3-export.json` | `52c9b2576aba3158ccdba791d8bd4400725ed9ae1dd3ad418f0591e7d2a2660f` |
| candidate_review | `r3-review/review.json` | `c3c148ab94992dd75c484bc736805c877a76096c118398ea83d273558f867a59` |
| proposal | `proposal-r3.json` | `44730b0e3ed8788d24b2efb11e1e20a565804daf713ca86b7141506e895cd8d6` |

Receiver checks performed:

- every covered file's bytes match its recorded SHA-256
- base and candidate exports match the packet's project, revision, run, package hash, requirements and checks
- the Policy Lab review binds the exact base export bytes
- the HS proposal binds that review, and the candidate carries its resolved requirements
- every failing candidate check from the export is listed as unresolved
- each applied modelled candidate matches its review row, and its native outcome matches the candidate export
