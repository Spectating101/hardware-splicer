# Hardware Splicer: Optiplex review handoff

## Start here

This branch publishes the previously local Optiplex integration work, captures the pending source-check and product-index files, and brings in the corrected F60 keyboard package from PR #342. It is a review snapshot for Codex. No changes from this handoff have been merged into GitHub main.

The source checkout continued on `integration/github-features-20261116`. This review was assembled in a separate worktree; the source checkout's files and index were not modified.

## Provenance

- Source integration commit: `ede2f538fd1ca3a02645b130e1b92337bda9a91b` (18 November 2026, 17:41:59 Taipei).
- Snapshot of pending source-check and product-index files: `824758af0b867f498918c35b9a6d92bbd7428201`.
- Keyboard source: `70a1e8decd059b386b0e672ba395eff60e895d36`, [PR #342](https://github.com/Spectating101/hardware-splicer/pull/342).
- Combined code commit tested for this handoff: `36a084e00f4a117e150cbec078e926fa66415e93`.
- GitHub main at preparation: `38dbad2b759a9313b81a5b10bfde7f20d64f308c`.
- Exact hashes and cutoff for captured working files: [snapshot manifest](HS_OPTIPLEX_HANDOFF_20261118.json).

The prior integration included keyboard commit `f2310b96`, but lacked the subsequent legacy-zone, compact-junction and round-10 mechanical packages. This review merges the complete later keyboard history. The merge completed without conflicts.

## Where to review

| Area | Main evidence | Review focus |
|---|---|---|
| Native source editing | [Connected workflow receipt](../status/generated/source-workflow-connection-20261118.json) | Retained native geometry and project rules, proposal/acceptance hashes, exact-revision checks, downstream invalidation. Moving a footprint does not automatically reroute copper. |
| Headless backend | [Release evidence](../status/generated/headless-backend-release-20261118.json), [deployment documentation](../PACKAGING_AND_DEPLOYMENT.md) | CLI/API/MCP parity, queued-job recovery, restore behavior and reproducible installation. The older full-suite receipt belongs to candidate `7934cf1a`, not the final afternoon additions. |
| Sweep keyboard | [Evaluation and limitations](../../eval/unseen_sweep/README.md) | Frozen predictions versus the post-reveal detector fix; controller-label discrepancy; unresolved native findings. |
| Five external devices | [Evaluation](../../eval/unseen_devices/README.md) | Operator-selected questions and case-specific adapters; 14 matching answers plus one abstention; two unresolved polygon-dependent copper paths. |
| Corrected F60 package | [Round-10 package](../../examples/arbitrage_lab/keyboard_splice/arbitrary_corpus/f60_mechanical_round10) | Square switch keepouts, rejection of the previous clipped aperture, 58 retained/four relocated keys, 42 active IDC contacts, source-derived matrix proof and physical-release limits. |
| Original product candidate | [Inspection nest](../../projects/pcb-inspection-nest/README.md) | Editable CAD and export checks; source attribution; bare-board-only geometry, tolerances, populated-board clearance and stability. |
| Product/reuse research | [Product index](../../projects/engineering-opportunity-portfolio/product-index.md), [expanded comparison](../../projects/engineering-opportunity-portfolio/expanded-market-comparison.md), [feasibility replay](../SALVAGE_COMPANY_FEASIBILITY.md) | Distinguish modeled offers and device briefs from finished designs, owned stock, completed sales and observed demand. |

## Verification performed for this handoff

**209 tests passed, zero failures, zero skips**, across 32 existing test files on the combined code commit above. This ran the keyboard-splice tests, including native KiCad checks, plus registered-source, stored-parser, parser-hardening, planning-bridge and engineering-source-ingestion regressions.

- [Machine-readable test receipt and exact file list](hs-optiplex-20261118/targeted-tests.json)
- [Complete targeted-test output](hs-optiplex-20261118/targeted-pytest.log)
- One existing Starlette/httpx deprecation warning was emitted.
- Imports were checked to resolve from the isolated review worktree.
- Subsequent handoff changes are documentation, evidence receipts and product-comparison data. No production code changed after this test run.
- The whole repository suite was not rerun for this publication. The existing 4,533-pass release evidence applies to the earlier candidate named in its receipt.
- Hosted CI results belong to their actual commit. Do not carry old green runs forward as evidence for this branch.

Reproduce the focused check in a suitable HS environment:

```sh
PYTHONPATH=src HARDWARE_SPLICER_SKIP_VISION_LIVE=1 python -m pytest -q -ra -p no:cacheprovider \
  tests/test_keyboard_splice*.py \
  tests/test_kicad_registered_source_check.py \
  tests/test_stored_source_parser.py \
  tests/test_stored_source_parser_hardening.py \
  tests/test_project_parser_planning_bridge.py \
  tests/test_engineering_source_ingestion.py
```

The local run used Python 3.13.5, Shapely 2.2.0, pytest 9.0.3 and the installed native KiCad tools. The dedicated hosted keyboard workflow uses Python 3.12.

## Specific review questions

1. **Registered-source checker scope.** The pending helper, now captured for review, is opt-in via `HARDWARE_SPLICER_ENABLE_KICAD_SOURCE_CHECK=1`. It checks an isolated hash-verified uploaded file. It does not copy companion project/custom-rule files, hierarchical sheets or external libraries. Keep this separate from retained-project rule verification in the editing workflow.
2. **Untested helper branches.** Its new tests cover format recognition, opt-in behavior, missing executable and signature mismatch. Review successful ERC/DRC, exit 5 with findings, timeout/error handling, report interpretation, schematic netlist export and the enabled parser integration. The report/subprocess output is not byte-bounded, and the receipt lacks a KiCad version.
3. **Combined parser behavior.** Verify that the opt-in early return preserves registered-source hash revalidation, the existing authority ceiling and downstream planning expectations.
4. **Keyboard integration.** Verify the newer Sweep detector behavior alongside the restored F60 round-10 package. The original arbitrary-donor strict 0/8 benchmark is not superseded by a narrower model success.
5. **Inventory correctness.** The feasibility replay records a legacy duplicate-listing bug: importing the same unpurchased offer twice increases apparent inventory and confidence despite zero receipts. The newer exact-materials/InvenTree path should remain distinct until reconciliation is implemented.
6. **Commercial and physical evidence.** The product comparisons are captured research drafts and hypothetical economics. The 620 configuration rows are briefs, not 620 completed products. The customer-service pilot was internal and fictional. Physical acceptance, actual customer orders, support cost and realized margins remain unverified.

## Suggested review outcome

Return concrete findings with affected paths and a reproduction or evidence reference. Distinguish integration defects, missing verification and product-development questions. This handoff is intended to make the existing work reviewable; it does not claim the broad stack is ready to merge or that any physical product has been built.
