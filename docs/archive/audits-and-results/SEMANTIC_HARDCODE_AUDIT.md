# Hardware Splicer Semantic Hardcode Audit

**Branch:** `agent/dual-agent-cleanroom-20260808`  
**Purpose:** distinguish deterministic engineering constitution from deterministic code that is performing semantic reasoning on behalf of the model.

This is a live cleanup inventory, not a blanket ban on regex, tables, defaults, or deterministic code.

## Classification

| Class | Meaning | Default action |
|---|---|---|
| `CONTRACT` | Deterministic truth, safety, identity, authority, validation, or security rule | Keep deterministic |
| `PARSER` | Deterministic syntax/format handling for a declared representation | Keep; test losslessness |
| `HEURISTIC` | Non-authoritative convenience inference with explicit provenance and safe fallback | Keep only if visibly non-authoritative |
| `DEMO_ONLY` | Golden/demo scaffolding isolated from normal product reasoning | Keep isolated or retire |
| `SCRIPT_BRAIN` | Keyword/regex/default logic that decides engineering meaning, architecture, or components from prose | Remove, demote, or replace with typed model proposal + verification |

## Executive finding

The current product has a strong deterministic truth/authority spine, but several older intake and catalog paths still contain semantic shortcut layers. The new dual-agent cleanroom is useful only if the embedded operator is prevented from inheriting those shortcuts as disguised project truth.

The primary risk is not regex itself. The risk is **semantic laundering**:

```text
human prose
  -> deterministic keyword/archetype/component guess
  -> guess becomes structured field
  -> downstream model sees structured field
  -> model appears to reason from evidence
```

The cleanup must preserve the distinction between **declared**, **observed**, **proposed**, and **verified** information.

## Confirmed inventory

### 1. `src/hardware_splicer/module_picker.py`

**Class:** `SCRIPT_BRAIN`  
**Priority:** P0

The natural-language path contains a large `MODULE_HINTS` table whose regex patterns map prose directly to capability groups and preferred component IDs. Examples include:

- temperature/humidity -> `dht22`
- pressure/environment -> `bme280`
- robot/rover/RC car -> `l298n`
- stepper/CNC/plotter -> `a4988-stepper`
- wireless -> `esp32-devkit`
- camera -> `esp32-cam-module`
- pump/watering -> pump + driver defaults

It also deterministically injects controller and power modules from phrase matches.

The function describes the design as `Regex for trained phrases; Qwen for novel goals when keyed.` That is exactly the inversion this cleanup is intended to remove: the model should interpret intent first, while deterministic code should validate/query capabilities after a typed proposal exists.

**Target state:**

- keep module registry and capability queries deterministic;
- stop prose regex from choosing preferred components as product truth;
- model emits typed requirements/capabilities and candidate rationale;
- catalog lookup returns viable candidates without silently selecting a favorite;
- final selection remains proposal-only until accepted and verified;
- legacy regex path may temporarily survive only as an explicitly offline compatibility path with provenance.

### 2. `src/hardware_splicer/phrase_expander.py`

**Class:** `SCRIPT_BRAIN` with a small `PARSER` subset  
**Priority:** P0

Typo normalization can be a harmless lexical convenience. Broad semantic rewrites are not.

High-risk examples include mapping vague beginner language or `where do I start` into a specific plant-watering intent. Those transforms collapse uncertainty onto a known demo rail before the model sees the original problem.

**Target state:**

- lexical normalization may remain lossless/non-semantic;
- semantic rewrites must not alter the user's engineering objective;
- model-first paths receive original user text;
- unknown/vague intent produces clarification or an explicit proposal, not a hidden canned objective.

### 3. `src/hardware_splicer/integrations/build_id_hints.py`

**Class:** `SCRIPT_BRAIN`  
**Priority:** P0

`keyword_build_id()` routes broad words and domain phrases to complete catalog builds. The table includes increasingly wide phrase families such as watering, robot/Enabot, printers/CNC, fans, relays, sensors, audio, input panels, lighting, pan-tilt, grippers, bench power, UART, and network-status use cases.

`reconcile_build_pick()` can override an LLM pick with the keyword build when deterministic planners agree or model confidence is below a threshold. This means a semantic heuristic can overrule the model and become the architecture decision.

**Target state:**

- `BUILD_ID_GUIDE` may remain as catalog descriptions supplied to a model/candidate search;
- keyword routing must not be an authority source;
- candidate generation should be capability/constraint based;
- disagreement between model and deterministic catalog compatibility should become a blocker/explanation, not a silent keyword override;
- golden-build aliases belong in demo fixtures, not normal semantic routing.

### 4. `src/hardware_splicer/integrations/qwen_intake_normalize.py`

**Class:** mixed `HEURISTIC` / `SCRIPT_BRAIN`  
**Priority:** P0

The module is presented as LLM normalization replacing keyword scaffolds, but its normal flow still calls `keyword_build_id()` and `reconcile_build_pick()`, and on model failure/offline mode falls back to `_detect_archetype_keywords()`.

The fallback directly maps words like soil/water/pump to watering, rover/wheel to rover, fan/airflow to airflow controller, pan/tilt to pan-tilt, and gripper/claw to gripper.

**Target state:**

- model response validated against typed schema and permitted catalog IDs;
- no semantic keyword result silently promoted into canonical archetype;
- unavailable model => unresolved semantic interpretation or explicit offline compatibility result, not fabricated certainty;
- any fallback is labeled with provenance and cannot raise authority.

### 5. `src/hardware_splicer/project_intake.py`

**Class:** mixed `CONTRACT`, orchestration, and inherited `SCRIPT_BRAIN`  
**Priority:** P1

The orchestration itself is legitimate. The risk is that `detect_archetype_llm()` feeds an archetype into assumptions, missing-info logic, salvage planning, compile-spec selection, scenario naming, expected authority, and eventually a recommended catalog build.

Because the upstream archetype can still be keyword-derived, one semantic guess has a wide blast radius.

A second risk is `salvage_package.recommended_build_id` overriding the archetype. That recommendation must be audited for provenance before it is allowed to steer canonical planning.

**Target state:**

- carry interpretation provenance with archetype/build candidate fields;
- distinguish `declared`, `model_proposed`, `legacy_heuristic`, and `verified_compatible`;
- no downstream step treats `legacy_heuristic` as declared fact;
- compile may use an accepted candidate but must not infer acceptance from routing confidence.

### 6. `src/hardware_splicer/engineering_planner.py`

**Class:** mixed `CONTRACT` / `SCRIPT_BRAIN`  
**Priority:** P1

Positive cleanup already exists on the current branch: a legacy intake archetype is no longer passed into robot topology as if it were declared robot truth; only an explicit structured `robot_genre` is used as a hint. Tests now pin that a wrong legacy archetype cannot override an explicit quadruped brief.

Remaining script-brain:

- `normalize_engineering_intake()` detects evolve/repair/modify/greenfield mode using prose token lists (`field failure`, `brownout`, `repair`, `salvage`, `modify`, `upgrade`, etc.).

This is lower risk than component selection because mode is workflow routing, but it is still semantic interpretation from prose.

**Target state:**

- structured mode from user/model proposal when available;
- deterministic inference only from explicit structured state (failure event, repair object, baseline revision, change request);
- prose-token fallback labeled non-authoritative or removed from model-first paths.

### 7. `src/hardware_splicer/robot_topology.py`

**Class:** mixed `CONTRACT` / `SCRIPT_BRAIN`  
**Priority:** P1

The Pydantic topology models, identity validation, link/joint reference checks, stable IDs, and authority fields are `CONTRACT` and should remain deterministic.

`detect_robot_genre()`, however, contains keyword families mapping prose/part labels to quadruped, mobile manipulator, robotic arm, drone, rover, pan-tilt, and gripper.

The current engineering planner has already reduced one major authority leak by refusing to feed the legacy intake archetype into this function as a hint. That is useful, but the topology classifier itself is still semantic script brain.

**Target state:**

- explicit `robot_genre` remains valid structured input;
- model may propose a genre with evidence/rationale;
- topology builder deterministically validates/builds a topology from typed structure;
- unknown prose should not silently become a genre.

### 8. `src/hardware_splicer/intent_clarifier.py`

**Class:** mostly improved `HEURISTIC`, one remaining semantic heuristic  
**Priority:** P2

Current branch improvement: clarification answers are preserved as literal `declared` observations with `interpretation_status: unresolved`. Older behavior that converted prose answers into guessed voltages, loads, or specific catalog modules has been removed. This is the correct direction.

Remaining issue: `_needs_clarification()` still uses a `vague_tokens` list (`something`, `gadget`, `device`, `project`, `board`, `hardware`) to decide whether clarification is required.

This is acceptable only as a low-authority UX trigger because it does not manufacture engineering facts. It should not become canonical intent classification.

### 9. `src/hardware_splicer/dual_agent_cleanroom.py`

**Class:** `CONTRACT`  
**Priority:** preserve and harden

The new cleanroom boundary currently:

- rejects forbidden outer-only context keys recursively;
- canonicalizes source collection ordering;
- requires model source references to resolve to product-visible source IDs;
- marks authority effect `none`;
- keeps fabrication/flash/power/motion/operation/release authority false.

This is exactly the type of determinism the cleanup should preserve.

**Hardening needed:** forbidden-key filtering is necessary but not sufficient against semantic leakage. A field can leak a golden answer under an innocuous key. Scenario construction must therefore be allowlist-based where practical, and cleanroom fixtures should contain explicit leakage probes.

### 10. `src/hardware_splicer/dual_agent_cleanroom_api.py`

**Class:** `CONTRACT`  
**Priority:** preserve and harden

Current branch improvement:

- caller supplies mission + expected revision, not a snapshot;
- server loads persisted project state;
- stale revisions are rejected;
- constraints come from persisted snapshot, not the evaluator;
- turn is evaluation-only and does not mutate project state or authority.

This prevents an evaluator from quietly handing the embedded operator the expected answer in a caller-provided snapshot.

## Cross-cutting risks still to audit

The next inventory pass should inspect these areas before semantic shortcut removal is considered complete:

- salvage resolver / salvage bridge build recommendations;
- module resolver and part-to-module mapping;
- firmware scaffold defaults derived from archetypes;
- robotics platform builders and geometry templates;
- electrical trust/simulation paths for domain-name special cases;
- marking/hardware detector logic in `apps/circuit-ai`;
- demo-name/build-ID branches in production code;
- regression corpora whose expected outputs encode the existing keyword router;
- LLM prompts that contain golden catalog routing examples so specific that they recreate the same script brain inside the prompt.

## Immediate refactor sequence

### Tranche A — baseline and provenance

1. Keep dependency manifests truthful across package install and `make setup`.
2. Keep route-composition tests tied to concrete HTTP operation registration rather than router implementation detail.
3. Keep compose finalization tests on the current public finalization contract rather than deleted private seams.
4. Add interpretation provenance where archetype/build/genre fields cross into project planning.

### Tranche B — remove architecture selection by keywords

1. Demote `keyword_build_id()` from decision authority to an explicit legacy/offline compatibility helper.
2. Stop `reconcile_build_pick()` from allowing keyword routing to silently override a valid model proposal.
3. Change model failure from `keyword certainty` to an unresolved/proposed state on model-first paths.
4. Add tests using paraphrases and unknown components that intentionally do **not** contain golden keywords.

### Tranche C — remove component selection by prose regex

1. Split module registry/capability lookup from natural-language `MODULE_HINTS`.
2. Introduce typed capability requirements as the input to deterministic catalog querying.
3. Let the model propose requirements and compare compatible candidates.
4. Keep all candidate choices at proposed authority until explicit human acceptance and deterministic verification.

### Tranche D — topology/mode cleanup

1. Remove prose keyword genre detection from model-first topology creation.
2. Prefer explicit structured mode/genre and model-proposed typed state.
3. Preserve deterministic topology/reference validation.
4. Keep UX-only clarification heuristics non-authoritative.

## Acceptance tests for every tranche

A semantic shortcut is not considered removed until all of the following are true:

- a paraphrase without the old trigger keywords reaches the same defensible engineering state;
- an unfamiliar but capability-equivalent component does not collapse to a favorite catalog part;
- unknown evidence stays unknown rather than being coerced into the nearest demo archetype;
- source ordering does not change the operator's evidence set;
- the embedded operator cannot see source code, golden answers, expected architecture, or outer analysis;
- every referenced evidence ID resolves to persisted product-visible evidence;
- deterministic safety/authority gates remain fail-closed;
- existing golden cases either remain defensible or are deliberately corrected with a documented reason;
- CI tests behavior/authority rather than the removed private implementation seam.

## Working principle

The goal is not to replace deterministic engineering with probabilistic AI.

The goal is:

> **model reasoning proposes meaning; deterministic systems validate facts, constraints, identity, evidence, execution, and authority.**
