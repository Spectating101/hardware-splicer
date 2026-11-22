# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Agent first, human reviews (owner, 2026-11-22). An AI agent drives the engineering work through the API and MCP. The person at the screen is a technical owner at a desk on a large screen. They set the objective, watch what the agent researched and ran, inspect the evidence, make the strategy decision and authorize anything with physical consequence. Phone use is for checking status only.

## Product Purpose

Hardware Splicer is an AI-driven, general-purpose engineering problem solver and workshop operator (canonical: `docs/HARDWARE_SPLICER_MISSION_FREEZE.md`). For one engineering objective, it works through this loop:

1. Understand the outcome and its constraints.
2. Research and map existing options.
3. Choose a strategy: build, buy, salvage, repair, adapt or fabricate.
4. Operate real engineering tools.
5. Produce concrete deliverables.
6. Verify and iterate on the same project.
7. Keep software evidence separate from physical proof.

Success is a project-specific improvement to a useful engineering outcome, with a clear record of what verified it and what remains unproven. Tests, plans, checklists and demos are supporting evidence, never the outcome.

## Positioning

Chosen by the owner, 2026-11-22:

- **A cross-domain loop.** One objective is carried through ECAD (KiCad), MCAD/3D (CadQuery, STEP/GLB, SolidWorks-class CAD as a target), simulation (SPICE, physics), firmware and sourcing in one place. Neighbouring tools each own one domain: Onshape, SolidWorks and Zoo for MCAD; Flux and AllSpice for PCB; Devin and GitHub Agent HQ for code. Their AI is a companion inside that one domain.
- **Strategy, not just design.** HS decides build vs buy vs salvage vs repair with evidence, before anything is drawn.

For competitive positioning, compare against the GitHub-signal side: repository discovery, turning repositories into tools, MCP registries and sandboxed agent execution. Engineering workspaces are interaction references, not positioning rivals.

## Operating Context

- **Driving the work:** the agent works through the HS API/MCP. The UI is where a person follows the project, reviews artifacts and evidence, and makes decisions.
- **Real artifact types:**
  - KiCad schematics and PCBs, with ERC/DRC receipts;
  - CadQuery output, STEP and GLB 3D models with per-part sidecars;
  - SPICE and physics simulation results;
  - firmware builds;
  - BOM and sourcing records;
  - bench captures and gates;
  - revision history and Compare;
  - Engineering Change Dossiers exchanged with Policy Lab and Cite;
  - GitHub-signal tool adoption records (commit pin, licence, network-isolated run, hashes).
- **Reference projects on hand:**
  - Fielddeck 5-inch display revision (cyberdeck, change dossier);
  - HS3G-B drone;
  - Ender-3 pen-plotter donor;
  - Fielddeck 7;
  - low-voltage witness fixture.

## Capabilities and Constraints

- **Authority is never implicitly upgraded.** Importing, composing, diffing and reviewing report state; none of them promote an engineering claim. No "ready" or "approved" badges, and no approval-green colours. Missing links read "unknown / not linked / not tested". A changed revision invalidates the evidence downstream of it.
- **Software evidence never claims physical proof.** Physical power, motion, fabrication and flight need recorded human authorization.
- **Frontend stack:** React 18 + Vite 6, `apps/splice-ui`, served by `product_api:app`. three.js for 3D, KiCanvas for KiCad, a Rust/WebAssembly module for heavy scene geometry, and strict TypeScript for the status, persistence and API modules.
- **Undecided:**
  - SolidWorks integration path (the format and viewer for SLDPRT/SLDASM; STEP is the current exchange);
  - multi-user review;
  - hosting target.

## Brand Commitments

- Name: Hardware Splicer (HS).
- The tagline from the design principles doc: "AI proposes → deterministic systems constrain → bench evidence decides → human authorizes."
- IBM Plex Sans and Mono are in use and now self-hosted. They are the incumbent choice, not a binding brand rule.

## Evidence on Hand

- **Committed evidence:**
  - real project stores and scene manifests (`projects/*/scene.json`);
  - Fielddeck GLB/STEP models with sidecars;
  - change-dossier evidence (`docs/status/generated/change-dossier-20261120*`);
  - native study runs;
  - KiCad reference designs (`hardware/reference_designs/`);
  - GitHub-signal adoption evidence (`examples/github_signals/`).
- **Not demonstrated** (do not imply otherwise):
  - a complete, independently verified custom drone design or physical build;
  - any physical validation of the Fielddeck revisions;
  - customers, testimonials or pricing.

## Product Principles

1. **The objective is the unit of work.** Every screen answers which objective it serves and where that objective stands in the loop.
2. **Strategy comes before drawing.** The decision between build, buy, salvage and repair is a first-class, reviewable record, not a hidden step.
3. **The artifact leads.** The engineering artifact, in its native form (schematic, board, model, plot), dominates. Chat and prose are secondary.
4. **The agent shows its work as typed steps.** Each tool run, source and decision is inspectable by domain, not as a wall of chat or log.
5. **The human decides at gates.** Decisions and authorizations wait in one place, each with its evidence and with what it would unlock.

## Accessibility & Inclusion

No product-specific standard is recorded. Keep 44 px targets on touch, visible keyboard focus and state words beside every colour.
