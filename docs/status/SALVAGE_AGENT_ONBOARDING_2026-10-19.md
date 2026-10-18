# Salvage agent onboarding cleanup — 2026-10-19

This tranche consolidates visual intake and the investigation queue on the
existing investigation PR, following the visual-intake PR. It opens no new PR,
adds no service/store and changes no physical authority rule.

## What an agent now gets

- One canonical salvage task index, with visual drafts and investigation context
  available on the same head.
- Compact discovery by default; full operation schemas remain available explicitly
  or one operation at a time.
- The missing parts-reading, spec-discovery, drafting and package-download
  operations in that index. Document/assurance specialist workflows are discoverable
  on demand instead of duplicating their full schemas at startup.
- Discriminated event request documentation and named JSON templates for the five
  proposal types; enumerated software-check requests. These document the existing
  handlers, not replace their runtime validation.
- Inventory and HS's inventory reading, structured requirements, recorded-check
  summaries and stale/current flags on resume. Freshness uses the canonical
  readiness gate's existing repair/evidence sequence boundary.
- A canonical-MCP-first quickstart, explicit recovery guidance and a separately
  labelled legacy compose guide.

## Measured discovery size

Measured as UTF-8 bytes of the MCP text renderer's indented/sorted JSON,
using the same Python 3.13 / FastAPI 0.136.3 environment:

| Manifest | Operations | Bytes |
| --- | ---: | ---: |
| Pre-cleanup merged visual/investigation head `9ce73d94` | 21 | 67,699 |
| New compact default | 25 | 12,681 |
| New explicit full detail | 25 | 100,852 |

The startup payload is about 81% smaller than the pre-cleanup response while
offering more workflow operations. Compact mode is about 87% smaller than the
same head's full response. These are byte counts, **not model-token or end-to-end
latency measurements**. Schema detail still has a cost when it is requested.

## Local verification

Separate runs, not an aggregate unique-test total:

- Initial focused integration regression: 104 passed.
- Final mission-store/delivery/evidence/onboarding regression: 136 passed.
- Dedicated MCP-SDK environment contract checks: 25 passed.
- Real MCP stdio smoke: passed, including compact salvage discovery, event
  contracts, context readback and unidentified-parts reading.
- Real Streamable HTTP MCP smoke: passed.

The shared legacy MCP environment was not upgraded. A dedicated environment
installed the canonical backend MCP extra, as the updated quickstart recommends.
The fresh dependency lane reports an existing duplicate OpenAPI operation-ID
warning in the anchored execution-evidence route; it is not suppressed by these
changes. Broad regression and transport checks also run in GitHub CI.

## What this does not establish

- No live LLM cold-start trial has run in this tranche.
- The automated cold-client controls are scripted interface tests, not an
  independent agent-usability score or a real e-waste demonstration.
- The known-parts package control is not presented as a dumpster-diving case.
- The native device planner still has bounded supported hardware families;
  clearer onboarding does not create arbitrary-donor engineering support.
- No hardware was fabricated, powered, flashed or measured.
  `physical_correctness=UNPROVEN`.

The next real-model trial is defined in
[SALVAGE_AGENT_TRIAL.md](../SALVAGE_AGENT_TRIAL.md): goal/evidence/connection only,
no source-code lookup or case-specific payload coaching, restart recovery and
separate engineering-progress and usability metrics.
