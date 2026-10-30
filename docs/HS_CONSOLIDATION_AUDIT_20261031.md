# HS engineering consolidation — audit and acceptance ledger

**Date:** 2026-10-31
**Source:** actual GitHub PR heads and native workflow logs; no physical devices operated.
**Scope:** engineering consolidation, not a new architecture, portfolio management or product-readiness assertion.

## Audit of existing work

| Branch/PR | Confirmed Oct 31 status | Classification | Dependency / missing validation |
|---|---|---|---|
| [#229 ESP32 sensor](https://github.com/Spectating101/hardware-splicer/pull/229) | Four workflows passed on `3e7aa66f`: Hardware-Splicer, Core Diagnostics, Cross-Domain Sensor 001 Evidence, native OpenSCAD + target PlatformIO. | **CONSOLIDATE, flagship** | Needs independently reconciled native artifacts and measured physical component fit, sensor electrical interface, real-device operation |
| [#230 Crazyflie system](https://github.com/Spectating101/hardware-splicer/pull/230) | General checks passed on `efa2fff8`. Native template audit passed but real flight-firmware Kbuild and Crazyflow simulation failed (logs linked below). | **RESEARCH / CONSOLIDATE as harder second benchmark** | Correct genuine upstream integration errors, native new-deck schematic, source-bound deck driver, calibrated dynamics |
| [#224 Buck converter](https://github.com/Spectating101/hardware-splicer/pull/224) | All four workflows passed on `1f1d65ee` after Python syntax repair; current electrical design remains schematic-topology proposal. | **PARK** | Selection and ratings of real semiconductor/magnetics/capacitors, electrical model + native KiCad schematic and routed PCB |
| [#227 Engineering landscape](https://github.com/Spectating101/hardware-splicer/pull/227) | Research snapshot committed; not a verified toolchain implementation. | **RESEARCH** | Exact upstream license, API and acceptance comparisons before reuse |
| [#225 Printer operator](https://github.com/Spectating101/hardware-splicer/pull/225) | Green earlier CI; stage-only OctoPrint connector, no physical print. | **PARK** | Device protocol acceptance, authorization, measured print results |
| [#226 Fleet](https://github.com/Spectating101/hardware-splicer/pull/226) | Stacked on #225; draft with Moonraker/fleet candidate capabilities. | **PARK, dependent on #225** | Finish actual protocol tests / compatible machine availability, no broad adoption here |
| [#214 Commercial routing](https://github.com/Spectating101/hardware-splicer/pull/214) | Separate commercial/value infrastructure; out of scope for engineering gate. | **PARK separately** | Avoid implying commercial value from standalone technical CI |

No unrelated PR merges are recommended in this phase.

## Actual upstream microdrone failure causes

Evidence: [PR #230 original latest CI](https://github.com/Spectating101/hardware-splicer/actions/runs/40565205700).
- The nested STM32 Kbuild failed with `No such file or directory: ../../tools/make/oot.mk` from the custom app Makefile. It was relative to the wrong evaluation directory.
- Crazyflow 0.4.0 failed with `AttributeError: 'NoneType' object has no attribute 'eglQueryString'` in PyOpenGL on headless GitHub Actions. The earlier SciPy array API startup flag had been repaired but did not repair EGL.
- Upstream historic KiCad connector audit passed. It is neither a modern new schematic nor an electrically qualified sensor PCB.

The stacked microdrone repair PR [#231](https://github.com/Spectating101/hardware-splicer/pull/231) uses a Makefile-path-anchored vendor root, **adds upstream's required top-level app `Kbuild`**, and requests headless OSMesa software GL. The later Kbuild-link failure exposed by the first patch was real: `examples/hs_sensor_deck/built-in.o` was missing. Upstream's official example has `obj-y += src/` in root `Kbuild`, which our new app initially lacked. The fixes preserve vendor commit, design digest and no-physical-authority gates. They require latest-commit reruns for a passing verdict.

## ESP32 integration structure

Same source spec:
- Device planner produces exact module and wiring contracts.
- Application builder generates an original source ZIP with source-spec/plan revision embedded.
- Real PlatformIO compiles the ESP32 Arduino target to binary and ELF.
- Mecha Splicer generates OpenSCAD, and native OpenSCAD + trimesh inspect geometry, USB, vents and retained lid fastener geometry.

Prior jobs independently verified each domain; the missing connection was an actual cross-job **hash/evidence acceptance package**. PR [#232](https://github.com/Spectating101/hardware-splicer/pull/232) uses same-run CI artifacts to close that documentation/authority gap without changing engineering designs.

## Unresolved technical gaps and acceptance thresholds

| Question | Existing defensible result | Outstanding gate |
|---|---|---|
| Is source spec → firmware/CAD deterministic? | Yes for tested example | Cross-run and cross-job identical SHA check on independent real files |
| Is there a native ESP32 firmware build? | Yes, PlatformIO Core 6.1.18, Espressif32 6.10.0 | Real-board pinout/I2C behavior and instrumentation |
| Are geometry files native engineering outputs? | OpenSCAD STL and independent trimesh inspections passed | Measured PCB/fastener fit, retained lid strength, thermal/ventilation |
| Is electronics independently engineered? | Catalog module wiring plan and pin-bound firmware | Native custom KiCad schematic/board/footprint net identity, ERC/DRC |
| Is simulation predictive? | Only bounded geometry and firmware host-model checks | Physical/material parameters and independent validation (no gratuitous simulation) |
| Are BOM and sourcing production ready? | Catalog module identities | Exact manufacturer part numbers, revs, distributor evidence, availability, qualification |
| Is equipment authorized for activation? | **No** | Independent operator approval after physical measurements |

## Acceptance report and external comparison plan

A software-only gate passes when native outputs from both jobs have identical spec/receipt, all actual file hashes match their native tool reports, and every physical-release field is false. It fails on a corrupted or stale source, wrong revision, missing native files or artificial promotion to actual measurements.

**Not yet performed:** equal-input head-to-head with competent domain engineer, general-purpose model and HS. No speed, cost, model price, native circuit success rate, human-correction counts or superiority claim should be reported without data. Scope the comparative benchmark to the same ESP32+BME280 spec, pins, enclosure, exact CAD/firmware versions, and explicit verification time/cost budgets. External tools may be incorporated if they outperform a local bridge.

## Atlas handoff

A successful acceptance job exports `ATLAS_CAPABILITY.json`. Atlas receives verified supported domains, exact source and acceptance digests, known blockers, entry points and *no physical authority*, without invoking a shared registry or database. Policy Lab remains outside the runtime dependency graph.

**Phase exit authority:** `software_candidate_only`. Physical assembly, power-on, flashing, printing, manufacture and commercial release remain separate explicitly unapproved actions.
