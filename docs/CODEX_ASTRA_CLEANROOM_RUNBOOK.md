# Codex / Astra clean-room runbook

**Status:** zero-inference staging. No Astra run is authorized by this document.

## Objective

Exercise one Hardware-Splicer frozen case with `gpt-6-astra` through a
ChatGPT-authenticated Codex client while keeping the model blind to HS source code,
tests, evaluator metadata, prior answers, unrelated MCP servers, and the public web.

The live path is:

```text
model-visible frozen mission
        ↓
ChatGPT-authenticated Codex / gpt-6-astra
        ↓
canonical local hs-backend-mcp (STDIO)
        ↓
isolated canonical HS backend store
        ↓
Codex JSONL trace in observer directory
        ↓
offline Codex clean-room + backend-result + #90 truth audit
```

This is deliberately not the OpenAI Responses API proof runner. The direct API path is
separate billable usage and remains only a compatibility/tripwire surface in this branch.

## Hard preconditions

The zero-inference preflight requires all of the following before a live command is even
considered:

1. Codex executable present;
2. Codex CLI version `>= 0.153.0`;
3. `codex login status` reports `Logged in using ChatGPT`;
4. `OPENAI_API_KEY` is not present in the parent environment;
5. `hs-backend-mcp` is installed and resolvable;
6. model-visible workspace, observer directory and HS repository are disjoint;
7. the isolated HS backend project store is empty;
8. no inference or provider model probe has been performed by the preflight.

The preflight inspects authentication mode only. It does not read, copy, print, or persist
authentication credentials.

## Install the canonical MCP surface

From the HS checkout being evaluated:

```bash
python -m pip install -e '.[backend-mcp]'
```

The existing canonical MCP contract remains authoritative. The Astra lane does not add a
second hardware backend.

## Prepare one frozen case without leakage

Create two empty directories outside the HS repository: one that Astra may see and one
observer-only directory for evaluator metadata, the exact snapshot, backend state and
traces.

```bash
mkdir -p /tmp/hs-astra-visible-001
mkdir -p /tmp/hs-astra-observer-001

python scripts/prepare_codex_astra_case.py \
  --case-id <one-exact-frozen-case-id> \
  --workspace /tmp/hs-astra-visible-001 \
  --observer-dir /tmp/hs-astra-observer-001 \
  --hs-repo-root "$PWD"
```

The preparation command performs no model or provider call. It writes exactly one file to
the model-visible workspace:

```text
MISSION.txt
```

The observer directory receives:

- `DEVELOPER_INSTRUCTIONS.txt` — exact frozen external-runner instructions;
- `CASE_SNAPSHOT.json` — exact product-visible snapshot for offline auditing;
- `CASE_MANIFEST.json` — outer case/equivalence/perturbation metadata and content hashes;
- empty `BACKEND_STORE/` — canonical project storage dedicated to this one experiment.

The Codex mission and developer instructions are regression-locked against the existing
external proof runner for all ten frozen cases. The Astra lane may not silently change the
protocol merely because the transport changed from Responses API to Codex.

## Zero-inference preflight and launch-plan inspection

```bash
python scripts/preflight_codex_astra.py \
  --workspace /tmp/hs-astra-visible-001 \
  --hs-repo-root "$PWD" \
  --mission-file /tmp/hs-astra-visible-001/MISSION.txt \
  --emit-launch-plan \
  --report-file /tmp/hs-astra-observer-001/PREFLIGHT.json
```

This command may execute only local client checks such as `codex --version` and
`codex login status`. It does **not** invoke Astra, contact HS through MCP, or consume a
model turn. A passing report therefore says nothing about Astra competence or even whether
Astra has completed account rollout for this particular client.

## Generated Codex policy

The launch uses ephemeral `-c` overrides instead of modifying the user's normal Codex
configuration. `codex exec --ignore-user-config` still uses existing Codex authentication
but ignores normal user configuration for the model session.

The experiment policy includes:

- `forced_login_method = "chatgpt"`;
- model `gpt-6-astra` at low reasoning effort initially;
- exact frozen rules as Codex `developer_instructions`;
- exact frozen case input as user stdin;
- web search disabled;
- shell network disabled;
- only the clean-room workspace writable;
- explicit read denial for the HS repository path;
- no inherited user rules;
- ephemeral session storage;
- JSONL event output;
- `hardware-splicer-backend` marked required;
- exactly four MCP tools enabled:
  - `hs_backend_status`;
  - `hs_backend_list_operations`;
  - `hs_backend_describe_operation`;
  - `hs_backend_call`;
- MCP calls pre-approved so a noninteractive run cannot hang on an approval prompt;
- bounded MCP output tokens and tool timeouts;
- `HARDWARE_SPLICER_PROJECT_ROOT` pinned to the empty observer-only backend store;
- HS-internal live LLM/vision/Qwen/JLC/autonomous routing surfaces forced offline.

The runtime strips known provider-key environment variables before starting Codex. No
secret value is written to plans or traces. There is no automatic fallback from unavailable
Codex/Astra to the billable Responses API.

## Inert single-case runner

The actual orchestration entrypoint is dry-run by default:

```bash
python scripts/run_codex_astra_case.py \
  --manifest /tmp/hs-astra-observer-001/CASE_MANIFEST.json
```

Dry-run validates the frozen package, empty backend store and local preflight, then prints
the single-case runtime plan. It does not launch Astra.

A live turn can only start when **both** `--execute` and the exact acknowledgement are
present:

```bash
python scripts/run_codex_astra_case.py \
  --manifest /tmp/hs-astra-observer-001/CASE_MANIFEST.json \
  --execute \
  --confirm-codex-allowance I_ACCEPT_CODEX_ALLOWANCE_USAGE
```

That acknowledgement means the user accepts consumption of the existing Work/Codex
allowance for **one** Astra case. It is not permission to run the ten-case corpus and it is
not permission to use API billing.

The runner never loops over multiple cases. It has a hard process timeout, preserves
stdout JSONL/stderr/result artifacts observer-side, and automatically runs the offline
combined audit after Codex exits.

## Why the observer rejects non-MCP tools

Codex is an agent runtime and may expose native command/file capabilities depending on
its current implementation. Filesystem and network restrictions make those capabilities
non-useful for escaping the clean room, but the experiment uses a stronger rule:

> a clean-room HS case is valid only when the engineering work is performed through the
> canonical HS MCP gateway.

`src/hardware_splicer/codex_exec_trace.py` therefore treats any observed
`command_execution`, `file_change`, `web_search`, or `collab_tool_call` item as experiment
contamination. Unknown future item types also fail closed until reviewed. A call through a
foreign MCP server or a tool outside the four-tool HS allowlist fails the same contract.

## Backend-result semantics and final readback

MCP transport success is not the same thing as an HS operation succeeding.
`hs_backend_call` returns a canonical dispatch envelope containing `ok`, HTTP
`status_code`, `operation_id`, method, path and the backend response.

The Codex observer therefore additionally requires:

- every `hs_backend_call` result to decode into a valid canonical dispatch envelope;
- envelope `operation_id` to match the requested operation;
- `ok` to agree with the HTTP status class;
- a successful final canonical project `GET` for the expected opaque experiment project;
- that readback to occur **after the last successful mutation**.

Intermediate 4xx/5xx HS results are retained as evidence and are not automatically fatal.
A model may discover an invalid attempt, correct it and continue. What cannot pass is an
uninspectable backend result or a workflow that mutates state and never reads the resulting
canonical project back.

## What `codex exec --json` gives the observer

Current Codex JSONL emits:

- thread start;
- turn start/completion/failure;
- token usage at turn completion;
- MCP tool items containing server, tool, arguments, result/error, and status;
- command/file/web/collaboration items when those capabilities are used.

The normalizer converts terminal HS MCP items into the response shape consumed by
`external_mcp_trace_audit.v2`. Started MCP calls without a terminal result fail closed.
Malformed JSONL, turn failures, stream errors, and error items also fail the evidence run.

Two verdicts are intentionally retained:

- `hard_truth_contract_pass` — the existing provider-neutral #90 MCP truth contract;
- `codex_hard_truth_contract_pass` — the existing contract plus Codex clean-room and
  backend-result/final-readback integrity.

Only the second is sufficient for an Astra-in-Codex clean-room result.

## Offline trace audit

The single-case runner invokes this automatically after a live process. It is also
available independently:

```bash
python scripts/audit_codex_astra_trace.py \
  --trace-file /tmp/hs-astra-observer-001/CODEX_ASTRA_TRACE.jsonl \
  --expected-project-id <opaque-experiment-project-id> \
  --snapshot-file /tmp/hs-astra-observer-001/CASE_SNAPSHOT.json \
  --out /tmp/hs-astra-observer-001/CODEX_ASTRA_AUDIT.json
```

The audit command performs no Codex, provider, or MCP network I/O.

## First live-run rule

When a live run is eventually authorized, execute exactly **one frozen case** first.
Do not run the ten-case corpus in the first attempt.

After that single case:

1. preserve JSONL, stderr, runtime-plan, result and audit artifacts;
2. inspect actual Work/Codex allowance usage;
3. inspect whether any non-MCP tool appeared;
4. inspect intermediate backend failures and the final canonical readback;
5. inspect the engineering result manually rather than equating audit pass with correctness;
6. decide whether a second case is justified.

The experiment stops rather than switching to an API key if Astra is unavailable, account
rollout is incomplete, MCP initialization fails, or the clean-room controls do not hold.

## Stage 2: visual geometry

The later visual experiment should be built on a temporary integration of the hardened
proof line and the reuse-first Product RC rather than duplicating the RC's geometry stack
inside this branch.

Target loop:

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
remain authoritative for geometry, and neither model vision nor geometric success grants
physical evidence or release authority.

## Current nonclaims

This runbook and its code do not prove:

- Astra is currently available on the user's local Codex installation;
- Astra has executed any HS case;
- the Codex allowance cost of one HS case;
- external-model competence;
- final project-state engineering correctness;
- visual-to-geometry correctness;
- physical correctness;
- physical authority.

No Astra inference was used to create or validate this runbook.
