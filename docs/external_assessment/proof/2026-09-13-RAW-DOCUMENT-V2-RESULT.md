# Astra raw-document v2 result

Raw-document v2 passed all four generic Codex/Astra contracts but failed one check in
the separately preregistered raw-document adjudicator. Its combined experiment status is
`failed`; the proof publisher now records the generic runtime result and optional
adjudication result separately so this cannot be mislabeled as a pass.

## What passed

- all 11/11 extraction targets passed every source, page, hash, quote, semantic,
  extraction-identity, authority, and review-state check;
- all 11 claims were used in the canonical pre-fabrication plan;
- all plan source references were valid;
- direct 3.3 V connection was rejected;
- TXU0304 remained a family-level preference;
- the incompatible single-device SN74AXC4T245 topology was rejected;
- all required blockers and extraction limitations were preserved;
- hard truth, mission progress, operation-to-state provenance, and terminal-report
  contracts passed;
- all 33 MCP calls completed without failure;
- revision 6 and a deterministic engineering package were produced;
- physical correctness remained `UNPROVEN` and physical authority remained closed.

Usage was 557,963 input tokens, 476,672 cached input tokens, and 3,763 output tokens.
No API fallback occurred.

## Why the combined experiment failed

The only failing raw-document check was
`txu0304_four_signal_mapping_complete`. Astra persisted the electrically meaningful
pairs `SCLK`→`CLK`, `CS#`→`/CS`, `MOSI_IO0`→`DI`, and `MISO_IO1`→`DO`. The v2 evaluator
required `DI_IO0` and `DO_IO1` for the final two DUT strings.

V2 correctly removed v1's route-notation and disposition errors, but it did not define a
canonical alias policy for datasheet labels such as `DI (IO0)` and `DO (IO1)`. The hidden
exact-string comparison therefore remains an unjustified serialization dependency. V2 is
not rerun or retroactively rescored.

## Next protocol boundary

A v3 evaluator may normalize only preregistered signal-label aliases before comparing the
same four direction pairs. It must retain all page, semantic, disposition, blocker,
provenance, report, and authority checks. That protocol must be committed and tagged before
one new live sample.

The sanitized proof bundle is in
`astra_runs/2026-09-13-raw-document-v2/PROOF_BUNDLE.json`.
