# Raw-document Astra v3 experiment

Status: preregistered implementation; no v3 live result exists at this revision.

## Research question

Can Astra produce a complete, attributable, authority-bounded pre-fabrication result from
the raw manufacturer documents when the evaluator treats documented signal-label aliases
as the same electrical signal?

V1 and v2 remain immutable failed samples. V3 is a new case and permits one new live run.

## Frozen execution

- Case ID: `spi-flash-adapter-raw-documents-blind-v3`
- Model: `gpt-6-astra`
- Reasoning effort: `low`
- Transport: ChatGPT-authenticated Codex through the canonical HS MCP backend
- Network: disabled inside the clean-room session
- API fallback: forbidden
- Wall-clock ceiling: 300 seconds
- MCP tool-call ceiling: 40
- Canonical backend-call ceiling: 36
- Physical authority: false

The complete model-visible snapshot and developer instructions are byte-for-byte identical
to v2. The same PDFs, hashes, questions, hidden expected pages, semantic targets, electrical
conclusions, generic contracts, and nonclaims remain in force.

## Sole evaluator change

Before comparing the TXU0304 logical mapping, the v3 observer normalizes these DUT-side
datasheet function labels:

| Accepted label | Compared as |
| --- | --- |
| `CLK` | `CLK` |
| `/CS` | `/CS` |
| `DI`, `DI(IO0)`, `DI_IO0` | `DI_IO0` |
| `DO`, `DO(IO1)`, `DO_IO1` | `DO_IO1` |

Whitespace inside a DUT label is ignored and matching is case-insensitive. Host-side signal
identities are not aliased. No arbitrary fuzzy matching or model-generated alias is accepted.
The observer records `mapping_alias_policy: datasheet_function_aliases_v1` in the result.

This change follows the v2 observation that Astra persisted `DI` and `DO`, labels that the
same frozen W25Q128JW document defines as the standard-SPI data input and output functions.
V2 is not rescored. The alias policy is frozen before v3 execution.

## Acceptance criteria

A v3 pass still requires every v2 criterion:

- all four generic truth/progress/provenance/final-report contracts;
- deterministic package export and final canonical readback;
- all eleven claims present exactly once and correctly source-, page-, hash-, quote-,
  semantic-, origin-, authority-, and review-anchored;
- all eleven claims referenced with zero assurance issues;
- direct 3.3 V connection rejected;
- TXU0304 preferred only at family level and mapped across the same four signal functions;
- incompatible single-device SN74AXC4T245 topology rejected;
- every required blocker preserved;
- independent signoff false, physical correctness `UNPROVEN`, and no physical authority.

The alias policy cannot rescue a wrong direction, missing signal, extra/missing mapping row,
wrong host identity, wrong candidate disposition, unsupported claim, provenance failure, or
authority violation.

## Claim boundary

A pass would establish the first complete HS raw-document existence proof under the frozen
contracts. It would not establish independent EE validation, visual PDF comprehension,
source authenticity/currentness, exact physical identity, circuit correctness, bench
behavior, fabrication readiness, or physical authority.
