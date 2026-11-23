# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- **Now:** the owner, running their own hardware projects (cyberdecks, pen plotters, salvage builds, repair) as a one-person workshop. Confirmed 2026-11-18.
- **How they use it:** agent first, human reviews (owner, 2026-11-22).
  - AI agents (Claude Code, Codex and the HS agent through the API and MCP) drive the engineering work.
  - The owner sits at a desk on a large screen. They set the objective, follow what the agent researched and ran, inspect the evidence, make the strategy decision, and authorize anything with physical consequence.
  - Phone use is for checking status only.
- **Next:** friends and early collaborators given access to the same workshop.
- **Later:** the staff of a hardware business built on this, serving paying customers. Not yet built; nothing may imply customers exist today.

## Product Purpose

Hardware Splicer turns an engineering goal, or a pile of owned and salvaged parts, into a digital project. Every claim in the project carries the evidence behind it: CAD, simulations, KiCad checks and source-pinned external tools. Success is a project the owner can trust because nothing is shown as more proven than it is.

The canonical mission (`docs/HARDWARE_SPLICER_MISSION_FREEZE.md`) is an engineering problem solver and workshop operator. It works through this loop:

1. Understand the outcome.
2. Research and map existing options.
3. Choose a strategy: build, buy, salvage, repair or adapt.
4. Operate real tools.
5. Produce deliverables.
6. Verify and iterate on the same project.
7. Keep software evidence separate from physical proof.

## Positioning

- **Authority is never implicitly upgraded.** Importing, composing, simulating and reviewing report state; only evidence promotes a claim. Release assessment lists blockers rather than declaring anything ready.
- **External tools are vetted.** Tools discovered from GitHub run only after human review, pinned to an exact commit, licence-checked, without network and with hashed evidence.
- **Owner's choice for the interface (2026-11-22):**
  - **A cross-domain loop.** One objective is carried through ECAD (KiCad), MCAD/3D (CadQuery, STEP/GLB, SolidWorks-class CAD as a target), simulation, firmware and sourcing in one place, all the way to the whole device: PCB, mechanics and how they fit. Most PCB and electrical projects stop at the board and its simulation.
  - **Strategy, not just design.** HS decides build vs buy vs salvage vs repair with evidence, before anything is drawn.
- **Who to compare against:** for competitive positioning, compare against the GitHub-signal side (repository discovery, repositories turned into tools, MCP registries, sandboxed agent execution). Engineering workspaces and open-source PCB tools are interaction references, not rivals.

## Operating Context

- Digital-only for now: no physical builds, purchases or power-on are performed (owner decision, 2026-11).
- Work happens in projects with saved revisions. A project may start from a goal, from owned parts, or from one of the registered reference studies (drone, Fielddeck, pen plotter and others).
- Several AI agents (Claude Code, Codex) work on the repository; the app is the owner's console onto their results.
- The interface need not copy the rigid tabs, layers and mode switching of CAD and EDA tools: because an AI drives, views can be composed around the question being asked (owner, 2026-11-22).

## Capabilities and Constraints

- Backend: FastAPI product API (`hs-serve`, default 127.0.0.1:8787) and an MCP gateway; local disk and SQLite state; single tenant today.
- Packaging decision (2026-11-18, recommended by Claude after the owner asked for a recommendation):
  1. Serve the built UI from the backend on one port first.
  2. Next, deploy to a VM behind nginx with real per-user sign-in, so friends can use it.
  3. Desktop or public SaaS later, only once the business needs them.
- The UI never computes or upgrades an authority label and never shows "build-ready" or "ready" badges. Labels and blockers come from the backend verbatim. Missing links read "unknown / not linked / not tested". A changed revision invalidates the evidence downstream of it.
- No in-app per-user authentication exists yet.
- Frontend: React 18 + Vite 6 (`apps/splice-ui`). It uses three.js for 3D, KiCanvas for KiCad, a Rust/WebAssembly module for scene geometry, and strict TypeScript for the status, persistence and API modules.

## Evidence on Hand

- Registered digital studies with saved revisions: HS-3G-B drone, Fielddeck 7 and the 5-inch revision, Ender 3 pen plotter, PCB inspection nest.
- The Fielddeck scene records: 38 parts with their geometry basis, 5 interfaces with open checks, blockers, a blocked alternate and a revision diff. Also a CAD face-fit measurement and change-dossier evidence.
- Sealed holdout evaluations: five unseen devices (14 of 15 correct, 1 abstention) and Ferris Sweep v2.2 (4 correct, 1 abstention). The developer agent chose the cases.
- Nothing has been fabricated, bought or measured. No customers, testimonials or revenue exist; none may be shown.

## Product Principles

1. Show the evidence, not a verdict: every claim names its authority and source.
2. Unknown is a first-class state; never fill it with a guess.
3. The project, not the tool or study, is the unit of work.
4. Built for one owner today, structured so collaborators can join without a rewrite.
5. The device is the centre: the screen shows the whole assembly, and questions about fit, connection and choice compose the view, rather than tabs and layers.
