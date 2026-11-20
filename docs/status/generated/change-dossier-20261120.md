# Engineering change dossier replay (change-dossier-20261120)

Result: **chain completed, every negative control refused**. All engineering values are modeled by the registered Fielddeck 5 digital study; nothing was built, measured or powered, and physical authority was never granted. This is a replay on real code, not customer use or physical proof.

## Chain

- HS project `digital-ad6d77eab00448cd9eb3c07e2691ddeb`.
- r1 run `6d65be4868854bf2a848499979fc7b50`, package `a9a0c1aac9c3e898`: work_runtime pass 3.166 h (limit 2.5); ordinary_source_margin pass 0.48 A (limit 0.3); high_keyboard_supply_limit pass 0.08 A (limit 0).
- Policy Lab `portable-runtime-4h` on r1: **BLOCKED** (metric.work_runtime_lower_h is 3.166 h; target >= 4 h.); replay verified: True.
- HS-validated proposal: `{"minimum_work_runtime_h": {"after": 4.0, "before": 2.5}}`.
- r2 run `df70f6a5008b4489b20e63a7885b71d0` (parent 1), package `9f05656fe0282dcc`: work_runtime FAIL 3.166 h (limit 4.0); ordinary_source_margin pass 0.48 A (limit 0.3); high_keyboard_supply_limit pass 0.08 A (limit 0). Requirements met: False.
- Policy Lab on r2: **BLOCKED** (Revise the design to satisfy HS constraint work_runtime.; metric.work_runtime_lower_h is 3.166 h; target >= 4 h.).
- Change evidence sha256 `24f6bca7bf8d976abc4582743606f39b99ee58551e597924527c59c9fcb3a01e`.
- Cite edition `e4c64c1113d79581` bound to r2; failing checks kept: work_runtime.
- r3 run `7fbc1add497d47ba94b4de021bd2e2ef` (modelled candidate applied): work_runtime pass 4.002 h (limit 4.0); ordinary_source_margin pass 0.48 A (limit 0.3); high_keyboard_supply_limit pass 0.08 A (limit 0). Requirements met: True.
- r4 run `3782cabc69364820a1c20b71abf35e36` (further change): work_runtime pass 4.002 h (limit 3.0); ordinary_source_margin pass 0.48 A (limit 0.3); high_keyboard_supply_limit pass 0.08 A (limit 0).

## Modelled candidate design change (revision 3)

Policy Lab `portable-runtime-4h-pi-load-candidate` on the failing revision 2 (BLOCKED) proposed `pi-work-load-budget`: `pi_work_current_a` 1 → **0.697** A (PROPOSED).

- Formula: `E_min = (R - r/2) x (P - r/2); P_required = E_min / T; dI = (P + r/2 - P_required) / V; I_after = floor((I_before - dI) / step) x step`.
- Numbers: before = 1, export_resolution = 0.001, required_current_reduction_a = 0.302685, required_work_power_w = 5.737073, runtime_h = 3.166, supply_voltage_v = 5, target_h = 4, usable_energy_lower_bound_wh = 22.948292, work_power_w = 7.25.
- Assumption: Runtime is usable energy divided by work system power, and the adjusted input does not change usable energy.
- Assumption: Work power falls by 5 W for each ampere removed from pi_work_current_a (declared supply voltage).
- Assumption: Exported values are rounded to the declared resolution; the bound takes the least favourable rounding.
- Assumption: Other checks reading this input (for example source margin) are not predicted here; HS must rerun them.
- HS replay check: replayed by Policy Lab verify here.
- HS requirement changes applied as revision 3: `{"pi_work_current_a": {"after": 0.697, "before": 1.0}}`.
- **Native rerun:** metric.work_runtime_lower_h = **4.002 h** against >= 4 h: meets the target (modeled, margin 0.002 h).
- Revision 3 metrics: `{"high_keyboard_source_margin_a": 0.08, "ordinary_source_margin_a": 0.48, "work_runtime_lower_h": 4.002, "work_runtime_upper_h": 5.65, "work_system_power_w": 5.735}`.
- Policy Lab on revision 3: ADMIT_WITH_LIMIT.
- Physical means of reaching this load: **unknown / not tested**. Nothing here says what would make the Pi draw this current.

## Negative and stale controls

- `stale_policy_feedback`: refused. The project changed after the policy assessment; export and assess the new revision.
- `changed_covered_file`: refused (exit 1). candidate_export: r2-export.json does not match its recorded SHA-256; the bytes changed
- `wrong_revision_identity`: refused (exit 1). candidate_export: export is not revision 2 of digital-ad6d77eab00448cd9eb3c07e2691ddeb with the recorded run and package
- `hs_repackage_after_change`: refused. Revision 2 is not the latest (3); export the current change.
- `stale_edition_check`: stale (exit 3). HS project is at revision 3; this edition describes revision 2; run_id changed from df70f6a5008b4489b20e63a7885b71d0 to 7fbc1add497d47ba94b4de021bd2e2ef; snapshot_sha256 changed from dfa3a253f6fc40750ad9e20c1b58ceb8f5cd89e8ec4bee6b5df1729e0fef2d46 to 4591bf4cefc077a19ac362d606b3d1cd48df77cf5dfd299efd20932ed8185a85; seal_sha256 changed from 5b926bcd4be2c58274e36bcc27dab6cae7f6a35c2ef0b28c2b082e44ce3c5f50 to 1e8c3f7a93338db720f6ff857e81e3911e48729992d2c2d0bd966010499b1141; package_sha256 changed from 9f05656fe0282dcc349cba248e8f1894560746578b5d484ff005d6347b62db93 to 27e330d6fc826822ca1b7112561e450a43cc24582d81078272325a4dda6c3d2c
- `stale_edition_reissue`: refused (exit 3)
- `candidate_edition_stale_check`: stale (exit 3). HS project is at revision 4; this edition describes revision 3; run_id changed from 7fbc1add497d47ba94b4de021bd2e2ef to 3782cabc69364820a1c20b71abf35e36; snapshot_sha256 changed from 4591bf4cefc077a19ac362d606b3d1cd48df77cf5dfd299efd20932ed8185a85 to 25bf241869ad988270d9bf48ad88c63094c9ee5ba65a8660317cb373db97a745; seal_sha256 changed from 1e8c3f7a93338db720f6ff857e81e3911e48729992d2c2d0bd966010499b1141 to bfe0487733e70d25aa0252fd14696e7dff02d87bb36e1e05e72b1d514337aead; package_sha256 changed from 27e330d6fc826822ca1b7112561e450a43cc24582d81078272325a4dda6c3d2c to d56014ebc09e95f5a34e1fcc913be268c0e1d8d1ac4f081eb499048c8f67fb81
- `candidate_edition_reissue`: refused (exit 3)

## Adapters

| Hand-off | Classification | Evidence |
|---|---|---|
| HS export → Policy Lab review | executable integration | HS `policy_layer` export bytes are reviewed and replay-verified by Policy Lab's own `run.mjs` in this replay. |
| Policy Lab review → HS proposal | executable integration | HS `validate_policy_feedback` checks the decision against its rows, runs Policy Lab `verify` itself, and binds the review to the exact export bytes. |
| HS proposal → new HS revision | executable integration | `DigitalStudyEngine.run_revision` reruns the registered native study; the check delta comes from `study_evidence`. |
| Policy Lab → modelled candidate design change → HS revision 3 | executable integration | Policy Lab computes the `pi_work_current_a` candidate from exported modeled numbers; HS applies the selected candidate and reruns natively; the packet reports the native value against the target. |
| HS change evidence → Cite dossier | executable integration | Cite's `engineering_change_cli` rereads and hash-checks every covered file and rederives the candidate outcome. |
| Cite stale-edition gate | executable integration | Triggered by real HS revisions 3 and 4; Cite compares each edition with HS's exported revision head. |
| Cite edition → Cite workspace claims | tested isolated adapter | `record_in_workspace` writes through Cite's project/claim/evidence store; exercised here, with no reader beyond the store. |
| Candidate load → physical means (underclock, board, peripheral) | not linked | Nothing identifies or tests how the Pi would draw the candidate current; stated as unknown / not tested. |
| Automatic HS → Cite revision watcher | proposed | Nothing notifies Cite of a new HS revision; the head is exported and passed by this script. |

## Not tested or not linked

- No physical build, bench measurement, power-on or field operation was performed for either revision.
- Modeled runtime and current values are calculations from declared assumptions, not observed behaviour.
- Physical means of reaching pi_work_current_a = 0.697: unknown / not tested.
- LivePresenter: not linked (optional, skipped).

## Files

- Revision-2 dossier: [`change-dossier-20261120-dossier.md`](change-dossier-20261120-dossier.md); stale-marked recheck: [`change-dossier-20261120-dossier-stale.md`](change-dossier-20261120-dossier-stale.md).
- Revision-3 (candidate) dossier: [`change-dossier-20261120-dossier-r3.md`](change-dossier-20261120-dossier-r3.md); stale-marked recheck: [`change-dossier-20261120-dossier-r3-stale.md`](change-dossier-20261120-dossier-r3-stale.md).
- Exact exchanged bytes: `change-dossier-20261120-exchange/`.
- Log and JSON summary: `change-dossier-20261120.log`, `change-dossier-20261120.json`.
- Sources: HS `55d3f4cda7f7`, Policy Lab `f3b18cc9c278`, Cite `d0d88886341a`.
