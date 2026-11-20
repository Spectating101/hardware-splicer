# Engineering change dossier replay (change-dossier-20261120)

Result: **chain completed, every negative control refused**. All engineering values are modeled by the registered Fielddeck 5 digital study; nothing was built, measured or powered, and physical authority was never granted. This is a replay on real code, not customer use or physical proof.

## Chain

- HS project `digital-9fa33a1ccc9c4c4aa677de4bcbb84317`.
- r1 run `d5d2aa1848874439aa048cb7665588a7`, package `e9c99154500a0f2b`: work_runtime pass 3.166 h (limit 2.5); ordinary_source_margin pass 0.48 A (limit 0.3); high_keyboard_supply_limit pass 0.08 A (limit 0).
- Policy Lab `portable-runtime-4h` on r1: **BLOCKED** (metric.work_runtime_lower_h is 3.166 h; target >= 4 h.); replay verified: True.
- HS-validated proposal: `{"minimum_work_runtime_h": {"after": 4.0, "before": 2.5}}`.
- r2 run `73a17dbce2414d46883a61f8dd974ced` (parent 1), package `b630c5ded559584a`: work_runtime FAIL 3.166 h (limit 4.0); ordinary_source_margin pass 0.48 A (limit 0.3); high_keyboard_supply_limit pass 0.08 A (limit 0). Requirements met: False.
- Policy Lab on r2: **BLOCKED** (Revise the design to satisfy HS constraint work_runtime.; metric.work_runtime_lower_h is 3.166 h; target >= 4 h.).
- Change evidence sha256 `0ace438ab8a563224baacfc9200b40e2f13a31629519a544c8b828d57087a18d`.
- Cite edition `7e2edb6b950a2c25` bound to r2; failing checks kept: work_runtime.
- r3 run `78ea06aa03b241fe921cb102a8423442` (modelled candidate applied): work_runtime pass 4.002 h (limit 4.0); ordinary_source_margin pass 0.48 A (limit 0.3); high_keyboard_supply_limit pass 0.08 A (limit 0). Requirements met: True.
- r4 run `1cef04ad3bdc4f29bf69d98610f2bacf` (further change): work_runtime pass 4.002 h (limit 3.0); ordinary_source_margin pass 0.48 A (limit 0.3); high_keyboard_supply_limit pass 0.08 A (limit 0).

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
- `wrong_revision_identity`: refused (exit 1). candidate_export: export is not revision 2 of digital-9fa33a1ccc9c4c4aa677de4bcbb84317 with the recorded run and package
- `hs_repackage_after_change`: refused. Revision 2 is not the latest (3); export the current change.
- `stale_edition_check`: stale (exit 3). HS project is at revision 3; this edition describes revision 2; run_id changed from 73a17dbce2414d46883a61f8dd974ced to 78ea06aa03b241fe921cb102a8423442; package_sha256 changed from b630c5ded559584a91c57211db0f8263bc2e6ba49ea20b26b2fc83927b1b688b to 7234517b8267886f0b6ed7a69b027fbf61061187e97bf9b2456c3fd5038f737c; snapshot_sha256 (declared by HS) changed from d2ecf433e7ba5b6b80da8c667b141347fc125486f9b57ba3071f337b5e816451 to b06b165100d1cf1ae65ed38e5aa39fe38fa6583e4f20ac20ad792c872d39c872; seal_sha256 (declared by HS) changed from 50c6b86ae6597ce2a70dce4842933a02b618d596ca1c42a9a8e016779c7957c7 to 61c8e4d525dfffe42e05f92a719e52b3f98d675389b38d77826cf2f62108c996
- `stale_edition_reissue`: refused (exit 3)
- `candidate_edition_stale_check`: stale (exit 3). HS project is at revision 4; this edition describes revision 3; run_id changed from 78ea06aa03b241fe921cb102a8423442 to 1cef04ad3bdc4f29bf69d98610f2bacf; package_sha256 changed from 7234517b8267886f0b6ed7a69b027fbf61061187e97bf9b2456c3fd5038f737c to 3c4854d05d8dd0c4c92febf75025412527d2c40f81b521a1b574357c0a0db64a; snapshot_sha256 (declared by HS) changed from b06b165100d1cf1ae65ed38e5aa39fe38fa6583e4f20ac20ad792c872d39c872 to ea7ffdd732bf2d77ecd0463d1e57ce49752df4b2cf8833dd3958f1cab0e316bf; seal_sha256 (declared by HS) changed from 61c8e4d525dfffe42e05f92a719e52b3f98d675389b38d77826cf2f62108c996 to 11f8304aa7706af94d0c160b5a2e44a753c856d6d109df6880b36d281d5403e7
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
- Sources: HS `f4e1cbc3ea42`, Policy Lab `f6876c12bf81`, Cite `77824d2c1f9a`.
