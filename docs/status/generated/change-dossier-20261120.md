# Engineering change dossier replay (change-dossier-20261120)

Result: **chain completed, every negative control refused**. All engineering values are modeled by the registered Fielddeck 5 digital study; nothing was built, measured or powered, and physical authority was never granted. This is a replay on real code, not customer use or physical proof.

## Chain

- HS project `digital-996558719b13454fb1724bef8f218093`.
- r1 run `09a597a3bd07423bad8cdba4cca99098`, package `f505c76f745da1d7`: work_runtime pass 3.166 h (limit 2.5); ordinary_source_margin pass 0.48 A (limit 0.3); high_keyboard_supply_limit pass 0.08 A (limit 0).
- Policy Lab `portable-runtime-4h` on r1: **BLOCKED** (metric.work_runtime_lower_h is 3.166 h; target >= 4 h.); replay verified: True.
- HS-validated proposal: `{"minimum_work_runtime_h": {"after": 4.0, "before": 2.5}}`.
- r2 run `597107a7c64a4a1bbad809b63d211543` (parent 1), package `d4652acd9d8e95f7`: work_runtime FAIL 3.166 h (limit 4.0); ordinary_source_margin pass 0.48 A (limit 0.3); high_keyboard_supply_limit pass 0.08 A (limit 0). Requirements met: False.
- Policy Lab on r2: **BLOCKED** (Revise the design to satisfy HS constraint work_runtime.; metric.work_runtime_lower_h is 3.166 h; target >= 4 h.).
- Change evidence sha256 `b639398c1ce60b9095381032905ba5af0b27f1763ad87ddedbe9307599881bd0`.
- Cite edition `2075bf9f3479df23` bound to r2; failing checks kept: work_runtime.
- r3 run `f35f80c0dfcb42e4b066906be52a919a` (modelled candidate applied): work_runtime pass 4.002 h (limit 4.0); ordinary_source_margin pass 0.48 A (limit 0.3); high_keyboard_supply_limit pass 0.08 A (limit 0). Requirements met: True.
- r4 run `0b05b3b8b1014fa88b8b45b75c33453b` (further change): work_runtime pass 4.002 h (limit 3.0); ordinary_source_margin pass 0.48 A (limit 0.3); high_keyboard_supply_limit pass 0.08 A (limit 0).

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
- `wrong_revision_identity`: refused (exit 1). candidate_export: export is not revision 2 of digital-996558719b13454fb1724bef8f218093 with the recorded run and package
- `hs_repackage_after_change`: refused. Revision 2 is not the latest (3); export the current change.
- `stale_edition_check`: stale (exit 3). HS project is at revision 3; this edition describes revision 2; run_id changed from 597107a7c64a4a1bbad809b63d211543 to f35f80c0dfcb42e4b066906be52a919a; package_sha256 changed from d4652acd9d8e95f7766ba9834d906bf8b10b8c0527c5a101947a70ae1dd16e07 to 6591f122cea54fba525f451286596b1078317907391fbfc1e7e878fe66fadb2d; snapshot_sha256 (declared by HS) changed from 4278906014bea41049345b204215cb01abdb0c8ae78b52c68d7d51cb9dcc6a67 to 5cbc24ce348e8cc355324823aacd640dc0ee4383ed29924b269c0aa3370e47ec; seal_sha256 (declared by HS) changed from 33dc96f410b578f103a0aea49efb2fd4c762245d921067aff2fc3ab9325f365d to 90d2a4d1e24a288f72ca966563acf51f71713a18ce376eb918c1abdfeb00af30
- `stale_edition_reissue`: refused (exit 3)
- `candidate_edition_stale_check`: stale (exit 3). HS project is at revision 4; this edition describes revision 3; run_id changed from f35f80c0dfcb42e4b066906be52a919a to 0b05b3b8b1014fa88b8b45b75c33453b; package_sha256 changed from 6591f122cea54fba525f451286596b1078317907391fbfc1e7e878fe66fadb2d to 5536cbe0883338558ab8ee9226e27ac74df0d46be49154cc98b2bd3febed39da; snapshot_sha256 (declared by HS) changed from 5cbc24ce348e8cc355324823aacd640dc0ee4383ed29924b269c0aa3370e47ec to 9693acd83a2e8a3ac20cf03bd3d48777e35d69364df235479f671ce29ca9a543; seal_sha256 (declared by HS) changed from 90d2a4d1e24a288f72ca966563acf51f71713a18ce376eb918c1abdfeb00af30 to 539b448e8d9b45b22d183458b2d2afd6de78e818304a2e201a2707f5c387fbbd
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
- Sources: HS `f1da210217bc`, Policy Lab `f6876c12bf81`, Cite `f964b3cb883d`.
