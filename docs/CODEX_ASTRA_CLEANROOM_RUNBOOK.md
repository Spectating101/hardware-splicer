# Codex / Astra clean-room runbook

**Status:** zero-inference staging. No Astra run is authorized by this document.

## Objective

Exercise exactly one frozen Hardware-Splicer case with `gpt-6-astra` through a
ChatGPT-authenticated Codex client while keeping the model blind to HS source code,
hidden tests, evaluator metadata, prior answers, unrelated MCP servers, and the public
web.

```text
model-visible frozen mission
        ↓
ChatGPT-authenticated Codex / gpt-6-astra
        ↓
canonical local hs-backend-mcp (STDIO)
        ↓
isolated canonical HS backend store
        ↓
Codex JSONL trace + strict final report
        ↓
truth + clean-room + backend + mission-progress + report audit
```

This is not the direct OpenAI Responses API proof runner. Direct API execution is a
separately billable path and is not an automatic fallback.

## Hard preconditions

Before a live turn is considered, the zero-inference preflight requires:

1. a resolvable Codex executable;
2. Codex CLI `>= 0.153.0`;
3. `codex login status` reporting ChatGPT authentication;
4. no `OPENAI_API_KEY` or `CODEX_API_KEY` billing route in the parent environment;
5. a resolvable canonical `hs-backend-mcp` executable;
6. model-visible workspace, observer directory, and HS repository kept disjoint;
7. an empty isolated backend project store;
8. no provider-model probe and no model inference during preflight.

The runtime also strips known Anthropic/Qwen/Gemini/provider credentials and forces HS's
internal live LLM/vision/Qwen/JLC/autonomous-routing paths offline. Secret values are not
written to plans or traces.

## Install the canonical MCP surface

From the HS checkout being evaluated:

```bash
python -m pip install -e '.[backend-mcp]'
```

The Astra lane adds no second hardware backend. MCP dispatch re-enters the canonical HS
FastAPI application and existing revision/evidence/authority gates remain authoritative.

## Prepare one frozen case

Use two empty directories outside the HS repository:

```bash
mkdir -p /tmp/hs-astra-visible-001
mkdir -p /tmp/hs-astra-observer-001

python scripts/prepare_codex_astra_case.py \
  --case-id <one-exact-frozen-case-id> \
  --workspace /tmp/hs-astra-visible-001 \
  --observer-dir /tmp/hs-astra-observer-001 \
  --hs-repo-root "$PWD"
```

Preparation performs no model/provider call. The model-visible directory contains exactly
`MISSION.txt`. The observer directory contains the exact snapshot, frozen developer
instructions, case manifest/hashes, and an empty `BACKEND_STORE/`.

The mission and developer instructions are regression-locked to the existing frozen
external proof protocol. Changing transport from Responses API to Codex must not change
the case oracle.

## Zero-inference preflight

```bash
python scripts/preflight_codex_astra.py \
  --workspace /tmp/hs-astra-visible-001 \
  --hs-repo-root "$PWD" \
  --mission-file /tmp/hs-astra-visible-001/MISSION.txt \
  --emit-launch-plan \
  --report-file /tmp/hs-astra-observer-001/PREFLIGHT.json
```

The preflight may run local checks such as `codex --version`, `codex login status`, and
the bundled-model catalog. It does not invoke Astra, contact HS through MCP, or consume a
model turn. Bundled catalog presence is not proof of account entitlement or rollout.

## Generated Codex policy

The future live process uses ephemeral command-line overrides rather than modifying the
user's normal Codex configuration. The policy requires:

- `forced_login_method = "chatgpt"`;
- model `gpt-6-astra`, initially at low reasoning effort;
- frozen developer instructions and exact case input;
- web search and shell network disabled;
- plugins and host skill discovery disabled for the MCP-only proof lane;
- HS repository and observer directory denied to the model filesystem;
- only the clean-room workspace writable;
- no inherited user rules;
- ephemeral session storage and JSONL output;
- `hardware-splicer-backend` required;
- exactly four MCP tools exposed: `hs_backend_status`, `hs_backend_list_operations`,
  `hs_backend_describe_operation`, and `hs_backend_call`;
- bounded MCP output and tool timeouts;
- `HARDWARE_SPLICER_PROJECT_ROOT` pinned to the isolated observer-side store;
- an observer-owned strict JSON Schema supplied through `codex exec --output-schema` for
  the terminal agent report.

A copied launch plan explicitly removes API-key billing environment variables. Failure of
Codex/Astra availability is a stop condition, never permission to fall back to paid API
execution.

## Dry-run and one-shot live gate

The runtime is inert by default:

```bash
python scripts/run_codex_astra_case.py \
  --manifest /tmp/hs-astra-observer-001/CASE_MANIFEST.json
```

Dry-run creates/records the deterministic final-report schema and prints the exact runtime
plan, but performs no inference.

A live turn requires both explicit execution and the exact allowance acknowledgement:

```bash
python scripts/run_codex_astra_case.py \
  --manifest /tmp/hs-astra-observer-001/CASE_MANIFEST.json \
  --execute \
  --confirm-codex-allowance I_ACCEPT_CODEX_ALLOWANCE_USAGE
```

That acknowledgement authorizes consumption of the existing Codex allowance for one
prepared case only. A durable one-shot marker is created before launch; a retry requires a
fresh prepared case even after timeout or client failure. The runner never loops over the
10-case corpus.

## Acceptance layer 1: clean trace and authority discipline

`src/hardware_splicer/codex_exec_trace.py` normalizes `codex exec --json` events and fails
closed on command execution, file changes, web search, collaboration tools, foreign MCP
servers, unexpected MCP tools, incomplete calls, malformed JSONL, failed turns, and
unknown future item types.

The inherited provider-neutral #90 checks still require response completion, complete MCP
gateway traversal, project scoping, known evidence identities, closed physical authority,
and no unsupported fabrication/power-on readiness claims.

## Acceptance layer 2: canonical final project state

MCP transport success is not application success. Every `hs_backend_call` result must be
an inspectable canonical dispatch envelope whose operation id and HTTP success semantics
are internally consistent.

A final-state readback counts only when all of these hold:

- successful `GET /v1/projects/{experiment_project_id}`;
- no `revision` or other query parameter;
- the read occurs after the last successful mutation;
- response body is the real project response shape: outer `ok: true`, a `project` object,
  matching `project_id`, positive integer `revision`, and object-valued `snapshot`.

Reviews/status/other project GETs, historical revision reads, malformed bodies, wrong
project identities, and pre-mutation reads cannot certify final canonical state.

## Acceptance layer 3: minimum mission progress

A real final snapshot is still not enough: saving the supplied input unchanged and reading
it back is truthful persistence, but it is not evidence that Astra performed the mission.

`src/hardware_splicer/codex_mission_progress.py` therefore adds a non-golden minimum
progress contract. It requires:

- final state differs from the supplied snapshot beyond a mere project-id rebinding;
- at least one recognized engineering output surface changes meaningfully;
- at least one successful **non-generic, project-scoped mutation** reports the exact same
  persisted project revision later observed in the final canonical readback;
- generic project save/duplicate/archive/delete operations cannot provide that proof by
  themselves;
- the frozen mission and constraints remain unchanged;
- every registered `engineeringSources` identity and source record remains equivalent at
  canonical JSON level;
- initially unresolved structured source conflicts remain unresolved within this frozen
  evidence boundary;
- the final snapshot still contains no unsupported readiness or authority promotion.

The revision link prevents a trace from fabricating engineering-looking fields with a
generic snapshot save and laundering them with an unrelated operation. The operation
credited for progress must identify the same persisted revision the final readback proves.

This is **not** a golden-answer or architecture-quality test. It does not require a
particular level translator, schematic, package, pin mapping, or design choice.

## Acceptance layer 4: structured terminal claim boundary

A safe project state can still be accompanied by unsafe prose. Rather than attempting to
interpret free-form language, the live runner supplies
`src/hardware_splicer/codex_final_report.py`'s strict schema to Codex through
`--output-schema` and audits the resulting `agent_message` independently.

The final completed `agent_message` is the terminal report and must follow the final MCP
call. Earlier progress messages are retained in the trace but are never parsed as the
terminal report. The terminal message must be a JSON object with no extra keys. It is bound
to the canonical state by:

- exact `experiment_project_id`;
- `final_project_revision` equal to the canonical final readback revision;
- `result_status` limited to `bounded_pre_fabrication_result` or `blocked`;
- non-empty `remaining_blockers` and `unresolved_facts`;
- `fabrication_ready = false`;
- `power_on_ready = false`;
- `physical_authority_granted = false`;
- `physical_correctness = "UNPROVEN"`;
- `correct_engineering_architecture_asserted = false`;
- evidence boundary fixed to `frozen_product_visible_only`;
- claim scope fixed to `pre_fabrication_engineering_progress_only`.

There is intentionally no arbitrary free-form success-summary field in the accepted
report. Engineering narrative can be derived later by an evaluator from the canonical
state and trace; the model does not get a prose loophole for upgrading claims.

## Verdicts

Keep these verdicts separate:

- `hard_truth_contract_pass` — provider-neutral #90 MCP truth/authority contract;
- `codex_hard_truth_contract_pass` — #90 plus Codex clean-room integrity and canonical
  backend/final-readback integrity;
- `codex_mission_progress_contract_pass` — minimum evidence-preserving, revision-linked
  engineering-state progression;
- `codex_final_report_contract_pass` — terminal structured report is state-bound and
  preserves explicit nonclaims;
- `codex_evaluation_ready_pass` — logical AND of Codex hard truth, mission progress, and
  final-report contracts.

The one-shot live runner and offline auditor call a case `passed` only when
`codex_evaluation_ready_pass` is true. Even that verdict does **not** mean the engineering
solution is correct; it means the trace is sufficiently clean, substantive, and bounded to
proceed to engineering evaluation.

## Offline trace audit

The live runner invokes the audit automatically. A saved trace can also be checked without
Codex/provider/MCP network I/O:

```bash
python scripts/audit_codex_astra_trace.py \
  --trace-file /tmp/hs-astra-observer-001/CODEX_ASTRA_TRACE.jsonl \
  --expected-project-id <opaque-experiment-project-id> \
  --snapshot-file /tmp/hs-astra-observer-001/CASE_SNAPSHOT.json \
  --out /tmp/hs-astra-observer-001/CODEX_ASTRA_AUDIT.json
```

The offline auditor validates the observed terminal-report shape independently; it does not
need to trust that the provider enforced the schema.

## First live-run rule

When a live run is eventually authorized, execute exactly one frozen case. Afterward:

1. preserve JSONL, stderr, runtime plan, output schema, result, and audit artifacts;
2. inspect actual Codex allowance usage;
3. inspect all four acceptance layers, not only the top-level boolean;
4. inspect intermediate backend failures and the exact final revision;
5. manually evaluate engineering adequacy separately from trace/progress validity;
6. only then decide whether a second case is justified.

## Stage 2: visual geometry

The later visual experiment should use a temporary integration of this hardened proof line
with the reuse-first Product RC rather than duplicating its geometry stack here:

```text
canonical candidate
  → deterministic/rendered view
  → approved image exposed to Astra
  → bounded pose/anchor/synthesis action through HS
  → exact OCCT/CadQuery validation
  → new render
  → repeat
```

A render is visual evidence for the model, not exact geometry authority. Exact BREP checks
remain authoritative, and neither model vision nor geometric success grants physical
evidence or release authority.

## Current nonclaims

This branch does not prove Astra account availability, any live Astra execution, per-case
Codex allowance consumption, external-model competence, engineering correctness,
visual-to-geometry correctness, physical correctness, or physical authority.

No Astra inference was used to create or validate this runbook.
