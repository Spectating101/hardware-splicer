# Codex / Astra clean-room runbook

**Status:** zero-inference staging. No Astra run is authorized by this document.

## Objective

Exercise one Hardware-Splicer frozen case with `gpt-6-astra` through a
ChatGPT-authenticated Codex client while keeping the model blind to HS source code,
tests, evaluator metadata, prior answers, unrelated MCP servers, and the public web.

The live path is:

```text
model-visible mission workspace
        ↓
ChatGPT-authenticated Codex / gpt-6-astra
        ↓
canonical local hs-backend-mcp (STDIO)
        ↓
canonical Hardware-Splicer FastAPI/backend state
        ↓
Codex JSONL trace
        ↓
offline Codex clean-room audit + existing HS external MCP truth audit
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
6. the model-visible workspace and HS repository are disjoint in both directions;
7. no inference or provider model probe has been performed by the preflight.

The preflight inspects authentication mode only. It does not read, copy, print, or persist
authentication credentials.

## Install the canonical MCP surface

From the HS checkout being evaluated:

```bash
python -m pip install -e '.[backend-mcp]'
```

The existing canonical MCP contract remains authoritative. The Astra lane does not add a
second hardware backend.

## Create a clean-room workspace

Use a directory that is neither inside the HS repository nor an ancestor of it.

Example:

```bash
mkdir -p /tmp/hs-astra-case-001
```

The eventual model-visible workspace should contain only inputs intentionally exposed to
the external operator, such as `MISSION.txt` and later approved render images. Do not put
case IDs, equivalence labels, perturbation labels, evaluator notes, source code, hidden
tests, expected answers, or prior run traces there.

## Zero-inference preflight

Assuming the model-visible mission has already been written to
`/tmp/hs-astra-case-001/MISSION.txt`:

```bash
python scripts/preflight_codex_astra.py \
  --workspace /tmp/hs-astra-case-001 \
  --hs-repo-root "$PWD" \
  --mission-file /tmp/hs-astra-case-001/MISSION.txt \
  --emit-launch-plan \
  --report-file /tmp/hs-astra-preflight.json
```

This command may execute only local client checks such as `codex --version` and
`codex login status`. It does **not** invoke Astra, contact HS through MCP, or consume a
model turn. A passing report therefore says nothing about Astra competence or even whether
Astra has completed account rollout for this particular client.

## Generated Codex policy

The launch plan uses ephemeral `-c` overrides instead of modifying the user's normal Codex
configuration. `codex exec --ignore-user-config` still uses existing Codex authentication
but ignores normal user configuration for the model session.

The generated experiment policy includes:

- `forced_login_method = "chatgpt"`;
- model `gpt-6-astra` at low reasoning effort initially;
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
- bounded MCP output tokens and tool timeouts.

The execution environment also removes `OPENAI_API_KEY`. There is no automatic fallback
from unavailable Codex/Astra to the billable Responses API.

## Why the observer still rejects non-MCP tools

Codex is an agent runtime and may expose native command/file capabilities depending on
its current implementation. Filesystem and network restrictions make those capabilities
non-useful for escaping the clean room, but the experiment uses a stronger rule:

> a clean-room HS case is valid only when the engineering work is performed through the
> canonical HS MCP gateway.

`src/hardware_splicer/codex_exec_trace.py` therefore treats any observed
`command_execution`, `file_change`, `web_search`, or `collab_tool_call` item as experiment
contamination. Unknown future item types also fail closed until reviewed. A call through a
foreign MCP server or a tool outside the four-tool HS allowlist fails the same contract.

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
- `codex_hard_truth_contract_pass` — the existing contract **plus** Codex clean-room
  integrity.

Only the second is sufficient for an Astra-in-Codex clean-room result.

## Offline trace audit

After a deliberately authorized live run has written `CODEX_ASTRA_TRACE.jsonl`, audit it
outside the model turn:

```bash
python scripts/audit_codex_astra_trace.py \
  --trace-file /tmp/hs-astra-case-001/CODEX_ASTRA_TRACE.jsonl \
  --expected-project-id <opaque-experiment-project-id> \
  --snapshot-file <exact-product-visible-snapshot.json> \
  --out /tmp/hs-astra-case-001/CODEX_ASTRA_AUDIT.json
```

The audit command performs no Codex, provider, or MCP network I/O. It derives the allowed
source identities from the exact product-visible snapshot and then applies both the Codex
clean-room checks and the existing HS outer truth audit.

## First live-run rule

When a live run is eventually authorized, execute exactly **one frozen case** first.
Do not run the ten-case corpus in the first attempt.

After that single case:

1. preserve the JSONL trace and audit artifact;
2. inspect actual Work/Codex allowance usage;
3. inspect whether any non-MCP tool appeared;
4. inspect MCP result semantics and final canonical project state;
5. decide whether a second case is justified.

The experiment should stop rather than switching to an API key if Astra is unavailable,
account rollout is incomplete, MCP initialization fails, or the clean-room controls do not
hold.

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
- final project-state correctness;
- visual-to-geometry correctness;
- physical correctness;
- physical authority.

No Astra inference was used to create or validate this runbook.
