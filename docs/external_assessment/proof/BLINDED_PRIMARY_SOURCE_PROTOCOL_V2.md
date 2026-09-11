# Blinded primary-source protocol v2

Status: prepared; no live Astra inference has been run for either v2 case.

## Why v2 exists

Milestone A (`spi-flash-adapter-primary-sources-v1`) correctly separated the evaluator
commit from the evidence commit, but it was not answer-blind. The canonical starting
snapshot placed `engineeringSourceAdjudication` in the model-visible mission. That object
contained supported conclusions, required unresolved facts, and forbidden claims.

This does not erase Milestone A's process/provenance result: Astra still had to invoke the
product surface, persist attributable canonical state, retain closed physical authority,
and pass the structural checks. It does limit what the run demonstrates about independently
discovering the candidate dispositions and blockers.

Milestone A and its proof bundle remain immutable historical artifacts. V2 uses new case
identities rather than silently changing the original case.

## Cases

### `spi-flash-adapter-primary-sources-blind-v2`

The model sees the same frozen sources and page-addressed claims, but it does not see
`engineeringSourceAdjudication`, supported conclusions, forbidden claims, evaluator metrics,
or observer expectations. Those remain in `ReplayCase.metadata`, which is written only to
the observer manifest and denied to the model filesystem.

### `spi-flash-adapter-primary-sources-blind-v2:identity-conflict`

The model sees two additional source claims over the same subject and predicate:

- declared current project identity: `W25Q128JW`;
- lower-authority proposed/advisory procurement transcription: `W25Q128JV`.

The visible snapshot does not declare an `engineeringSourceConflict`, prescribe a winner,
or include the observer conflict rubric. The existing source-graph logic independently
detects the disagreement because the claims share `physical-dut/component_identity` and
have different values.

Before any live run, the observer-only evaluator requires:

- preservation and explicit use of both source and claim identities;
- preservation of declared-over-proposed authority ordering;
- an explicit persisted identity conflict;
- no silent selection of JV as the resolved physical identity;
- physical marking/package verification as a resolution action;
- a retained identity blocker;
- valid source/claim references;
- closed physical authority.

The evaluator is implemented in
`codex_astra_identity_conflict_adjudication.py`. A passing result will not establish the
physical DUT identity, electrical correctness, or physical authority.

## Execution rule

Do not run the five-case matrix yet. The next paid inference, if performed, is exactly one
identity-conflict v2 run. Before launching it:

1. freeze and externally timestamp the evaluator commit;
2. verify all model-visible files contain no observer rubric or expected disposition;
3. use the context profile to replace repeated broad operation discovery with a compact,
   task-scoped route;
4. retain the raw PDF capture outside model-visible storage;
5. publish success or failure with the same hash-accounted proof-bundle process.
