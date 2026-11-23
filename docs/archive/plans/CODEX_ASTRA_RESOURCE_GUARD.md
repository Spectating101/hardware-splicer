# Codex / Astra resource guard

**Status:** software-only hardening. This document does not authorize a live Astra run.

The canonical future live entrypoint for the one-case Astra experiment is:

```bash
python scripts/run_budgeted_codex_astra_case.py \
  --manifest /path/to/observer/CASE_MANIFEST.json
```

If `--backend-command` is supplied, it must name the raw canonical
`hs-backend-mcp` executable. Never pass an existing budget proxy or governed launcher;
this entrypoint creates the one and only governor layer itself and rejects nested
governors before any model execution.

Dry-run is the default. A live turn still requires the exact existing allowance acknowledgement:

```bash
python scripts/run_budgeted_codex_astra_case.py \
  --manifest /path/to/observer/CASE_MANIFEST.json \
  --execute \
  --confirm-codex-allowance I_ACCEPT_CODEX_ALLOWANCE_USAGE
```

Do not use `scripts/run_codex_astra_case.py` directly for a future live experiment. That
script remains the delegated one-shot implementation; the budgeted front door is what
forces its MCP command through the resource governor.

## Hard exposure limits

The wrapper does not offer a cost estimate as a guarantee. It enforces deterministic
limits that bound the amount of agent looping we permit before the experiment is invalid:

- maximum wall-clock runtime: **300 seconds**;
- maximum MCP `tools/call` requests: **20**;
- maximum `hs_backend_call` requests: **8**;
- maximum one MCP client message: **262,144 bytes**;
- exactly the four canonical HS gateway tool names remain allowed;
- any malformed, oversized, unknown-tool, or over-budget request terminates the governed
  MCP child and fails the session closed;
- no direct API fallback is permitted.

The one-shot MCP launcher is created in a randomized mode-`0755` traversal directory
beneath `/tmp`, which contains only a mode-`0700` launcher and no credentials. Codex's
Linux sandbox needs parent-directory traversal before it can apply the explicit read
grant to the launcher. Codex also protects home/cache paths from local command execution
even when a leaf file is listed in a permission profile, so the launcher must not be
emitted beneath a user cache directory.

Protocol initialization, notifications, and tool-list discovery do not consume the tool
budget because they are transport setup rather than agent engineering work.

## Architecture

```text
Codex / Astra
    |
    | stdio MCP
    v
codex_budgeted_mcp_proxy
    |  hard request/tool/backend-call counters
    v
canonical hs-backend-mcp
    v
canonical Hardware-Splicer FastAPI / ProjectStore
```

The governor does not duplicate any Hardware-Splicer operation, project truth, evidence
rule, or physical-authority decision. It only decides whether another MCP request is
allowed to reach the canonical child process.

The launcher preserves the invoking virtual environment's `python` path instead of
resolving its interpreter symlink to the system Python. This keeps the installed governor
package available even when Codex strips ambient Python import-path variables from the
MCP child environment.

## What the limits do and do not prove

These limits bound **wall-clock and MCP-loop exposure** for a single prepared case. They do
not produce an exact token or Codex-allowance ceiling: the model can consume different
amounts of reasoning/context inside the same number of calls, tool outputs vary in size,
and allowance accounting remains external to HS.

Accordingly, even a successful one-case run must still be followed by inspection of the
actual account-visible Codex usage before another case is considered.

The resource guard grants no physical authority and says nothing about engineering
correctness, fabrication readiness, model competence, or the adequacy of the final design.
