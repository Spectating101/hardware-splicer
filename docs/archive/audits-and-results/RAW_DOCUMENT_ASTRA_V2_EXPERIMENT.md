# Raw-document Astra v2 experiment

Status: preregistered implementation; no v2 live result exists at this revision.

## Research question

Can an external Astra session independently extract all eleven hidden electrical facts
from three hash-bound manufacturer PDFs, turn them into attributable canonical engineering
state, and satisfy the complete Hardware Splicer acceptance contract in one bounded run?

This is a new frozen case, not a relabeling or mutation of raw-document v1. The v1 result
remains failed and is published separately.

## Frozen case

- Case ID: `spi-flash-adapter-raw-documents-blind-v2`
- Model: `gpt-6-astra`
- Reasoning effort: `low`
- Transport: ChatGPT-authenticated Codex through the canonical HS MCP backend
- Network: disabled inside the clean-room session
- API fallback: forbidden
- Wall-clock ceiling: 300 seconds
- MCP tool-call ceiling: 40
- Canonical backend-call ceiling: 36
- Physical authority: false

The document identities, byte hashes, revisions, sizes, page counts, eleven neutral
questions, hidden page expectations, hidden semantic targets, engineering conclusions,
and raw-document adjudicator are unchanged from v1.

## Preregistered v2 protocol delta

V1 revealed three interface/contract ambiguities. V2 changes only the model-visible
serialization instructions and initial blocker catalog:

1. `host` and `dut` in a logical-mapping row must contain bare project signal names.
   Translator pins and route notation belong in rationale.
2. A topology shown by document evidence to be incapable of the required direction split
   must use status `rejected`. `held` is reserved for insufficient evidence.
3. Three already-known assurance limitations are predeclared as blockers: independent
   review is pending, extracted text can misrepresent visual content, and frozen hashes do
   not establish authenticity/currentness/physical identity. Terminal blocker arrays must
   use exact strings from the initial blocker catalog.

These clarifications do not disclose expected pages, values, claim paraphrases, component
conclusions, or evaluator checks. They do not relax any adjudication rule. In particular,
the mapping evaluator still requires the same four exact signal pairs, and the AXC candidate
must still be rejected if its derived topology cannot provide the simultaneous 3+1 split.

## Acceptance criteria

A pass requires every generic contract and every raw-document adjudication check to pass:

- hard truth and authority closure;
- substantive mission progress;
- successful operation-to-state provenance;
- terminal canonical readback and structured final report;
- deterministic package export;
- all eleven claims correctly source-, page-, quote-, and hash-anchored;
- all eleven claims used, still proposed, and still unreviewed;
- zero source-reference issues;
- direct 3.3 V connection rejected;
- TXU0304 preferred only at family level with the exact four-signal mapping;
- the incompatible single-device AXC topology rejected;
- every original implementation/physical blocker preserved;
- independent signoff false and physical correctness `UNPROVEN`.

No rerun under this frozen v2 tag is permitted merely to obtain a better sample. A failing
result remains a failure and must be published or reported as such before any v3 change.

## Claim boundary

Even a full pass would demonstrate governed document extraction and pre-fabrication
reasoning, not an electrically validated design. It would not prove PDF visual comprehension,
source authenticity/currentness, independent EE review, exact physical identities, circuit
correctness, bench behavior, fabrication readiness, or physical authority.
