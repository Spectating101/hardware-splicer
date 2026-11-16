# GitHub features integrated November 16 2026

This integration brings useful GitHub functionality into the active checkout while preserving the existing engineering mission and local work. It starts from `445a8945`, includes current remote main `38dbad2b`, and combines the reviewed branches below. GitHub's main branch and PR states are unchanged.

The active checkout uses local branch `integration/github-features-20261116`. The previous `test/source-evidence-handoff-20261020` branch remains available at its original commit.

## Features now available

| Capability | Imported work | Where to use it |
| --- | --- | --- |
| Discover, evaluate and dispatch native engineering tools | Main's #280–#284: GitHub signal discovery, capability selection, durable remote jobs, worker inventory and admission | [Task router](GITHUB_SIGNAL_TASK_ROUTER_20261105.md), [remote workshop](HS_REMOTE_WORKSHOP_CONTROLLER_20261105.md), [worker pool](HS_WORKER_POOL_ADMISSION_20261105.md) |
| Compare construction strategies and preserve requested functionality | #337 consolidation, including #217, #230/#231, #235, #276, #278 and #291 | [Microdrone reference](SYSTEM_EXAMPLE_MICRODRONE_001.md), [drone lab](../examples/drone_lab/README.md), [build versus buy](../examples/arbitrage_lab/build_vs_buy/README.md) |
| Generate and inspect the HS-3G drone design | #338: source inputs, CAD generator, mass/propulsion/cost calculations and package checks | [HS-3G package](../examples/drone_proving_ground/README.md) |
| Advance the same drone through a native design iteration | Local follow-up: sourced lower-current powertrain, bounded CAD search, cut/post-drill handoff and independent artifact verification | [HS-3G-B workflow](../examples/drone_proving_ground/revision_b/README.md), operator case `hs3g_drone_revision_b` |
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

### Extended native verification

The complete native run at `35d469fa` exercised **4,240 root cases**: **4,234 passed, three failed, three skipped**, in 1,124.13 seconds. The failures were the two planning regressions described below and the CAD environment's missing `pypdf` dependency in a CLI child process. After the scope refinement at `71ee7de8` and installing the same `pypdf==6.18.1` used by the root environment, **all 105 affected tests passed** in 160.34 seconds. All three failures passed in that follow-up. Across the full run and rechecks, 4,238 unique cases passed and three live-vision cases remain unverified; this is combined coverage, not a second single green full invocation. **29 of the prior 32 skipped cases were exercised successfully.**

The extended verification uses the existing CAD environment with CadQuery, trimesh, PyBullet and native KiCad bindings, plus the root environment's remaining dependencies. Pinned third-party files and the existing pinned vendor-library cache were restored before running the complete root suite. The exact environment, source revisions, hashes, test outcomes and remaining skips are recorded in the [extended verification receipt](status/generated/extended-native-verification-2026-11-16.json).

Enabling the CAD profile first exposed four plant-watering tests that expected all nine production gates to pass despite real KiCad ERC failures. More seriously, the overall project packet still claimed production readiness while its circuit gate and production metrics rejected the same build. Commit `35d469fa` makes production claims and the release dashboard honor both the current circuit receipts and the stored gate. The complete run caught an overreach in that first fix: two planning-only tests also lost their scoped claims. The follow-up confines the veto to production promotion, keeps unfinished designs usable for planning, and exposes circuit failures in their checks and next actions. A rejected project also stops advertising bench-ready or released capabilities. Seven regressions cover native failures, a stale positive summary, goal mismatch, requested-part omissions, clean/scenario-only paths, the saved intake packet, and preservation of planning scope.

Positive evidence-extraction and scoring tests explicitly assume a clean ERC receipt, using the existing `assume_clean_kicad_erc` fixture. They prove the downstream positive path, not that the example circuit is electrically valid. An independent run with real KiCad 9.0.2 still finds four errors: an undriven ground supply, an undriven GPIO34 input, and unconnected MOSFET-module VOUT+ and VOUT- pins. It now reports `claimable=false`, `build_ready=false`, and `production_ready=false`, with eight of nine production gates passing. Artifact creation remains separate from readiness.

Both Java routing entry points now force headless mode. The bounded native checks passed without a display; no further routing feature work was added.

The public-source tests use the original RPI_DEV archive at `ebdfcffac2f03c01222ed851d44bf75bde5b10ad`, dinodeck BOM at `7762e2f744ad2ed3f9672baf75acf5efdf866666`, DroneSkeleton arm at `15d139b215cb46b375fe3fae3e5f9d65baa01097`, and the iFixit PSP 300x UMD replacement guide. Archive Git blob identities and individual file SHA-256 hashes are retained in the receipt. Real ERC/DRC findings from the source projects remain findings, rather than being presented as approvals. The vendor-host lane catches its seeded adapter fault against the pinned Adafruit libraries and a modeled bus; it does not test silicon or physical wiring.

The live Gemini smoke test reached the provider but failed with `API_KEY_INVALID`; no successful live vision result is claimed. The two Qwen live tests lack configured keys. These service gaps are distinct from deterministic software regression coverage.

The HS-3G source recheck preserves its engineering blockers. Its modeled full-throttle demand is 77.9 A versus the pack's nominal 45.5 A continuous rating, derived from 650 mAh and 70C. The manufacturer bench table and battery rating support that mismatch. The nominal 70% bench-command limit is not a verified installed-flight-controller setting. The cutter's guidance also still rejects the bottom plate's 2.2 mm motor holes and 1.4 mm minimum web against about 3.2 mm holes and 6 mm web for 3 mm stock. See the [motor table](https://www.ligpower.com/product/f1404-kv3800-fpv-motor.html), [battery specifications](https://chinahobbyline.com/products/cnhl-ministar-series-650mah-14-8v-4s-70c-lipo-battery-with-xt30-plug), and [cutter guidelines](https://sendcutsend.com/materials/carbon-fiber/). No physical measurements, fabrication or flight occurred.

### HS-3G-B candidate delivery

Commits `19bce248` and `11b9efe4` advance the same GPS/analog-FPV drone through the existing workshop operator. The [candidate package](../examples/drone_proving_ground/revision_b/reference/README.md) contains editable STEP/STL/DXF, component placement envelopes, a 1:1 drill sheet and coordinates, BOM, wiring guidance, a partial review-only configuration, and a hash-checked official INAV firmware image with pinned upstream evidence and licence. The original HS-3G package remains the baseline.

The bounded CAD search rejects 135 mm for 2.38 mm prop clearance, then selects 137 mm with 3.34 mm clearance and modeled takeoff mass **234.90 g**. Nominal mass reserve is 15.10 g; a named +5 g battery uncertainty leaves 10.10 g for other unmodeled mass. The revised motor/prop/battery combination gives 25.8 A in the maker bench table, or **31.24 A** with the explicit voltage sensitivity and 20% design factor. These declared-model checks pass without relying on a throttle cap. Cutter blanks omit the sixteen small motor holes; finished geometry and the separate drilling handoff retain that distinction. The drilling process and thinner frame remain physically unqualified.

A fresh registered operator run stages the retained source, generates the package and passes **44 independent artifact checks**, including STEP reimport, DXF/STL inspection, cut-blank screening, model/BOM reconciliation and pinned firmware validation. **All 48 focused native tests pass**, including unchanged baseline regeneration and rejection of tampered BOM, cutter geometry and firmware. The complete native root suite on final code commit `11b9efe41f471a48783e085d32b91ddfb10fca28`, with the three preserved local files, passes in one invocation: **4,247 passed, three skipped, zero failures**, in 1,037.66 seconds. CAD, KiCad, pinned vendor-library, public-source and headless routing regression profiles were enabled. The skips are the three previously identified live-vision provider gaps. This is a new complete green root invocation, superseding the combined-coverage limitation of the preceding extended run.

The [delivery receipt](status/generated/hs3g-revision-b-2026-11-16.json) binds the source revision, operator result, committed package hashes, test reports and preserved local work. All three original local files still match their starting SHA-256 values. The drill sheet was visually checked in a real headless browser. The BOM subtotal is a labelled US$346.91 snapshot/allowance, not a checkout quote; retained cutting costs are explicitly distinguished from refreshed part prices. A commercial GPS BNF can still cost less under the retained build-versus-buy comparison.

Engineering acceptance is limited to the digital scope. The controller is discontinued at the maker, and the dealer stock lead has not been confirmed for delivery. Shop acceptance, separate drilling qualification, actual component measurements, complete configuration/calibration, current/temperature measurements and frame vibration evidence remain open. Purchase readiness, fabrication, power and flight permissions remain false; no hardware was built or flashed. These changes are committed locally and have not been pushed to GitHub.

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
