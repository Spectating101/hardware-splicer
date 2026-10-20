# Genuine ChatGPT-authenticated Codex engineering-agent trial

Date: October 20, 2026. Run on authorized Linux Optiplex.

## CLI restoration and authentication

Global Codex package was missing and the global npm folder was not
writable. Installed official Codex v0.163.0 in a stable unprivileged
location at ~/.local/share/hardware-splicer/codex-chatgpt/ .
The native Codex CLI reports Logged in using ChatGPT.
Live inference succeeded using the locally configured gpt-6.1-sol model.

HS integration explicitly excludes API-key environment variables,
uses ephemeral sessions, read-only sandbox, no auto approvals,
ignores inherited user tool registrations and rules, and does not
pass any commands to the model for execution. HS executes only its
bounded source/design actions. No paid API key was supplied.

## Real live engineering experiment (not a mock)

Unseen stationary barcode feeder concept, with SIX actual bounded
public page receipts for the LS2208 scanner, Epson LQ-680 printer,
QNAP TS-219P II NAS board, and manufacturer family references.
No listed donor is in our possession and none is bench-tested.

Genuine model-selected tool sequence:
1. inspect_sources -> six actual source records received by model.
2. derive_functions -> stationary equipment functional decomposition.
3. audit_candidate -> real HS plan and independent provenance oracle,
   source integrity true, conditional candidate accepted true,
   physical build authorization false.
4. finish -> explicit provisional engineering design and evidence gaps.

The model's final output explains incompatible scanner interface
alternatives, lack of a verified NAS motor-control path, unverified
printer mechanics and power, absent completion feedback and missing
independent safety stop. It does not claim physical construction.

Total approximately 169 seconds, status MODEL_FINISHED. Actual
model reasoning with three executed source/design tool calls. All
actual full model decisions, tool receipts and SHA256 values are saved
in CODEX_CHATGPT_LIVE_ENGINEERING_TRIAL_2026-10-20.json.

## Default agent integration

The SDK and MCP hs_run_reasoning_engineering_agent now prefer the
codex_chatgpt provider. This uses the CLI at the stable installed path
or the operator-controlled HARDWARE_SPLICER_CODEX_CHATGPT_JS environment.
No hidden Qwen fallback and no invented model output on errors.
Legacy text-provider route must be selected explicitly.

The scripts/run_codex_engineering_reasoning_trial.py runs the actual
Codex model over a full case with bounded tools. The native CLI adapter
never assumes or asks for API keys. Test-suite provider doubles are
distinct from the real run and cannot claim a live model.

## Limitations

This is one real successful CONDITIONAL investigation, not evidence
that HS independently designed or built a functional multi-donor device.
The source references are not specimen measurements, mechanical fit
is unknown, and motion/power/fabrication remain blocked.
The old Qwen route still had a qwen_http_error. Nested model calls
inside canonical planning may require further isolation so the outer
Codex operator remains the only reasoning model in future evaluations.

A general AI engineering agent needs additional hard unseen tasks,
real measured source-to-component identity and instrument feedback,
actual 3D enclosure fits, multiple engineering trade-off revisions
and externally graded hardware functionality.

## Independent live SDK default-path probe

A second real model invocation used the NORMAL HS SDK entrypoint with
no explicit provider and no explicit CLI path. Codex was found at the
persistent user-owned default location. With max_steps=1 it selected
inspect_sources and executed that genuine HS tool successfully.
Its status was STEP_BUDGET_EXHAUSTED, not MODEL_FINISHED, exactly as
expected for an intentionally one-step trial. No physical authorization.
The raw output is in CODEX_CHATGPT_LIVE_SDK_DEFAULT_PROBE_2026-10-20.json.
