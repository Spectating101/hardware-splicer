# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- **Now:** the owner, running their own hardware projects (cyberdecks, pen plotters, salvage builds, repair) as a one-person workshop. Confirmed 2026-11-18.
- **Next:** friends and early collaborators given access to the same workshop.
- **Later:** the staff of a hardware business built on this, serving paying customers. Not yet built; nothing may imply customers exist today.

## Product Purpose

Hardware Splicer turns an engineering goal, or a pile of owned and salvaged parts, into a digital project whose every claim carries the evidence behind it: CAD, simulations, KiCad checks, source-pinned external tools. Success is a project the owner can trust because nothing is shown as more proven than it is.

## Positioning

Authority is never implicitly upgraded. Importing, composing, simulating and reviewing report state; only evidence promotes a claim, and release assessment lists blockers rather than declaring anything ready. External tools discovered from GitHub run only after human review, pinned to an exact commit, licence-checked, without network, with hashed evidence.

## Operating Context

- Digital-only for now: no physical builds, purchases or power-on are performed (owner decision, 2026-11).
- Work happens in projects with saved revisions; a project may start from a goal, from owned parts, or from one of the registered reference studies (drone, Fielddeck, pen plotter and others).
- Several AI agents (Claude Code, Codex) work on the repository; the app is the owner's console onto their results.

## Capabilities and Constraints

- Backend: FastAPI product API (`hs-serve`, default 127.0.0.1:8787) and an MCP gateway; local disk and SQLite state; single tenant today.
- Packaging decision (2026-11-18, recommended by Claude, owner asked for a recommendation): serve the built UI from the backend on one port first; next, deploy to a VM behind nginx with real per-user sign-in so friends can use it; desktop or public SaaS later, only once the business needs them.
- The UI never computes or upgrades an authority label and never shows "build-ready" or "ready" badges; labels and blockers come from the backend verbatim.
- No in-app per-user authentication exists yet.

## Evidence on Hand

- Registered digital studies with saved revisions: HS-3G-B drone, Fielddeck 7 and 5-inch revision, Ender 3 pen plotter, PCB inspection nest.
- Sealed holdout evaluations: five unseen devices (14 of 15 correct, 1 abstention) and Ferris Sweep v2.2 (4 correct, 1 abstention), cases chosen by the developer agent.
- Nothing has been fabricated, bought or measured. No customers, testimonials or revenue exist; none may be shown.

## Product Principles

1. Show the evidence, not a verdict: every claim names its authority and source.
2. Unknown is a first-class state; never fill it with a guess.
3. The project, not the tool or study, is the unit of work.
4. Built for one owner today, structured so collaborators can join without a rewrite.
