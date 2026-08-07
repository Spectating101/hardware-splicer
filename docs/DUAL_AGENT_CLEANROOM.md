# Hardware Splicer Dual-Agent Cleanroom

**Status:** development doctrine for the post-PR-55 cleanup line  
**Base frontier:** `agent/public-visual-adapter-spike-20260805`  
**Goal:** remove scripted semantic reasoning while preserving deterministic engineering truth.

## 1. Why this exists

Hardware Splicer now has enough AI-facing surface area that ordinary source review is no longer sufficient to judge whether the product actually behaves like an engineering agent.

A system can look agentic from the outside while still being driven by:

- phrase rewrites that convert unfamiliar requests into known demo language;
- regex/keyword routing that substitutes a canned ontology for interpretation;
- preferred-component IDs that silently force a familiar architecture;
- fixture-specific branches or golden-path assumptions;
- tests that validate recognition of the fixture rather than competence on the task;
- model calls used only after deterministic code has already made the important semantic decision.

The cleanup target is therefore not "remove determinism". Hardware Splicer requires deterministic engineering contracts. The target is **deterministic code pretending to reason**.

## 2. Preserve the engineering constitution

The following should remain deterministic and fail-closed unless there is a strong engineering reason to change them:

- project/revision identity and optimistic concurrency;
- evidence provenance and authority ceilings;
- source hashes and artifact hashes;
- action allowlists and execution boundaries;
- human accept/reject decisions;
- DRC/ERC and tool-result truth;
- physical evidence requirements;
- fabrication, flashing, power, motion, operation, and release authority gates;
- electrical limits and explicit component/interface contracts;
- reproducible package construction;
- filesystem, path, upload, storage, and security boundaries.

These are constraints and measurements, not cognition.

## 3. Purge semantic script brain

The following are presumptively suspect when they influence engineering interpretation or architecture selection:

- natural-language regex routing;
- phrase-expansion tables whose purpose is to turn user language into known trigger phrases;
- keyword families used as substitutes for semantic interpretation;
- magic preferred-component IDs selected from user prose;
- demo-name or fixture-name conditionals in production reasoning paths;
- architecture defaults that are not derived from evidence, constraints, or explicit policy;
- silent fallback from unknown intent to a familiar project archetype;
- hand-maintained synonym maps used to decide engineering meaning;
- tests whose primary assertion is that a known phrase maps to a known canned design;
- hidden test-only knowledge available to the product agent.

A deterministic parser is acceptable when it parses a declared format. A deterministic rule is acceptable when it enforces a declared contract. A deterministic heuristic becomes suspect when it answers a question that should require interpretation.

### First confirmed examples

`src/hardware_splicer/module_picker.py` currently contains a large hand-written `MODULE_HINTS` table mapping phrases such as robot, rover, plant, pump, weather, relay, camera, and stepper language onto preferred modules and architectures. It explicitly describes the path as "Regex for trained phrases; Qwen for novel goals".

`src/hardware_splicer/phrase_expander.py` rewrites messy user language into phrases the deterministic router understands, including broad semantic rewrites such as beginner/no-experience language into a specific simple-build intent and "where do I start" into a plant-watering project.

These are priority cleanup targets because they can make a system appear robust on paraphrases while actually translating the user back onto a scripted rail.

## 4. Two-pronged agent model

Hardware Splicer development should use two deliberately different model roles.

### A. System Engineer / Observer

The outer agent works **on** Hardware Splicer.

It may inspect:

- repository source;
- architecture and contracts;
- tests and CI;
- traces and persisted project revisions;
- tool artifacts and failures;
- operator-agent transcripts and action history.

It may propose or implement code changes, but it must distinguish:

1. what the source appears to intend;
2. what the embedded operator actually observed;
3. what deterministic evidence proves.

It should prefer root-cause fixes over fixture patches.

### B. Embedded Operator / Engineer

The inner agent works **inside** Hardware Splicer as an ordinary engineering operator.

It should be given only the product-visible information appropriate to the scenario:

- user/project brief;
- uploaded evidence available through the product;
- Project Studio / JARVIS / public API / MCP / CLI surfaces under test;
- tool results and errors returned through those surfaces.

It must not receive:

- repository source code;
- hidden golden answers;
- fixture-specific expected architecture;
- private implementation notes;
- outer-agent analysis;
- test assertions that reveal the intended solution.

The embedded operator should behave as if Hardware Splicer is the only engineering environment it has.

## 5. The system itself is the arbiter

The two agents do not vote on whether a design is correct.

Correctness and authority come from deterministic evidence:

- source/evidence identities;
- interface contracts;
- DRC/ERC/tool output;
- simulation where valid;
- artifact hashes;
- bench measurements;
- explicit human decisions;
- physical-authority gates.

The outer agent evaluates the inner agent's behavior against these records. The inner agent cannot promote its own confidence into project truth.

## 6. Evaluation loop

Each cleanroom scenario should run as:

```text
scenario seed
  -> embedded operator uses public HS surface
  -> HS records revisions, proposals, decisions, previews, failures, repairs
  -> deterministic evidence establishes what actually happened
  -> outer engineer inspects trace + source
  -> outer engineer classifies failure
  -> patch or policy change
  -> replay original scenario
  -> replay perturbed variants
```

A fix is not accepted merely because the original case passes.

## 7. Required perturbations

Every important scenario should have transformations designed to expose scripted reasoning:

- paraphrase the same engineering goal without known keywords;
- change word order and irrelevant prose;
- use an unfamiliar but functionally equivalent component;
- omit brand/model names while preserving constraints;
- introduce a plausible but incorrect analogy;
- provide conflicting sources with different authority;
- provide partial evidence and require a clarification/blocker rather than a guess;
- change units or representation without changing the physical meaning;
- reorder uploaded evidence;
- inject a deterministic tool failure;
- retry from a stale project revision;
- remove the golden fixture name and IDs;
- replace the demo domain while preserving the same class of engineering problem.

The desired invariant is not identical prose. It is equivalent engineering state, blockers, and authority.

## 8. Core scenario families

The initial cleanroom suite should cover at least:

1. **greenfield fixture** — requirements to candidate with no preselected architecture;
2. **salvage / inherited board** — ambiguous donor hardware with partial interface evidence;
3. **semiconductor DUT fixture** — conflicting voltage domains and default-off safety requirements;
4. **robot / machine** — electrical + mechanical + firmware graph consistency;
5. **bench closure** — measurements needed before firmware/power authority;
6. **unknown component** — force evidence acquisition rather than catalog analogy;
7. **failure repair** — preserve failed parent and create a bounded successor;
8. **evidence conflict** — higher-authority evidence must defeat plausible lower-authority inference.

## 9. Metrics

Track properties rather than a single pass/fail score.

### Agentic competence

- **novel-intent success:** useful progress without matching a known phrase family;
- **clarification quality:** asks for missing information rather than inventing it;
- **proposal quality:** actions are technically relevant and evidence-linked;
- **repair quality:** failure evidence changes the successor appropriately;
- **tool-use quality:** chooses the right bounded tool rather than narrating around uncertainty.

### Anti-script robustness

- **paraphrase invariance:** equivalent intent reaches equivalent engineering state;
- **fixture independence:** success survives renamed IDs and unfamiliar components;
- **ordering invariance:** source ordering does not change truth;
- **unknown handling:** unknowns remain unknown instead of falling to a favorite module;
- **golden leakage rate:** no hidden expected answer reaches the embedded operator.

### Truth discipline

- **evidence fidelity:** claims cite valid persisted evidence identities;
- **authority discipline:** no model statement elevates physical authority;
- **failure preservation:** failed evidence is immutable and visible;
- **reproducibility:** replay of the same accepted revision yields the same deterministic artifacts where required.

## 10. Failure taxonomy for the outer engineer

When the inner operator fails, classify the cause before patching:

- **MODEL_REASONING** — model interpretation or planning failure;
- **CONTEXT_CONSTRUCTION** — relevant evidence not exposed or too much irrelevant context;
- **SCRIPT_BRAIN** — regex, phrase rewrite, keyword table, magic component/default, fixture branch;
- **TOOL_CONTRACT** — product does not expose a needed bounded operation;
- **TOOL_IMPLEMENTATION** — tool exists but returns incorrect/incomplete evidence;
- **STATE_MODEL** — revision, lineage, persistence, or identity problem;
- **UI_AFFORDANCE** — public surface hides or misrepresents a valid operation;
- **EVIDENCE_MODEL** — authority/provenance schema cannot represent the needed truth;
- **TEST_ORACLE** — test encodes the old implementation instead of desired behavior;
- **PHYSICAL_GAP** — software cannot resolve the question without real-world evidence.

Only `MODEL_REASONING` should normally be fixed with prompting/model changes. The others are system defects.

## 11. Cleanup order

### Phase 0 — restore trustworthy baseline

- repair the current PR-55 exact-head regressions;
- keep the passing Project Studio, Visual Workbench, browser E2E, deployment, robot-reference, splice demo, golden-loop, and real-bench bars intact;
- separate obsolete-test failures from real product regressions.

### Phase 1 — inventory semantic hardcodes

Audit production reasoning paths for:

- regex and keyword routing;
- phrase rewriting;
- preferred component IDs;
- demo-specific switches;
- implicit architecture defaults;
- model calls that happen only after deterministic semantic decisions.

Classify every hit as **contract**, **parser**, **heuristic**, **demo-only**, or **script-brain**. Do not remove a safety/format contract because it contains a regex.

### Phase 2 — establish embedded-operator harness

Create an operator adapter that can execute a scenario through the same public interfaces an outsider uses. Capture:

- all requests/responses;
- project revisions;
- model/provider identities;
- proposed actions and human decisions;
- tool results/failures;
- evidence references;
- final blockers and authority state.

No repository source is injected into the operator context.

### Phase 3 — remove semantic shortcut layers behind reversible boundaries

Start with `phrase_expander.py` and natural-language `module_picker.py` behavior.

The replacement should move toward:

```text
user intent
  -> model produces typed engineering intent / requirements
  -> validator checks schema and evidence references
  -> deterministic capability/catalog query
  -> model compares viable candidates against constraints
  -> explicit proposal
  -> human review
  -> deterministic verification
```

The model should choose from evidence-bound capabilities, not from a regex-selected favorite part.

### Phase 4 — adversarial replay

For every removed shortcut, run original golden cases plus paraphrases, renamed fixtures, unfamiliar components, incomplete evidence, and conflicts. A regression that reveals the old golden depended on the shortcut is useful evidence, not a reason to restore the shortcut automatically.

### Phase 5 — let the embedded operator criticize the product

After completing each scenario, ask the embedded operator for a structured retrospective limited to what it could observe inside the product:

- what it believed the current state was;
- what information it could not obtain;
- which action it wanted but could not express;
- which UI/tool result was ambiguous;
- where it was forced to guess;
- what it would do next as an engineer.

The outer engineer compares this retrospective with source and trace evidence. Disagreement is a diagnostic signal.

## 12. Acceptance rule

A cleanup tranche is complete only when:

1. the targeted semantic shortcut is removed or made non-authoritative;
2. existing deterministic truth/safety contracts remain intact;
3. original golden cases still have defensible outcomes or are intentionally corrected;
4. perturbed cleanroom cases do not depend on known trigger phrases or fixture IDs;
5. the embedded operator can explain its next action from product-visible evidence;
6. the outer engineer can trace that behavior to explicit system contracts rather than hidden script logic;
7. exact-head CI is green for the tranche's declared scope.

The objective is not maximal model autonomy. The objective is **maximal model reasoning inside minimal, explicit, auditable engineering constraints**.
