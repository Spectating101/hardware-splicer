# Repository consolidation (24 November 2026)

The repository had 255 open pull requests, 363 branches, and a `main` 495 commits behind the integration branch where the work lived. This records what was done and how to get anything back.

## What changed

- `main` is the trunk again: the integration line merged in #381 (full suite: 4,751 passed, 0 failed). `integration/github-features-20261116` is retired; new work targets `main`.
- 218 pull requests closed, each with a comment giving the reason: already merged (17), commits contained in a later PR of the same chain, superseded by code on `main`, or stale. Verdicts came from mechanical checks (ancestry, `git cherry`) plus a reading of each remaining PR; chain-containment claims were re-checked by ancestry.
- 38 pull requests remain open, all based on `main`: 19 carry a whole topic (label `consolidated-topic`, title prefixed with the topic) and 19 are standalone.
- 325 branches deleted; 39 remain (`main` and the head of each open PR).

## Nothing was lost

Every branch tip that existed on 2026-11-23 is kept in this repository under `refs/archive/branches/<branch name>` (362 refs). GitHub does not list these refs, but they are fetched by name. To restore a branch:

```bash
git fetch origin refs/archive/branches/<branch>
git push origin FETCH_HEAD:refs/heads/<branch>
```

Then reopen its pull request if it had one. Every closed PR's closing comment names its exact archive ref.

## Open pull requests

### One per topic

- #86 [workbench-rc] Converge Hardware Splicer into reuse-first product RC
- #121 [device-lane] Draft a device from a typed parts list
- #124 [mission-runtime] Let a mission wait for a person's physical evidence and resume
- #131 [fabricator-control-plane] Add capability-driven fabrication lab scheduling and resource arbitration
- #144 [salvage-convergence] feat: read-only evidence-grounded mission review sheet
- #163 [solidcraft-cad-bridge] feat: real end-to-end CAD to MK4S G-code, gated printer dry run, live Codex commissioning guide
- #174 [cad-fem] Validate Kirsch analytical hole stress and screen Mecha double-hole bracket (stacked)
- #192 [unified-engineering] feat(ui): OpenBlueprint DesignPackage bridge and unified HS project explorer
- #218 [mechanical-chemistry-core] Unpack the Lamé parameters in the order scikit-fem returns them
- #222 [kicad-wokwi-intake] WIP: Capture original KiCad UUID at converter parser stage
- #243 [esp32-sensor-cross-domain] feat: make ESP32 sensor a second canonical HS machine product using real native evidence
- #273 [repair-restoration-evidence] feat(hs): integrate evidence-first repair portfolio and first honest whole-product restoration dossier
- #288 [optiplex-signed-erc-worker] Reject malformed findings in signed ERC bundles
- #314 [cyberdeck-cm5-dual-touch] feat(hs): separate 720x1280 panels with real SSH + CM5IO physical first-boot release gate
- #317 [thor-split-qwerty] feat(hs): ZMK dual-controller firmware from Thor split QWERTY PCB matrix
- #345 [restoration-hinge-stack] Report hinge retention and cable saddle as the geometry supports
- #349 [optiplex-f60-a5-plotter] HS: build and verify an A5 inspection-card plotter project
- #369 [witness-fixture] Research: G0–G4 witness build readiness, source-bound replay and physical HOLDs
- #374 [heldout-generality] HS: preregister untouched post-tuning electrical holdout and harden native edits

### Standalone

- #122 Fabrication Mission Runtime: persistent missions, accepted execution, agent trials and red-team hardening
- #158 feat: Open Repair Alliance category evidence for repair mission discovery
- #169 Hardware Splicer Practical Chemistry v2 — Enforced Project Release and Physical Gates
- #189 WIP: Real KiCad SPI PCB + SolidCraft/FreeCAD shell cross-domain device acceptance
- #190 Integrate source-aware hybrid sheet/connector construction comparisons into HS/Mecha
- #202 WIP: Compete by absorbing Wokwi designs into HS Studio with real-source fidelity benchmarks
- #214 feat: consolidate HS commercial value routing across salvage, Product Factory and outcomes
- #215 WIP: Preserve converter-runtime native KiCad UUIDs and verify source-backed visual pin/net identities
- #223 Find I2C address clashes, offer repairs an agent can apply and HS verifies
- #226 WIP: Protocol-neutral HS manufacturing fleet with OctoPrint/Moonraker discovery
- #285 feat(hs): signed opt-in Optiplex KiCad worker, replay-safe enrollment and evidence
- #344 Close audited bypasses in the repair diagnosis gates
- #347 Hardware Splicer: fix the SPI adapter order package to the independent fab check
- #352 Drive ground nets and gate no-connects on an explicit schematic pin policy
- #357 Add source-bound mechanical fixture strategies and cross-project evidence handoff
- #359 Experiment: resolve witness power-envelope corner with replayed 13 Ω load candidate
- #372 HS: generalize held-out KiCad Edge.Cuts to source-audited STEP inspection trays
- #373 Audit witness consolidation scope, evidence hashes and dependency boundaries
- #382 Tidy the repository top level and docs
