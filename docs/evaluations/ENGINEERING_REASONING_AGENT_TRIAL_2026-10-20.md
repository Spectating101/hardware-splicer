# First LLM-directed Hardware Splicer engineering loop

Date: 2026-10-20. Reuses existing text provider adapter and HS
tools to let a model choose source inspection, functional decomposition,
independent candidate audit or declared-concept casing generation.

## Implementation and controls

The new engineering_reasoning_agent module implements a maximum
six-step loop. Each model-selected action runs a real allowlisted HS
tool and returns its receipt to the next model step. Receipts include
the model reason, source evidence context and hashed tool output.
The agent cannot print, power, move, flash or grant hardware authority.
Its SDK entrypoint and MCP tool are both callable.

## What was actually tested

Four deterministic tests succeeded: real source inspection then
real functional decomposition, with receipts observed before the model
test-double chose a final conditional result; unauthorized firmware
action rejection; unavailable model reporting; MCP tool availability.
These tests prove control flow and tool integration only.

The separate real live-provider invocation against the unfamiliar
stationary label-feeder case FAILED at the first model request with
qwen_http_error. Status MODEL_UNAVAILABLE, zero actual model decisions
and no live-engineering result. This limitation was preserved in the
machine-readable evaluation. No credential values are stored.

## Next

Connect a working authenticated model runtime, ideally using existing
ChatGPT/Codex user allowance without silent paid API requests.
Run unfamiliar repair/splicing cases with tool feedback and independent
engineering evaluation, not a self-reported success score.
