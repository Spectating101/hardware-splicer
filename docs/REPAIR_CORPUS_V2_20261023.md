# Repair Challenge 02 — 16 sourced cases, frozen HS, baseline comparison

**Executed:** 2026-10-23. **Status: exploratory developer-curated benchmark, NOT independent prospective/held-out accuracy, physical repair, or commercial competitor head-to-head.**

## What actually changed

This PR expands the four-example repair pilot (draft #205) into **16 public source-based incidents**, with **10 owner-confirmed replacement fixes**, one commenter-confirmed separate-device anecdote, one confirmed non-component reset, and four other cases without a confirmed full repair.

The executable HS diagnostic implementation `src/hardware_splicer/repair_path_diagnostics.py` stays **frozen at commit `be06210bf06db8bc6a2068cfda71b52c47749565`**. No source-specific diagnosis rules or tuned part weights were added. The only additions are developer-curated observational data, a sealed outcome file, a diagnostic comparison script, an independent evidence-adequacy gate in the evaluation harness, a trivial non-AI baseline, answer-hidden prompts for an external model, and tests.

## Evidence and leak prevention

Public original incidents include [iPhone XS charger shutdown](https://www.ifixit.com/Answers/View/699930/iPhone+XS+automatically+shuts+down+once+plugged+to+charger), [iPhone 6 earpiece following battery repair](https://www.ifixit.com/Answers/View/536701/Ear+speaker+stopped+working+after+battery+replacement), [ThinkPad P17 power reset](https://www.ifixit.com/Answers/View/934998/Laptop+Won't+Power+On), [iPhone 4S faulty replacement battery](https://www.ifixit.com/Answers/View/378113/Replaced+Battery,+will+not+charge+even+though+it+shows+it+is.), [MacBook 2010 battery fault](https://www.ifixit.com/Answers/View/645248/Battery+indicator+works+but+does+not+charge+or+get+recognized), [PS5 aftermarket PSU mismatch](https://www.ifixit.com/Answers/View/924602/Missing+piece+reassembling+ps5,+now+overheating), [iPhone 15 charging-flex failed substitution](https://www.ifixit.com/Answers/View/874876/iPhone+15,+restarting+every+3+miutes,+I+attached+the+crash+log), and other linked iFixit discussions. **These are user reports**, not independent instrumented repair-verification records.

Two separate files deliberately prevent answer leakage:

- `blind_observations.json`: original symptom summaries and reported pass/fail route observations only. **No post-fix labels or URLs**; question titles/URLs can themselves reveal solutions. Includes device type, enumerated *candidate* components, manually modeled functional path membership and coarse 1–5 service-cost rank.
- `sealed_outcomes.json`: original source URLs, confirmation category and reported remedy. Loaded by the runner **only after all HS and naive-baseline predictions finish**. Owner confirmation is tracked separately from an expert's unverified hypothesis or a second commenter's similar device.

**Critical scope caveat:** Although the diagnosis function is blind to the answer file, the *benchmark author* selected the cases, manually assigned candidate parts and functional paths, and corrected two input encoding errors after inspecting outcomes. It is thus **not** an independent held-out cohort. Manual inferred paths aren't measured electrical connectivity; human source annotation can bias performance.

Input audit also corrected a serious earlier benchmark issue: “gaming load” on the PS5 is an *operating condition*, **not an electrical component**. It is now encoded as the same power path under two conditions. That case lacks a distinguishing route and cannot be scored as a supported component diagnosis. An iPhone charging-flex link and a distinct MacBook keyboard-flex service cost were also audited.

## Raw reproducible results

Runner `benchmarks/repair_corpus_v2_20261023/evaluate.py` executes both on identical cases. Comparator is the **simple non-AI “most frequent component in failed paths” heuristic** with alphabetical tie-breaking, *not a commercial competitor, deep learning model, professional mechanic or trusted diagnostic service*.

| Metric | Actual result |
| --- | ---: |
| Independently published incidents transcribed | **16** |
| Original owner confirmed replaceable-part fix | **10** |
| Confirmed fixes with at least 2 distinct functional routes | **5** |
| Confirmed fixes with inadequate discriminatory evidence | **5** |
| HS correct first component on eligible owner-confirmed routes | **3 / 5** |
| Trivial frequency baseline correct on eligible confirmed routes | **0 / 5** |
| HS correct on ALL owner-confirmed fixes, counting insufficient-evidence cases as misses | **3 / 10** |
| HS explicit abstentions across all cases | **9 / 16** |
| Cases without sufficient differentiating routes (confirmed + unresolved) | **10 / 16** |
| Real external model queries | **0** |
| Devices physically repaired / hardware measurements obtained | **0** |

**These numbers must not be described as 60% general repair accuracy or superiority over a real product.** The eligible `n=5` is tiny, hand-selected, and includes two closely related iPhone charging-flex symptom patterns. The numerator of three matches is mostly those two iPhones and a MacBook trackpad/keyboard flex. The simple comparator is intentionally weak; its `0/5` is not a competitive victory.

The evidence audit found a further real flaw: the frozen HS reasoner sometimes **proposes a part on a load-dependent failure even when both pass and fail observations traverse the exact same component path**. Its old requirement of two observations was too permissive. The harness flags this as **insufficient discriminating routes**, refuses to credit any match, and records that failure separately. *Do not silently fix the engine and rescore this benchmark as though it were unchanged.*

Other important misses: iPhone 4S replacement-battery vs charging-port tie, MacBook battery vs battery connector tie, and many single-symptom cases where HS properly refuses to choose.

## How to reproduce

Install dependencies with `pip install -e '.[dev]'` and execute:

```bash
python benchmarks/repair_corpus_v2_20261023/evaluate.py /tmp/hs_repair_corpus_v2.json
python benchmarks/repair_corpus_v2_20261023/prepare_external_prompts.py /tmp/external_same_input.jsonl
pytest -q tests/test_repair_corpus_v2.py tests/test_repair_corpus_external_protocol.py tests/test_repair_path_diagnostics.py
```

Expected: `16` cases, `10` owner-confirmed fixes, `5` eligible, `3` HS matches, `0` simple-baseline matches, and `9` HS abstentions. The previous CI-focused run completed **46 passing Python tests** including old repair API and project-package regressions.

## Real competitor protocol is prepared but NOT executed

`prepare_external_prompts.py` writes the **same symptom, candidate component, reversible-test and observed route evidence** for each source case to a JSONL file without source URLs or resolutions. The external system must return one candidate ID or a justified abstention, proposed reversible next check, and a transcript/receipt. The scorer `score_external_baseline.py` enforces exactly one response per case, valid candidate identities, provider name and transcript SHA-256, then scores against sealed owner-confirmed outcomes.

**The external scorer does not authenticate the model call**, and no third-party model was queried in this work. HS `3/5` vs simple heuristic `0/5` is not a head-to-head against Flux, iFixit FixBot, an open-source LLM, or an expert technician. Do not fabricate those missing results. A genuine external run is still necessary.

### Next steps (engineering and business relevance)

1. **Independent blinded corpus:** recruit an evaluator who did not select cases or know outcomes, gather 20–50 confirmed repairs across electronic and mechanical failure types, and preserve diagnostic pre-fix evidence snapshots.
2. **Repair engine fix on a separate branch:** abstain on identical pass/fail component routes; distinguish operating-state changes from physical topology. Keep frozen V2 receipts immutable.
3. **Better evidence acquisition:** obtain device identity, tested voltages, thermal readings, known-good substitution results and genuine schematic connectivity, rather than requiring a human author to invent path membership.
4. **Real comparison:** run the prepared identical prompts on a connected capable AI assistant and/or a repair-tech baseline, collecting transcript costs, time, component errors and justified abstentions.
5. **Repair economics:** once diagnoses become reliable, attach verified parts pricing, replacement vs repair value, salvage value, and cost of unnecessary replacement. Never claim savings based on ordinal 1–5 service rank.

**Verdict:** HS has a bounded triage capability when structured evidence exists; it is not yet a broadly capable, evidence-gathering or competitively verified physical repair engineer.
