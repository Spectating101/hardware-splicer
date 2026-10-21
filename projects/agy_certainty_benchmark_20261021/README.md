# Hardware Splicer — high-end model certainty pilot

**Native HS agent trials, 21 October 2026, Optiplex.** This is an evidence-
controlled model comparison, not a fabricated design, contract price forecast,
physical build, model release or production authorization.

## Purpose and actual execution

The existing HS text provider already supported `agy`, but the current CLI
requires `--print=<prompt>` rather than the legacy standalone `--print` flag.
The legacy call failed before receiving any model response. The adapter is now
fixed to use the actual CLI option syntax and to run sandboxed against an
isolated temporary workspace. A stale default model (`gemini-2.5-flash`) is
replaced with one actually listed by the user's `agy models` on Optiplex:
`gemini-3.8-flash-medium`. This does **not** change the chosen model for other
agents that explicitly select their own model.

All comparison sessions used the **actual HS native** `run_ai_project_orchestrator`,
with the same immutable vendor source excerpts and original KiCad mechanical
facts, same prompt and constraints, a five-action limit, and the requested
provider model name. No manufactured hardware was inspected, fabricated or
operated. `agy` provider details and outputs were recorded against the
registered source hash. Copilot CLI was the existing fast baseline.

| Actual model | Four-case source fact checks | Mean elapsed seconds, 4 cases | Original BOM arithmetic challenge |
| --- | ---: | ---: | --- |
| GitHub Copilot CLI (baseline) | 13/13 | 20.7 | Valid, all six fact checks |
| Claude Sonnet 5.5 High | 13/13 | 35.0 | Provider/schema failure; cannot score |
| Claude Opus 5.5 High | 13/13 | 51.4 | Valid, all six fact checks |
| Gemini 4 Argon High | 13/13 | 88.6 | Valid, all six fact checks |

The first four original tasks were: (1) the Holybro X500 V2 manufacturer
motor, ESC and propeller inventory versus **missing motor-arm mounting geometry**;
(2) the iFixit PSP-300x UMD guide versus **unknown actual device condition and
solvent/battery safety**; (3) Prusament ASA manufacturer UV and 93 °C claims
versus **absent standardized HDT and sustained-use tests**; and (4) the real
RPI_DEV KiCad-derived PCB board envelope and Q1 3.6 mm drill versus an
**unsupported four-M3-corner-mount note**.

In all 16 original task sessions, models correctly referenced the supplied
source values, preserved non-authorizing engineering posture and proposed
further validation instead of approving an unmeasured adapter, printed
retention, faulty drive diagnosis or 90 °C sustained thermal enclosure.
There were **no unknown/fabricated source IDs** in the returned canonical
source-ID lists. More citations and longer prose are not a valid surrogate for
verified engineering accuracy or better decision quality.

### Harder financial/evidence reconciliation

The fifth task used HS's own deterministic audit of the original upstream
`therebelrobot/dinodeck-2026` BOM at commit `7762e2f`.

- Published top-level claim: **$140–230**, excluding enclosure.
- Sum of its six published categories: **$193–270**.
- Low-end error **+$53**; upper-end error **+$40**.
- Against provisional **$250** component ceiling, high-end category estimate
  exceeds budget by **$20 before** unquoted shipping, enclosure, tools, tax,
  repairs, returns or labor.

Opus, Argon and Copilot each recovered all six audit facts and explicitly
refused an exact maximum bid, speculative profit guarantee or purchase
approval. Sonnet's fifth response failed the native HS JSON contract after
~29 seconds, so the session is recorded as **not successfully evaluated**.
A subsequent direct Sonnet CLI schema probe reported **individual quota
exhaustion**. Whether that was the proximate cause of the earlier invalid
response was **not independently established**. Thus it should not be
interpreted as proof that Sonnet is intellectually worse on cost arithmetic.

### More important than model eloquence

All four generally reached the correct action: obtain missing original
mechanical/repair/thermal evidence and run appropriate deterministic checks.
The richer models provided more granular safety hypotheses (e.g., print
orientation/creep, PCB component keep-outs, thermal load profiles). However,
**none demonstrated a measurable accuracy or approval-quality advantage on
these five selected cases**. Argon's average latency was over four times the
Copilot baseline, and Opus about 2.5 times. These are observed end-to-end
latencies in this host/provider configuration, not general speed rankings.

**Model routing recommendation for HS:**

1. Keep the existing fast Copilot-backed path for ordinary source summarizing,
   deterministic tool selection and normal engineering source tasks.
2. Offer **Sonnet 5.5** as a selectable cross-disciplinary review model when
   time/quota permits; do not make it a hard dependency given the observed
   provider/schema failure.
3. Reserve **Opus 5.5** as an explicit independent second opinion on difficult
   source conflicts, ambiguous physical safety assumptions or high-value
   decisions. The more expansive review is useful, but does not constitute
   measurement-based verification and did not win these factual tests.
4. Keep **Gemini 4 Argon** as an independent alternative model for genuinely
   hard cases; do not route routine HS work through it without additional
   demonstrated benefit because of the observed latency.
5. Never treat multi-model agreement as engineering clearance: sources can be
   stale or wrong, and no number of agreeing text models substitutes for
   CAD-mating measurements, ERC/DRC, FEM convergence or bench testing.

**Certainty should come from source hashes + deterministic checks + measured
geometry/loads**, while a stronger model is used to *find missing assumptions
and propose the next test*. The current HS project AI sessions already accept
an explicit per-session model, so this routing can be selected without
making Opus the global default.

## Failures and improvements included in this change

- Fixed the exact `agy --print=...` syntax after testing the available Opus,
  Sonnet and Argon endpoints with real response payloads.
- In inference, restricted the CLI to `--sandbox`, disabled slash expansion,
  and changed its subprocess CWD to an empty temporary directory so that
  repository contents are not supplied via ambient project context.
  **The CLI does not currently expose a verified strict no-tools flag**; do
  not overstate tool isolation.
- Error handling now rejects **every nonzero CLI exit even when stdout is
  nonempty**. The observed quota exhausted JSON envelope with HTTP 429 is
  classified as a provider failure instead of a valid model answer. Invalid
  JSON is also rejected without elevating any claims or persisting a cached
  successful answer. The provider fallback chain recognizes those errors.
- The model compare and report scripts are recorded under `scripts/`; the
  [machine-readable output](./MODEL_COMPARISON.json) keeps all five per-model
  statuses, source references, summary judgments, action selection and
  warnings, without uploading full vendor documents or private provider
  credentials.

## Benchmark limitations

Small, hand-selected sample (5 tasks, 1 inference per model/task). The
predeclared fact-count checks are **literal token-presence checks**, not
independent engineering-validation trials. Actual source correctness is
limited to the retrieved public page or deterministic analysis of original
source bytes. No price quotation, hardware build, physical assembly, material
coupon, measured failure rate, user study, statistical significance,
model-specific price-per-token or actual usage quota calculation was assessed.
The original comparison sessions ran with `--sandbox` but before the stronger
empty-CWD adapter change, so model-environment isolation was best-effort.
Sonnet's quota exhaustion makes the fifth task non-comparable for that model.

Repeat the same task with new models via:

```bash
HARDWARE_SPLICER_LLM_PROVIDER=agy PYTHONPATH=src .venv/bin/python \
 scripts/benchmark_hs_agy_engineering_certainty.py opus55
HARDWARE_SPLICER_LLM_PROVIDER=agy PYTHONPATH=src .venv/bin/python \
 scripts/benchmark_hs_agy_engineering_certainty.py sonnet55
HARDWARE_SPLICER_LLM_PROVIDER=agy PYTHONPATH=src .venv/bin/python \
 scripts/benchmark_hs_agy_engineering_certainty.py argon4
```

The replay depends on the isolated source archives from the preceding Oct-21
trial on the authorized Optiplex and should not be run unattended against
quota-limited models. Generated local sample traces are kept under
`/tmp/hs-agy-certainty-trial-20261021` rather than checked into Git.
