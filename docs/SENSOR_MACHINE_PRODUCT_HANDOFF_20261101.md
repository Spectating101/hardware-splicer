# Second product family: ESP32–BME280 -> canonical MachineProject

**Dependency:** independent electrical/firmware/mechanical acceptance from PR #233 (stacked on #232/#229). Not derived from ClearBench and not dependent on the water-filter product branch.

## What this PR executes

The existing source-bound electronic sensor generator already produces:
- a **catalog-based** ESP32 DevKitC V4 / BME280 four-wire electrical proposal;
- real PlatformIO ESP32 firmware ELF and BIN;
- source-matched OpenSCAD base/lid geometry and independent trimesh checks;
- retained mechanical bolt-ear geometry proposals, unqualified BOM, SHA256 receipts;
- same-run independent evidence reconciliation.

This PR **revalidates those native files** using the existing acceptance verifier and exports a canonical `MachineProject` containing requirements, functions, subsystems, components, I2C and mechanical interfaces, native evidence references, and planned physical verification. A source-hashed `PRODUCT_HANDOFF.json`, `MACHINE_PROJECT.json`, acceptance report, Atlas capability and `HANDOFF_RECEIPT.json` are published in one downstream independent CI job.

Digital proof is represented as *nonphysical evidence*. Three tests are marked passed only for symbolic software pin consistency, native firmware compilation, and rendered CAD meshes. Two required physical verifications remain planned: actual assembly/wiring/fit and actual environmental sensor performance. Unresolved physical interfaces and a safety requirement block operational release.

## Why a second product matters

This provides a separate **electronic environmental monitoring** product, using the same canonical MachineProject schema as the later function-first filtration work. It tests portability of the **engineering evidence and product handoff layer**, not universal automatic function-to-manufacture synthesis.

No filter-specific dimensions, water flow, pressure ratings or treatment logic are reused. No new custom KiCad PCB has been made for the sensor and native KiCad verification of the separate SPI adapter design is not transferred to it.

## Reproduce using artifacts from the same native CI run

```sh
python scripts/export_sensor_machine_handoff_001.py \
  --geometry .cache/acceptance-input/geometry \
  --firmware .cache/acceptance-input/firmware \
  --out .cache/hs-sensor-machine-product-001
```

The source input generator is in PR #229/#233; the downstream exporter refuses stale, missing, mutated, cross-revision or physically-promoted inputs. Unit tests are synthetic and test *mapping integrity only*. The native CI job must run before we call this accepted.

## Remaining HS-wide milestones

1. Reconcile and compare the **two genuinely different** canonical MachineProject products with domain-specific acceptance gates.
2. Promote real physical mounting, instrumented test and supplier information *only when independently observed*, not through synthetic CI.
3. Try an electromechanical moving product (rover or drone) against the same machine interface and evidence contract; do not flatten dynamics/safety into water or sensor assumptions.
4. Benchmark against independent design systems and actual domain engineers before asserting quality, cost or automation superiority.

No hardware ordered, assembled, printed, powered, flashed or tested by this change.
