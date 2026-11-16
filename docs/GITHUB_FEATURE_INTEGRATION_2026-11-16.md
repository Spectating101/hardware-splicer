# GitHub features integrated November 16 2026

This integration brings useful GitHub functionality into the active checkout while preserving the existing engineering mission and local work. It starts from `445a8945`, includes current remote main `38dbad2b`, and combines the reviewed branches below. GitHub's main branch and PR states are unchanged.

The active checkout uses local branch `integration/github-features-20261116`. The previous `test/source-evidence-handoff-20261020` branch remains available at its original commit.

## Features now available

| Capability | Imported work | Where to use it |
| --- | --- | --- |
| Discover, evaluate and dispatch native engineering tools | Main's #280–#284: GitHub signal discovery, capability selection, durable remote jobs, worker inventory and admission | [Task router](GITHUB_SIGNAL_TASK_ROUTER_20261105.md), [remote workshop](HS_REMOTE_WORKSHOP_CONTROLLER_20261105.md), [worker pool](HS_WORKER_POOL_ADMISSION_20261105.md) |
| Compare construction strategies and preserve requested functionality | #337 consolidation, including #217, #230/#231, #235, #276, #278 and #291 | [Microdrone reference](SYSTEM_EXAMPLE_MICRODRONE_001.md), [drone lab](../examples/drone_lab/README.md), [build versus buy](../examples/arbitrage_lab/build_vs_buy/README.md) |
| Generate and inspect the HS-3G drone design | #338: source inputs, CAD generator, mass/propulsion/cost calculations and package checks | [HS-3G package](../examples/drone_proving_ground/README.md) |
| Execute one bounded native engineering work order and recover interrupted KiCad stages | #315/#343 plus the source-custody repair | `scripts/hs_workshop_operator.py`, `scripts/hs_spi_checkpoint.py` |
| Reconstruct a source-backed keyboard PCB after a virtual cut | #342: KiCad extraction, copper islands, cut search, repair loop, bridge/remount boards, firmware/source and matrix checks | [Keyboard reconstruction](../examples/arbitrage_lab/keyboard_splice/README.md), `scripts/hs_keyboard_splice_probe.py` |
| Report build readiness against the actual goal, requested parts and KiCad results | Isolated #346 commits, without importing the unrelated repair/hinge stack | Existing intake, SDK and MCP entry points; both goal coverage and requested-part gates are retained |
| Keep optional dependencies optional | #339 plus the MCP collection repair | CAD tests skip explicitly without the CAD extra; SDK/REST checks still run without MCP |

The new `keyboard-splice` extra and the existing `cad` extra are both retained in `pyproject.toml`. Shapely 2.2.0 is installed in this checkout's existing virtualenv, enabling the new copper-island solver. Native KiCad remains a separate interpreter/toolchain; CAD regeneration was also exercised in the existing CAD environment.

The original branch's 27 unique commits, broader engineering charter, source bundles, Copilot opt-in integration, and cross-domain engineering work are preserved. The three original uncommitted files are preserved byte for byte.

## Integration decisions

The goal-coverage cherry-pick conflicted with #217's requested-part check in `project_intake.py`. The combined implementation applies goal coverage and then passes the requested-part comparison into the same design-quality gate. A new end-to-end regression proves that an unrelated scaffold and a missing requested servo are both reported.

The keyboard branch and the consolidation branch added different optional dependency groups at the same location. Both groups are retained.

The native operator pilot was actually rerun after integration. Its source digest changed to `9d00c1842d1e66970567bd64e919443fd35acdc6ee85136137f4c1155bc55c78`; its fresh native verification receipt remains `6fa005f1d3544275997c8588af277277a67bef6c8d30c1c4da2eab356982596b`. The committed pilot now describes the combined source rather than inheriting a stale success.

## Validation of the combined checkout

| Check | Result |
| --- | --- |
| Request fidelity, remote dispatch/worker inventory, microdrone reference, proxy process and pricing tests | 81 passed |
| Goal coverage, requested-part coexistence, KiCad trust and MCP defaults | 36 passed |
| Keyboard feature tests | 121 passed |
| Tool discovery/router, multi-CAD, product ecosystem, function selection and related feature tests | 126 passed |
| Native SPI capability/reference, workshop, checkpoint and source-custody tests | 66 passed, 3 native-binding skips in the project virtualenv |
| Existing source-bundle, cross-domain, drone and Copilot tests | 29 passed, 6 optional skips |
| Intake, SDK, scratch compiler, JARVIS, fabrication planning and scoring regression | 97 passed, 4 optional skips |
| HS-3G tests in the native CAD environment | 24 passed |
| Splice UI tests | 82 passed |
| Splice UI production build | Passed |

These were the initial focused test batches, with overlapping coverage. The subsequent full verification below runs the complete root Python suite. Remote workers were unavailable, so both full runs used one local test worker, two CPU cores and single-threaded BLAS settings.

### Full suite verification

The complete rerun on source commit `c54d10fb5bb165ed5bfe6dd4c7dcb91c827eaf00`, including the three preserved local files, passed: **4,202 passed, 32 skipped, zero failures**, plus **three passing subtests**, in 927.66 seconds. The separate Mecha-Splicer and 3D-Splicer suites passed **32** and **15** tests respectively. Optional skips cover unavailable CAD/native bindings, external fixtures, live providers and configured toolchains.

The first full run exposed five failures: three manifestations of a cleanroom evidence-ID regression, one stale executor fixture, and one native KiCad DRC timeout. The cleanroom guard now rejects unresolved references retained by source-alias normalization, with regressions for requirements, candidates and actions. The provenance negative fixture now uses an actually unimplemented tool; ERC is an implemented executor. The timeout case passed in isolation and in the complete rerun, with a fresh zero-error DRC report. Its independent ERC errors still block build and fabrication readiness; the timeout policy and readiness checks are unchanged.

Both runs, exact source revisions, skipped-test reasons, fixes and log hashes are preserved in the [full-suite verification receipt](status/generated/full-suite-verification-2026-11-16.json). Local JUnit reports and logs are under `.cache/hardware-splicer/full-suite-20261116/`. Generated artifacts changed by the Mecha tests were restored; the original three local files retain their starting SHA-256 hashes.

A real native SPI operator run passes its engineering checks while reporting `verified_design_only_physical_blocked`. An interrupted checkpoint run reuses three completed stages and executes the remaining two; its verification receipt is byte-identical to the uninterrupted five-stage run. A fresh controlled six-key keyboard reconstruction connects its required modeled copper groups, passes all 64 ideal switch combinations, and generates a four-channel native interposer with zero DRC errors or open connections. The overall keyboard verdict remains `BLOCKED_REFERENCE_ONLY`. Real CAD regeneration also produces the HS-3G STEP/STL package; its battery-current and cutter-rule checks remain blocking.

The three MCP proxy failures described in the earlier catchup were caused by subprocesses resolving the other editable checkout. They pass here with `PYTHONPATH=src`, which points both pytest and its subprocesses at the combined source.

Exact imported refs and native outcomes are recorded in the [integration receipt](status/generated/github-feature-integration-2026-11-16.json).

## Useful starting commands

From the repository root:

```bash
PYTHONPATH=src .venv/bin/python scripts/hs_workshop_operator.py --list
PYTHONPATH=src .venv/bin/python scripts/hs_keyboard_splice_probe.py --help
/usr/bin/python3 scripts/hs_spi_checkpoint.py --help
```

Use the native KiCad interpreter for actual SPI execution. Use an environment with the `cad` extra for HS-3G regeneration. Model providers and remote dispatch still require their explicit configuration and approval paths.

## Work deliberately left separate

The #318–#336 repair-investigation and hinge chain requires integration together with #344/#345's truth corrections; it was not pulled indirectly through #346's base branch. The #340/#347 fabrication stack changes the SPI reference board and order package, so it remains separate from this source-preserving integration. U1 placement and the frozen-release relationship still need resolution there.

No physical cut, fabrication, power-on, flight or production release is established by these software integrations.
