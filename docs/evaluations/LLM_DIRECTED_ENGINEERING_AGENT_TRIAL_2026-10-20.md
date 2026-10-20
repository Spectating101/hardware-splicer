# Hardware Splicer: LLM engineering agent instead of a fixed function template

Date: 2026-10-20. Optiplex. Isolated draft branch.
Objective: let a connected LLM investigate an unfamiliar machine, reason
about repurposing donor components, propose interfaces, request missing
measurements, and revise in response to independent engineering gates.

## Implemented

The new model-directed controller has a JSON LLM boundary (Ollama
loopback adapter) and a bounded action set:
inspect_donors, inspect_requirements, evaluate_design,
prepare_concept_cad, finish.

The model selects tools and provides architecture hypotheses. The host
creates separate receipts, checks donor ID and original exact source
quotes, checks proposed interfaces, independent stop, measurement plan,
alternative architecture and physical-evidence boundaries.
There is no arbitrary shell, browsing, power-on or printer control.

A separate model-independent stepwise SDK/MCP tool lets any CONNECTED
model drive the same actions without a local API key or heavy model
on the Optiplex. Start by sending engineering_case; continue with
the returned session_state and model_decision(action,reason,optional
design) through HS MCP tool hs_engineering_agent_session. A caller-supplied
prior pass status is recomputed and cannot authorize fabricated physical
claims. Sessions are bounded to ten steps.

Important: the returned session state is a JSON transport convenience,
not an authenticated append-only durable audit store. Genuine hardware
measurements require separate signed instrument/specimen records.

## Unfamiliar optical sorter investigation

Goal: make a stationary low-voltage table-top two-bin optical sorting
machine from four unowned faulty donor categories: printer, webcam,
desk fan and old router. No motor, electrical, mechanical or imaging
measurements are present. No item is declared physically reusable.

A GPT-6 design was authored during this interactive conversation, NOT
through local Ollama. The provisional design is a gravity-feed and
indexed-inspection path with an optical window and two-way chute.
It includes seven functional blocks, three *hypothetical* donor uses,
two new-component needs, four unknown interfaces, four actionable
donor measurements and two alternative mechanical architectures.
Unknown fan motor is not selected as a verified low-voltage actuator.
All physical/electrical/stock authority remains false.

The original capability claim quotations for reused donor hypotheses
were checked against the case intake; there is no new guessed pinout.
The independent structural/source/evidence oracle accepted this
conditional proposal, NOT its real-world engineering feasibility.

Six genuine HS MCP handler calls were exercised using the GPT-6-authored
decisions: start, inspect_donors, inspect_requirements, evaluate_design,
prepare_concept_cad, finish. The CAD request was BLOCKED because no
donor geometry or explicit concept envelope had been established.
The result retained zero physical measurements and no build authority.

References:
- AGENT_OPTICAL_SORTER_CONDITIONAL_REFERENCE_2026-10-20.json
- GPT6_CONNECTED_AGENT_TOOL_SESSION_2026-10-20.json

This replay is a conversation-assisted LLM/tool demonstration,
NOT a fully autonomous background run.

## Local unattended inference: FAILED, do not call green

Local installed models Qwen2.5:7b-instruct and 1.5b-instruct were
reachable. Short isolated model responses succeeded: 7B roughly 37 s
for a minimal JSON output, 1.5B roughly 7.5 s.

But complete unfamiliar engineering prompts failed:
- Qwen 7B: first action timed out after 150 seconds; no trace output.
- Qwen 1.5B: first action timed out after approximately 150 seconds.
- Qwen 1.5B compact request: first action timed out after 85 seconds.
- Claude Code OAuth had expired and could not refresh.
- Gemini CLI smoke request also timed out.

Observed host: CPU load over 30, physical RAM 28/31 GiB consumed,
swap 24/24 GiB full, several Ollama models loaded concurrently.
The first two 1.5B failures have exact machine-readable receipts:
- OLLAMA_QWEN15_AGENT_TIMEOUT_2026-10-20.json
- OLLAMA_QWEN15_COMPACT_TIMEOUT_2026-10-20.json

The executor now catches model provider failures without falsely
claiming a completed investigation.

## Adversarial acceptance

At least 26 new tests falsify manufactured evidence, fake physical
stock, invented donor identities, unsupported source quotation,
wrong mobility domain, missing measurements, ignored stop design,
out-of-budget model calls, model-generated shell actions, and spoofed
prior audit success booleans.

This oracle verifies a bounded proposed design's structural/evidence
integrity only. It does NOT verify actual compatibility, engineering
quality, physical dynamics, working circuits, or successful assembly.

## Next technical requirements

1. Use a capable connected model through the stepwise HS MCP tool
   rather than requiring local heavy inference.
2. Add a durable server-side append-only state/evidence log.
3. Equip the agent with actual image and instrument readouts linked to
   specific acquired donor IDs, instead of marketplace descriptions.
4. Allow the model to invoke SolidCraft, PartCAD, KiCad and SPICE
   through typed evidence-safe tools; validate outputs independently.
5. Test the complete process on an unfamiliar goal under a real
   connected model, including rejected and revised architectures.
6. Physical capability remains blocked pending acquired hardware,
   measured interface contracts, safe assembly and real tests.

Verdict: model-driven architecture and tool boundaries implemented;
interactive GPT-6 decision/HS MCP tool loop demonstrated; unattended
local-model engineering run still BLOCKED by inference timeouts.
