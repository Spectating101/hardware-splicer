# Engineering change dossier replay (change-dossier-20261120)

Result: **chain completed, every negative control refused**. All engineering values are modeled by the registered Fielddeck 5 digital study; nothing was built, measured or powered, and physical authority was never granted. This is a replay on real code, not customer use or physical proof.

## Chain

- HS project `digital-278ce63f5bb5427795e172920cefa95b`.
- r1 run `765e60c3a0b24c95bf14cc28f05fd7ad`, package `c8352f6c9a15ca99`: work_runtime pass 3.166 h (limit 2.5); ordinary_source_margin pass 0.48 A (limit 0.3); high_keyboard_supply_limit pass 0.08 A (limit 0).
- Policy Lab `portable-runtime-4h` on r1: **BLOCKED** (metric.work_runtime_lower_h is 3.166 h; target >= 4 h.); replay verified: True.
- HS-validated proposal: `{"minimum_work_runtime_h": {"after": 4.0, "before": 2.5}}`.
- r2 run `22f91786d72648938a9c657f593f9e33` (parent 1), package `7e53b5f7385b28db`: work_runtime FAIL 3.166 h (limit 4.0); ordinary_source_margin pass 0.48 A (limit 0.3); high_keyboard_supply_limit pass 0.08 A (limit 0). Requirements met: False.
- Policy Lab on r2: **BLOCKED** (Revise the design to satisfy HS constraint work_runtime.; metric.work_runtime_lower_h is 3.166 h; target >= 4 h.).
- Change evidence sha256 `5c29ac1bf4c13347a7946ca8f9634ba92c56b4acdc56a056329cbc79972c8c73`.
- Cite edition `ba12b22711425655` bound to r2; failing checks kept: work_runtime.
- r3 run `02889759d72843afa9d9c7a0d4e98591`: work_runtime pass 3.166 h (limit 3.0); ordinary_source_margin pass 0.48 A (limit 0.3); high_keyboard_supply_limit pass 0.08 A (limit 0).

## Negative and stale controls

- `stale_policy_feedback`: refused. The project changed after the policy assessment; export and assess the new revision.
- `changed_covered_file`: refused (exit 1). candidate_export: r2-export.json does not match its recorded SHA-256; the bytes changed
- `wrong_revision_identity`: refused (exit 1). candidate_export: export is not revision 2 of digital-278ce63f5bb5427795e172920cefa95b with the recorded run and package
- `hs_repackage_after_change`: refused. Revision 2 is not the latest (3); export the current change.
- `stale_edition_check`: stale (exit 3). HS project is at revision 3; this edition describes revision 2; run_id changed from 22f91786d72648938a9c657f593f9e33 to 02889759d72843afa9d9c7a0d4e98591; snapshot_sha256 changed from f368826ad623d0b9ce3abb2ed23ff5e0004c73464efec71b9b0622fc7f694a3a to 209a3a69f5c82fcd672eb34b67bce5370c1b4592672b2784452f04598f45b524; seal_sha256 changed from bd9013d7c812fe93dc7d3bbecb70b2ab1739eec2dbc878f05e5f1d6b5fc74195 to 8297d57da31a059a6b0db19d7b2e695ebb3cd0b4c19088ddfb1672abb97266b0; package_sha256 changed from 7e53b5f7385b28dbd030962ef10135b934c6dcbec957329001c93a923f782aad to 88effccc3d409037179754b33b4438cfbb86b63966d3b8013fec12b8b6200dc1
- `stale_edition_reissue`: refused (exit 3)

## Adapters

| Hand-off | Classification | Evidence |
|---|---|---|
| HS export → Policy Lab review | executable integration | HS `policy_layer` export bytes are reviewed and replay-verified by Policy Lab's own `run.mjs` in this replay. |
| Policy Lab review → HS proposal | executable integration | HS `validate_policy_feedback` binds the review to the exact export bytes and resolves the overrides. |
| HS proposal → new HS revision | executable integration | `DigitalStudyEngine.run_revision` reruns the registered native study; the check delta comes from `study_evidence`. |
| HS change evidence → Cite dossier | executable integration | Cite's `engineering_change_cli` (new receiving contract) rereads and hash-checks every covered file. |
| Cite stale-edition gate | executable integration | Triggered here by a real third HS revision; Cite compares the edition with HS's exported revision head. |
| Cite edition → Cite workspace claims | tested isolated adapter | `record_in_workspace` writes through Cite's project/claim/evidence store; exercised here, with no reader beyond the store. |
| Automatic HS → Cite revision watcher | proposed | Nothing notifies Cite of a new HS revision; the head is exported and passed by this script. |
| Policy Lab → computed design fix | proposed | Policy Lab returns the policy's declared target as the override; it does not propose a design change that meets it. |

## Not tested or not linked

- No physical build, bench measurement, power-on or field operation was performed for either revision.
- Modeled runtime and current values are calculations from declared assumptions, not observed behaviour.
- LivePresenter: not linked (optional, skipped).

## Files

- Readable dossier: [`change-dossier-20261120-dossier.md`](change-dossier-20261120-dossier.md); stale-marked recheck: [`change-dossier-20261120-dossier-stale.md`](change-dossier-20261120-dossier-stale.md).
- Exact exchanged bytes: `change-dossier-20261120-exchange/`.
- Log and JSON summary: `change-dossier-20261120.log`, `change-dossier-20261120.json`.
- Sources: HS `c9abb1db547f`, Policy Lab `c565530a9fca`, Cite `9bc8ff12c0bb`.
