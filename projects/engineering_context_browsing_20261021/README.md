# HS engineering-context browsing, genuinely tested

**2026-10-21, isolated Optiplex repository branch:**
`integration/hs-unified-engineering-20261021`.

## Functional feature

HS now has an explicit native AI engineering action:
`research_engineering_context`. When missing information could change an
engineering decision, the agent can propose an external lookup selected from
`engineeringResearchRequests` recorded in the revision-pinned project. The
accepted tool action:

1. Locates the exact registered research question and trusted publisher hosts;
   it does **not** execute model-authored URLs, code, or browser instructions.
2. Searches bounded public HTML search results for those trusted hosts, or
   retrieves an explicitly **project-pinned** original publisher document URL.
3. Reads a bounded amount of HTML (or a specific original iFixit public guide
   API), preserves page URL, SHA-256 of the original downloaded bytes, and a
   short excerpt. A search result snippet without original page bytes has **no**
   original-document SHA-256 and cannot become authoritative source evidence.
4. Persists the read-only result in the actual HS AI action history and
   project snapshot. A subsequent native AI session receives the retrieved
   excerpt, original URL and a canonical `W1`, `W2` publisher-source alias.
5. Permits citation of such evidence for **attributed published claims only**:
   it cannot prove acquired hardware identity, material tests, physical fit,
   real part numbers, electrical power-on, or fabrication/release readiness.
6. Reuses the same recent successful exact request (6-hour bound) rather than
   browsing again; changed queries and stale results invalidate the reuse.

The implementation preserves existing explicit approval of a software-only
source action. It is **not** an unrestricted browser and does not perform
physical operations, purchasing or device authorization.

## A real matched before-and-after capability test

The tests called the **same actual GitHub Copilot text provider** through the
HS project API for each device, twice, using the same engineering question.
The first native AI session lacked publisher text. The AI chose the read-only
`research_engineering_context` action. The executor fetched the published
original, persisted a SHA-256-backed source, and then a second native session
received its excerpt and source alias. All results were saved to three separate
HS project stores on the authorized Optiplex.

| Original engineering question | Before retrieval | After retrieval | Fetched original publisher |
| --- | ---: | ---: | --- |
| Holybro X500 V2 motor/ESC/propeller model specifications | **0/3** | **3/3** | [Holybro X500 V2 ARF Kit](https://holybro.com/products/x500-v2-kits) |
| PSP 300x UMD guide safety, number of steps, target model | **2/3** | **3/3** | [iFixit PSP 300x Guide 1586](https://www.ifixit.com/Guide/PSP+300x+UMD+Drive+Replacement/1586) |
| Prusament ASA UV/outdoor suitability and temperature behavior | **1/3** | **3/3** | [Prusament ASA](https://prusament.com/materials/prusament-asa/) |
| **Total** | **3/9** | **9/9** | Three independent source sites |

**Metric definition:** the figures are counts of **predeclared factual term
checks** present in model output, not independent expert judgement. After
retrieval, each counted term was also visible in the title or short extracted
publisher text, and the model's structured requirements cited the hash-pinned
`web-*` publisher source identity. The displayed publisher specifications are
manufacturer statements, **not measured validation**. Small selected pilot,
no statistical significance, no device assembly, no claims about other models.

The motor information was previously absent. After browsing, the model stated
**Holybro 2216 KV920 motors, BLHeli S 20A ESCs and six 1045 propellers**,
with a manufacturer URL and source ID. For the PSP it identified battery
removal and the **42-step** publisher guide while declining to substitute a
PSP 2000/300xc guide. For ASA it identified UV/outdoor suitability and
publisher-stated thermal resistance, without certifying a particular printed
part's strength, environmental or chemical safety.

The additional **drone third-session test** confirmed the agent stopped
repeating an already completed search and proposed verification and missing-
evidence actions instead. Its existing model output remained physically
non-authorizing.

## Failures the pilot exposed and repaired

- A naive first version retrieved documents but the model still refused to use
  them because only previously uploaded CAD was citation-eligible. Publisher
  evidence now has a distinct `W#` citation class and attributed-only ceiling.
- Exact published guides/pages sometimes exceed 500 KB: Holybro product HTML
  was ~522 KB and PX4 instructions ~1.08 MB. The bounded page ceiling is now
  1.35 MB, with short model-facing excerpts.
- Public Brave HTML search **returned HTTP 429** after repeated trial queries.
  Google/Bing endpoints on this device were not usable as automatic result
  pages. **Reliable general search discovery is not established.** The
  successful measured A/B used **known official URLs supplied to the projects
  by the evaluator** and actually downloaded by HS; this proves retrievability,
  AI-tool execution and evidence-backed reasoning, **not autonomous discovery
  of unknown source URLs**. Initial search-only failure trials are intentionally
  distinguished from these known-source trials.
- Repeated already-completed research requests previously caused redundant
  actions; now a six-hour content-identity-bound source cache prevents needless
  fetches, and the model prompt points it toward verification instead.

## Tests, files and reproducibility

- Source implementation:
  `src/hardware_splicer/engineering_web_research.py`,
  `src/hardware_splicer/ai_project_tool_executor.py`,
  `src/hardware_splicer/ai_project_tool_executor_api.py`,
  `src/hardware_splicer/ai_project_orchestrator.py`.
- Regressions: `tests/test_engineering_web_research.py` (source host/URL
  rejection, source hashes, prompt evidence handoff, API persistence,
  idempotence, stale-query cache invalidation and non-authority).
- Live paired benchmark:
  `scripts/benchmark_hs_research_impact.py`. Produce publication-safe summary
  with `scripts/summarize_hs_browsing_benchmark.py`.
- Final machine-readable compact results:
  [BENCHMARK_RESULTS.json](./BENCHMARK_RESULTS.json). The full live
  downloaded/publisher excerpts and model API project sessions are maintained
  in `/tmp/hs-engineering-browsing-ablation-pinned-20261021/` on Optiplex,
  not republished as copyrighted vendor documentation in the repository.

### Re-running the paired test

A configured Copilot text provider and access to those original publishers are
necessary. Run one case at a time to avoid provider/network contention:

```bash
HARDWARE_SPLICER_LLM_PROVIDER=copilot_cli PYTHONPATH=src .venv/bin/python \
 scripts/benchmark_hs_research_impact.py drone --out-root /tmp/hs-new-browse-pair
HARDWARE_SPLICER_LLM_PROVIDER=copilot_cli PYTHONPATH=src .venv/bin/python \
 scripts/benchmark_hs_research_impact.py repair --out-root /tmp/hs-new-browse-pair
HARDWARE_SPLICER_LLM_PROVIDER=copilot_cli PYTHONPATH=src .venv/bin/python \
 scripts/benchmark_hs_research_impact.py chemistry --out-root /tmp/hs-new-browse-pair
```

**Current verdict:** conditional external context browsing improves the
agent's ability to state source-backed engineering information **when original
source retrieval succeeds**. No demonstration yet of broader browsing-service
reliability or improved device manufacturing success; those remain separate
engineering and commercial acceptance tests.
