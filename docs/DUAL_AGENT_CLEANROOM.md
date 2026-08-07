# Hardware Splicer Dual-Agent Cleanroom

**Status:** active implementation line after PR #55  
**Base frontier:** `agent/public-visual-adapter-spike-20260805`  
**Goal:** remove scripted semantic reasoning while preserving deterministic engineering truth.

## 1. Why this exists

Hardware Splicer now has enough AI-facing surface area that ordinary source review is no longer sufficient to judge whether the product actually behaves like an engineering agent.

A system can look agentic from the outside while still being driven by phrase rewrites, regex/keyword routing, preferred-component IDs, fixture-specific branches, or tests that only prove recognition of the fixture. The cleanup target is therefore not "remove determinism". Hardware Splicer requires deterministic engineering contracts. The target is **deterministic code pretending to reason**.

## 2. Preserve the engineering constitution

Keep deterministic and fail-closed:

- project/revision identity and optimistic concurrency;
- evidence provenance and authority ceilings;
- source/artifact hashes;
- action allowlists and execution boundaries;
- human accept/reject decisions;
- DRC/ERC and tool-result truth;
- physical evidence requirements;
- fabrication, flashing, power, motion, operation, and release gates;
- explicit electrical/component/interface contracts;
- reproducible package construction;
- filesystem, upload, storage, and security boundaries.

These are constraints and measurements, not cognition.

## 3. Purge semantic script brain

Presumptively suspect when they decide engineering meaning:

- natural-language regex routing;
- phrase-expansion tables that translate users onto known trigger phrases;
- keyword families used as a substitute for interpretation;
- magic preferred-component IDs selected from prose;
- demo/fixture-specific semantic branches;
- architecture defaults not derived from evidence, constraints, or explicit policy;
- silent fallback from unknown intent to a familiar project archetype;
- tests whose primary assertion is that a known phrase maps to a canned design.

A deterministic parser is acceptable when it parses a declared format. A deterministic rule is acceptable when it enforces a declared contract. A deterministic heuristic becomes suspect when it answers a question that should require interpretation.

### Confirmed targets

- `module_picker.py`: hand-written phrase/regex -> preferred-module routing; currently describes the path as "Regex for trained phrases; Qwen for novel goals".
- `phrase_expander.py`: rewrites messy user language into phrases the deterministic router understands.
- `circuit_synthesis/planner.py`: keyword families select topology planners.
- legacy intake/archetype routing: derived classifier results can leak into later engineering layers as if they were declared truth.

### First removals already implemented

`intent_clarifier.py` no longer translates broad answers such as "battery", "ESP32", or "pump motor" into invented voltage/current values, load classes, or catalog parts. Answers remain `authority: declared` observations with `interpretation_status: unresolved`.

The source-agnostic engineering planner no longer passes the legacy intake `archetype` guess into robot topology as an authoritative hint. Only an explicitly structured `robot_genre` may act as a hint; otherwise topology derives from its own engineering inputs. This prevents one classifier's guess from overriding a contradictory brief.

## 4. Two-pronged agent model

### Outer System Engineer / Observer

Works **on** Hardware Splicer and may inspect repository source, architecture, CI, tests, traces, persisted revisions, tool artifacts, failures, and inner-agent transcripts. It must separate what the code intended, what the embedded operator observed, and what deterministic evidence proves.

### Embedded Operator / Engineer

Works **inside** Hardware Splicer as an ordinary engineering operator.

Implemented canonical HTTP path:

`POST /v1/projects/{project_id}/cleanroom/operator-turn`

The caller supplies an exact expected revision, mission, and model controls. The server loads the persisted project snapshot itself. The caller cannot supply a project snapshot or arbitrary engineering constraints.

The embedded operator must not receive repository source, hidden golden answers, fixture expectations, implementation notes, outer-agent analysis, or hidden test assertions. Cleanroom code rejects those outer-only fields recursively and rejects model evidence/source IDs that do not resolve to product-visible project sources.

## 5. The system is the arbiter

The agents do not vote on correctness. Correctness and authority come from source/evidence identities, interface contracts, DRC/ERC/tool output, valid simulation, artifact hashes, bench measurements, explicit human decisions, and physical-authority gates.

The cleanroom path is evaluation-only: no automatic action execution, no project mutation, and no fabrication/flash/power/motion/operation/release authority elevation.

## 6. Evaluation loop

```text
scenario seed
  -> persisted HS project revision
  -> embedded operator uses the product-visible cleanroom path
  -> HS returns proposal/evidence/tool state
  -> deterministic evidence establishes what happened
  -> outer engineer inspects trace + source
  -> classify failure
  -> patch root cause
  -> replay original scenario
  -> replay perturbed variants
```

A fix is not accepted merely because the original case passes.

## 7. Perturbations

Important scenarios should be replayed with:

- paraphrased goals without known keywords;
- changed word order/irrelevant prose;
- unfamiliar but functionally equivalent components;
- omitted brand/model names while preserving constraints;
- plausible but wrong analogies;
- conflicting sources with different authority;
- partial evidence requiring a blocker/clarification rather than a guess;
- unit/representation changes preserving physical meaning;
- reordered evidence;
- deterministic tool failure;
- stale project revision;
- renamed fixture/project IDs;
- changed demo domain preserving the same engineering class.

Implemented first invariant: source collections are canonicalized by stable source identity before cleanroom context construction, so reversing upload order produces the same context hash.

## 8. Scenario families

1. greenfield fixture;
2. salvage/inherited board;
3. semiconductor DUT fixture;
4. robot/machine;
5. bench closure;
6. unknown component;
7. failure repair;
8. conflicting evidence.

Golden rover and semiconductor fixture traces are the first serious domains to connect to this path.

## 9. Metrics

Track properties rather than one score.

### Agentic competence
- novel-intent success;
- clarification quality;
- evidence-linked proposal quality;
- failure-fed repair quality;
- bounded tool-use quality.

### Anti-script robustness
- paraphrase invariance;
- fixture independence;
- source-order invariance;
- unknown handling;
- golden leakage rate.

### Truth discipline
- evidence identity fidelity;
- authority discipline;
- immutable failure preservation;
- deterministic artifact reproducibility where required.

## 10. Failure taxonomy

Classify before patching:

- `MODEL_REASONING`
- `CONTEXT_CONSTRUCTION`
- `SCRIPT_BRAIN`
- `TOOL_CONTRACT`
- `TOOL_IMPLEMENTATION`
- `STATE_MODEL`
- `UI_AFFORDANCE`
- `EVIDENCE_MODEL`
- `TEST_ORACLE`
- `PHYSICAL_GAP`

Only `MODEL_REASONING` should normally be fixed with model/prompt changes. The others are system defects.

## 11. Current implementation status

### Baseline trust

- runtime dependency profiles aligned;
- stale Design Studio async-job tests replaced with the current finalization contract;
- route uniqueness now checks actual HTTP operation identity rather than Starlette traversal internals;
- trust reports distinguish unavailable DRC from failed DRC and never format unknown evidence as a fake zero;
- structured-source adapter metadata is promoted into graph-visible representation without authority elevation.

### Embedded operator harness

Implemented:

- source/outer-context isolation;
- persisted-revision HTTP entry point;
- stale-revision rejection;
- caller snapshot injection rejection;
- caller constraint injection rejection;
- evidence identity validation;
- zero-authority/evaluation-only contract;
- source-order canonicalization.

### Semantic cleanup

Started:

- clarification answers no longer fabricate electrical facts;
- legacy archetype guesses no longer override robot topology evidence.

Next:

- put a typed semantic-intent/capability proposal in front of module selection;
- demote `phrase_expander.py` and regex `module_picker.py` to offline/failure-only fallback;
- stop keyword topology dispatch from owning normal LLM-enabled engineering paths;
- connect cleanroom runs to rover + semiconductor golden domains and perturb them.

Target architecture:

```text
user intent
  -> model produces typed engineering intent / requirements
  -> schema/evidence validation
  -> deterministic capability/catalog query
  -> model compares viable candidates against constraints
  -> explicit proposal
  -> human review
  -> deterministic verification
```

The model chooses from evidence-bound capabilities; deterministic code enforces contracts and truth.

## 12. Acceptance rule

A cleanup tranche is complete only when:

1. targeted semantic shortcut is removed or made non-authoritative;
2. deterministic truth/safety contracts remain intact;
3. original golden cases have defensible outcomes or are intentionally corrected;
4. perturbed cases do not depend on trigger phrases/fixture IDs;
5. the embedded operator can explain its next action from product-visible evidence;
6. the outer engineer can trace behavior to explicit contracts rather than hidden script logic;
7. exact-head CI is green for the tranche's declared scope.

The objective is **maximal model reasoning inside minimal, explicit, auditable engineering constraints**.