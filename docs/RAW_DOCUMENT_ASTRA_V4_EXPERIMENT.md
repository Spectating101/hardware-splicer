# Raw-document Astra v4 experiment

Status: preregistered implementation; no v4 live result exists at this revision.

## Research question

Can the complete v3 raw-document task pass in a Codex clean room that also suppresses
host-global `AGENTS.md` instruction discovery?

V1, v2, and v3 remain immutable failed samples. V4 permits one new live run because v3
identified a runner-isolation defect outside the engineering task.

## Frozen execution

- Case ID: `spi-flash-adapter-raw-documents-blind-v4`
- Model: `gpt-6-astra`
- Reasoning effort: `low`
- Transport: ChatGPT-authenticated Codex through the canonical HS MCP backend
- Network: disabled inside the clean-room session
- API fallback: forbidden
- Wall-clock ceiling: 300 seconds
- MCP tool-call ceiling: 40
- Canonical backend-call ceiling: 36
- Physical authority: false

The model-visible mission, project snapshot, and developer instructions are byte-for-byte
identical to v3. The raw adjudicator and `datasheet_function_aliases_v1` mapping policy are
also unchanged.

## Sole runner change

The Codex client is launched with these additional official configuration overrides:

- `project_doc_max_bytes=0`
- `project_doc_fallback_filenames=[]`

Codex already runs with `--ignore-user-config`, `--ignore-rules`, plugins disabled, host
skill discovery disabled, web disabled, and a filesystem policy that denies the HS repository
and observer directory. V4 adds the missing project-instruction boundary. The no-shell audit
is not relaxed: any `command_execution`, even a denied or read-only attempt, still fails the
clean-room contract.

The [official Codex configuration reference](https://developers.openai.com/codex/config-reference/)
describes `project_doc_max_bytes` as the maximum bytes read from `AGENTS.md` when building project instructions and
`project_doc_fallback_filenames` as the additional filenames tried when `AGENTS.md` is absent.

## Acceptance criteria

A v4 pass requires both:

1. every generic hard-truth, clean-room, mission-progress, provenance, final-report,
   readback, and package contract; and
2. every v3 raw-document extraction, semantic, architecture, mapping, blocker, review, and
   authority check.

No shell or non-HS tool is allowed. No failed backend operation is allowed. No criterion is
weakened to accommodate v3.

## Claim boundary

A pass would establish a complete raw-document existence proof for this case, including
clean-room tool discipline. It would not establish independent EE validation, visual PDF
comprehension, source authenticity/currentness, exact physical identity, circuit correctness,
bench behavior, fabrication readiness, or physical authority.
