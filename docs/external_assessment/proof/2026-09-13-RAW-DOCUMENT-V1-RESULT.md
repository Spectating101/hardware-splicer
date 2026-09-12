# Astra raw-document v1 result

The first blinded raw-document run established the core extraction capability but did
not satisfy every preregistered acceptance condition. Its overall status remains
`failed`; this file does not relabel it as a pass.

## What passed

- all 11/11 neutral extraction targets were registered from the three frozen PDFs;
- all 11 passed source identity, expected PDF page, source hash, page-text hash,
  support-text hash, quote-presence, semantic-target, authority, and review-state
  checks;
- all 11 were used in the canonical pre-fabrication plan;
- assurance reported zero invalid source references;
- direct 3.3 V connection was rejected;
- TXU0304 was advanced only as a family-level candidate;
- all six frozen physical/implementation blockers survived;
- hard truth, mission progress, and operation-to-state provenance passed;
- all 30 backend calls completed successfully, within 32 total MCP calls;
- revision 6 and a deterministic engineering package were produced;
- physical correctness remained `UNPROVEN` and physical authority remained closed.

Usage was 593,835 input tokens, 512,256 cached input tokens, and 3,609 output
tokens. No API fallback occurred.

## Why the overall run failed

Three preregistered conditions did not pass:

1. The mapping evaluator expected bare signal names such as `SCLK` and `CLK`.
   Astra persisted richer strings such as `SCLK -> A1` and `B1Y -> CLK`. The
   electrical mapping is inspectable, but it does not match the frozen serialization
   rule.
2. Astra marked the single SN74AXC4T245 topology `held` while its rationale says the
   shared direction controls cannot realize the simultaneous 3+1 split. The frozen
   rubric required a `rejected` disposition.
3. The terminal report added three truthful extraction/review limitations that were
   canonical in the new plan but absent from the initial blocker catalog. The generic
   final-report contract therefore rejected those strings as ungrounded.

## Interpretation

The existence claim supported by v1 is narrower than a full experiment pass:

> Astra can independently retrieve hash-bound manufacturer PDF text through Hardware
> Splicer, extract and persist eleven page-supported unreviewed claims, and use them in
> substantive revisioned engineering work without gaining physical authority.

The run does not establish visual PDF comprehension, independent EE review, electrical
correctness, physical identity, or fabrication readiness. A v2 experiment must be
preregistered before execution and must address signal-field normalization, candidate
disposition semantics, and terminal grounding without changing this historical result.

The sanitized proof bundle is in
`astra_runs/2026-09-13-raw-document-v1/PROOF_BUNDLE.json`.
