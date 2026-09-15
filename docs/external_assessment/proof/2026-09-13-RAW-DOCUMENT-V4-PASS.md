# Astra raw-document v4 pass

Raw-document v4 is the first complete passing Hardware Splicer raw-PDF Astra run. It
passed all four generic Codex/Astra contracts and every preregistered raw-document
adjudication check in one clean-room attempt.

## Result

- combined result: `passed`;
- raw-document claims: 11/11 fully anchored and used;
- source-reference issues: 0 across 137 plan references;
- authority violations: 0;
- MCP calls: 33, with 0 failed calls and 0 backend application failures;
- final canonical revision: 6;
- deterministic engineering package: present;
- input tokens: 572,649, of which 488,448 were cached;
- output tokens: 3,564;
- API fallback: false;
- physical correctness: `UNPROVEN`;
- physical authority granted: false.

## What Astra did

With no curated claim paraphrases, expected pages, expected values, expected conclusions,
repository access, web access, or shell use, Astra:

1. searched and read exact pages from three hash-bound manufacturer PDFs through HS;
2. registered all eleven target claims with page text that the server verified was present;
3. preserved server-computed source, page-text, support-text, and extraction identities;
4. kept every model-derived document claim `proposed` and `unreviewed`;
5. used those claims in canonical requirements, candidates, decisions, blockers, and
   dependency-aware next actions;
6. rejected direct 3.3 V connection from the DUT absolute-maximum evidence;
7. preferred TXU0304 only as a family-level candidate with a complete 3+1 SPI mapping;
8. rejected one SN74AXC4T245 for the simultaneous 3+1 direction requirement;
9. retained every implementation, identity, timing, review, and physical-evidence blocker;
10. read back revisioned canonical state and exported a deterministic package.

## Why this is the boundary result

V1 demonstrated correct extraction but failed three contract edges. V2 passed all generic
contracts but exposed an unjustified signal-label string dependency. V3 passed the entire
raw rubric but exposed host-global Codex instruction contamination. Each result was frozen
and published as failed. V4 changed only the runner isolation boundary from v3; its
model-visible engineering task and raw evaluator were unchanged.

The strongest supported claim is:

> In this frozen case, Astra independently extracted all preregistered engineering facts
> from hash-bound manufacturer PDF text through Hardware Splicer, converted them into
> attributable revisioned pre-fabrication state, satisfied deterministic engineering and
> provenance checks, and preserved uncertainty and physical-authority boundaries.

## Nonclaims

This result does not prove visual PDF comprehension, source authenticity or currentness,
independent EE review, electrical correctness, exact physical DUT/programmer/package
identity, supply/timing/protection closure, bench behavior, fabrication readiness, or
physical authority. It is an existence proof for governed pre-fabrication reasoning, not a
validated circuit.

The sanitized, hash-accounted proof bundle is in
`astra_runs/2026-09-13-raw-document-v4-pass/PROOF_BUNDLE.json`.
