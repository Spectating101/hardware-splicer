# Published Astra runs

This directory preserves sanitized, hash-accounted evidence from live clean-room Astra
runs. Each bundle states its own acceptance result and nonclaims. A passing run is evidence
that the model satisfied the tested process and persistence contracts for that case; it is
not proof of electrical correctness, source truth, fabrication readiness, or physical
authority.

## 2026-09-12 sequence

1. `2026-09-12-sellable-baseline` — passing baseline run on the original declared-evidence
   case.
2. The first primary-source attempt stopped before model inference because the governor was
   launched with a Python environment in which Hardware Splicer was not importable. It used
   no model tokens and produced no trace, so there is no full proof bundle to publish.
3. `2026-09-12-primary-source-runtime-mismatch` — Astra reasoned about the new case, but the
   isolated backend was a stale installation without the pre-fabrication-plan endpoint.
   Its attempted state transition failed and the provenance contract correctly rejected the
   unchanged project state.
4. `2026-09-12-primary-source-pass` — after reinstalling the isolated backend from the frozen
   repository commit, all four acceptance contracts and the preregistered document-grounded
   adjudication passed.

The failed attempt is retained because it demonstrates that persuasive model reasoning alone
does not earn credit when the claimed engineering state was not persisted.

## 2026-09-13 blinded sequence

The 2026-09-13 sequence removed the observer adjudication and expected conclusions from the
model-visible snapshot. It also exposed a neutral canonical record contract through the task
manifest so the model could serialize an independently derived answer without guessing hidden
candidate IDs or duplicated locator fields.

1. `2026-09-13-blind-v2-baseline-timeout` — timed out after the empty-store read; no
   engineering package was created.
2. `2026-09-13-blind-v2-baseline-guard-fail` — substantive state and a package were created,
   but the eight-call backend limit denied final readback. The original exact-label
   adjudicator also exposed an answer-shaped serialization assumption.
3. `2026-09-13-blind-v4-baseline-audit-calibration` — the document adjudication passed, but
   the generic audit still required the superseded list-and-describe discovery route instead
   of accepting the compact task manifest.
4. `2026-09-13-blind-v5-baseline-pass` — clean blinded baseline pass: all four generic
   contracts and all eleven document-grounded checks passed.
5. `2026-09-13-blind-v5-conflict-guard-fail` — all twelve conflict-specific checks passed,
   but the nine-call backend guard denied package export and final readback.
6. `2026-09-13-blind-v6-conflict-guard-fail` — all twelve conflict-specific checks passed
   again and package export succeeded, but evidence-delta use made final readback call twelve;
   the eleven-call guard denied it.

The conflict result is therefore `2/2` for persisted conflict reasoning but `0/2` for the full
evaluation-ready contract under the tested resource guards. The post-calibration v7 guard is
twelve backend calls; no v7 live result is claimed. See `2026-09-13-BLINDED-RUN-REPORT.md` for
the exact interpretation and nonclaims.

## 2026-09-13 raw-document sequence

`2026-09-13-raw-document-v1` is the first run in which Astra received no curated facts,
claim paraphrases, page numbers, expected values, or expected conclusions. It searched and
read three hash-bound manufacturer PDFs only through Hardware Splicer's document-evidence
surface. All eleven hidden claim checks and the hard-truth, mission-progress, and provenance
contracts passed. The overall run remains failed because one candidate disposition, one
mapping serialization rule, and the terminal blocker-grounding contract did not pass. See
`../2026-09-13-RAW-DOCUMENT-V1-RESULT.md` for the bounded interpretation and nonclaims.

`2026-09-13-raw-document-v2` passed all four generic contracts and corrected v1's
candidate-disposition and terminal-grounding failures. It still failed the combined
experiment because the raw adjudicator required normalized DUT strings `DI_IO0` and
`DO_IO1`, while Astra used the datasheet-native aliases `DI` and `DO`. All eleven hidden
document claims otherwise passed every adjudication check. See
`../2026-09-13-RAW-DOCUMENT-V2-RESULT.md`.
