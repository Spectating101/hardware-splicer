# Hardware Splicer — Mission and Engineering Operating Contract

**Frozen 2026-10-20. Status: CANONICAL DIRECTION.**

This document exists because multiple implementation rounds drifted from the user's engineering objective into isolated reasoning benchmarks, template assembly exercises and narrow component-compatibility checkers. Read this before selecting work, proposing a milestone, designing an agent, or interpreting a test result. Changes to the mission require an explicit user direction; implementation refinements do not.

## Mission

**Hardware Splicer is intended to be an AI-driven, general-purpose engineering problem solver and workshop operator.** It should investigate an engineering objective, discover and evaluate existing work, choose a feasible engineering approach, use specialized software and models, design or adapt hardware and firmware, verify what it can, and produce a concrete fabrication, construction, repair, reconstruction or assembly outcome with explicit physical-validation requirements.

Its scope is *not confined* to electronics, drones, robots, circuit repair, salvaged parts, or making incompatible parts fit. The name “Splicer” must never force donor substitutions. Buying a reliable commercial module, reusing a documented open design, modifying donor hardware, creating a PCB, or fabricating a new mechanical part are alternative engineering strategies. The system chooses based on objective, evidence, engineering feasibility, resources, time, cost and utility.

## User objective is the persistent unit of work

Example user assignment: **“Build an affordable and useful drone from obtainable parts.”** The agent should not quietly replace this objective with “benchmark diagnostic test selection”, “duplicate a preconfigured kit”, “classify a donor component”, or “pass unit tests”. These are potential tools or substeps, not the goal. A real project remains open until it produces an assessable engineering artifact and clearly separates unresolved work from verified work.

Projects may include consumer electronics, handheld consoles, cyberdecks, salvage/repair, robots, mechanical systems, practical chemical/physical engineering and other feasible disciplines. No single example project defines the architecture or the product.

## Required integrated operating loop

1. **Understand the engineering outcome and constraints.** Clarify function, user value, available parts/tools, safety envelope, budget and acceptance criteria. Where assumptions are necessary, label and test them rather than silently inventing facts.
2. **Research and map options.** Actively discover primary manuals, reference designs, schematics, datasheets, established repos, ecosystems, purchasable parts, repair records and prior projects; inspect and verify rather than merely list tools or companies.
3. **Compare solution strategies.** Consider build vs buy vs salvage vs repair vs adaptation vs custom fabrication; make engineering/economic trade-offs, choosing an approach for a reason instead of imposing splicing or a kit.
4. **Orchestrate existing capabilities.** The agent should invoke HS electrical, mechanical, CAD, firmware, materials, sourcing, verification, simulation and project tools as relevant. Prefer integrating mature open engineering software (e.g. KiCad, PX4, FreeCAD, SPICE) over rebuilding it without necessity. The agent must genuinely operate the tools and interpret results, not merely enumerate them.
5. **Produce concrete engineering deliverables.** Depending on the task: justified architecture, exact part identities and alternatives, interface contracts, compatibility evidence, quantitative calculations, modifiable CAD/PCB/firmware outputs, BOM with real sourcing and costs, assembly or repair procedures, and traceable validation evidence.
6. **Verify, repair and iterate on the SAME project.** Detect technical or economic blockers, use the appropriate HS capability to correct them, regenerate affected artifacts, and measure progress against the original engineering goal. Do not substitute an ever-growing collection of internal demonstrations.
7. **Separate software evidence from physical proof.** Simulation, CAD checks, arithmetic and sourced manuals do not certify a real machine. Physical power, motion, hazardous chemistry, fabrication and flight remain subject to appropriate authorization, supervision, testing and local legal requirements. Preserve fail-closed evidence/authority invariants.

## Definition of engineering progress

Progress is **a project-specific improvement that affects the feasibility, quality or completion of a useful engineering outcome**: a verified donor selection, fixed incompatibility, dimensioned adapter, routed and checked board, credible calculations, source-checked firmware configuration, tested simulation, or actionable build package. A checkpoint must report the tangible artifact, what independently verified it, and what remains unproven.

Do **not** equate any of these with delivered hardware capability:
- passing unit tests, synthetic scenarios, or LLM self-evaluations;
- generating JSON outlines, open-question inventories or checklists;
- copying an established assembly manual or cloning a repo;
- detecting an incompatibility without solving it when redesign is feasible;
- attaching AI to a toolbox without a demonstrated agent-driven workflow;
- declaring success simply because a PR, commit, demo or planning file exists.

Unit tests and safety gates remain necessary engineering controls. They are **supporting evidence**, never the primary project outcome.

## Practical milestone and stopping rules

Before adding a tool, benchmark, subsystem or new project, answer:
1. Which currently open **user engineering objective** does this advance?
2. Which exact blocking step in that objective requires this change?
3. What new design/repair/build artifact or independent verification will result?
4. Can an existing external repository or tool perform the task better?
5. What acceptance evidence would distinguish actual advancement from another planning exercise?

If there is no concrete answer, do not add another arbitrary layer. If the project remains incomplete, continue with the next actual blocking engineering step rather than repeatedly asking the user to say “next.” Be candid about what is unverified, unavailable or unsafe.

## First active practical proving ground

**Drone engineering objective:** derive a viable, economically sensible drone from accessible components. Evaluate open existing kits and designs (PX4/Pixhawk, independent donor CAD/electronics, etc.) as competing inputs, not as predetermined answers. Select a strategy, acquire/reference exact component specifications, produce a design and assembly/fabrication deliverables, run real engineering checks and simulations where possible, and record any physical-only validation required. The drone is one integration proving ground, **not a permanent drone-only mission**.

Current status as of freeze: HS has substantial individual engineering tools and some source-backed drone assembly/adaptation evaluations, but **has not demonstrated a complete, independently verified hybrid or custom drone design, fabrication, or physical build**. Do not rebrand preliminary work packages as a successful engineering result.

## Relationship to existing documentation

This charter specifies **future product direction and work selection**, not a claim that those capabilities exist today. Existing `README.md`/`docs/product/` descriptions of the bounded SPI adapter product and evidence/authority contracts remain accurate for their specific validated scope. `docs/MACHINE_PROJECT_SPINE.md` and `docs/INTEGRATION_STACK.md` continue to control engineering truth and physical authority. This charter changes neither their evidence rules nor any safety permissions.

**Short form:** *HS must solve engineering objectives by intelligently using and integrating engineering capabilities, then deliver verifiable physical-world designs or repairs. A better toolbox, another score, or a prettier checklist is not the objective.*
