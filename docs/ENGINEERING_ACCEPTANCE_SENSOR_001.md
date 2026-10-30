# HS ESP32 Sensor 001 — consolidated engineering acceptance (2026-10-31)

## Purpose

Use **PR #229** as a software-only engineering baseline. This change adds *no new electrical circuits, CAD shapes, firmware behavior, hardware activation, Atlas runtime, or manufacturing logic*. It binds the **native OpenSCAD/trimesh** and **native PlatformIO** job results into one testable source-bound acceptance record.

## Background

PR #229 head `3e7aa66fb1d95e8d88f7a012d163cb5ba6fe1c3b` had all four GitHub workflows green as confirmed in the October 31 audit. This alone does not mean the independent jobs used identical source artifacts or that a release-ready device exists.

## New acceptance jobs

`Cross-Domain Physical Geometry + ESP32 Compile` now has three sequentially related jobs: existing native CAD/geometry checks, existing embedded target compilation, then **reconcile-and-publish-capability**.

The aggregator downloads actual same-run artifacts from the first two jobs, rather than trusting their green checkmark. The acceptance CLI `scripts/verify_cross_domain_acceptance_001.py` then checks:

- Exact equality of the independent jobs' `CROSS_DOMAIN_RECEIPT.json` records and source design digest.
- Every upstream generated artifact digest and actual original `DEVICE_SPEC.json`, `DEVICE_PLAN.json`, `FIRMWARE_SOURCE.zip`, and CAD model inputs.
- Actual rendered base/lid STL bytes, source-bound USB and ventilation mesh checks, and their recorded SHA-256 and declared watertightness results.
- Independent retained lid/base STL bytes, source CAD SHA-256, mechanical geometry evidence, and an explicit **board mounting blocked** flag.
- Actual `firmware.elf`, `firmware.bin`, PlatformIO compile log SHA-256, fixed target command, pinned tool version and the exact firmware source ZIP digest.
- All physical use and manufacturing claims remain **false**. Evidence of cross-compilation is not evidence of sensor wiring, temperature/humidity measurements, mechanical fit or performance.

A stale candidate from one job, modified mesh, forged vendor identity, missing binary, altered build log, false qualification claim, or incorrect source hash must cause failure.

### Reproduce from native tool outputs

```bash
pytest -q tests/test_engineering_acceptance_sensor.py

python scripts/verify_cross_domain_acceptance_001.py \
  --geometry .cache/acceptance-input/geometry \
  --firmware .cache/acceptance-input/firmware \
  --out .cache/hs-engineering-acceptance-001
```

The two input folders must contain the native tool artifacts downloaded from **the same GitHub Actions run**; independent synthetic fixture unit tests exercise validator behavior only, not engineering capability.

## Output

- `ENGINEERING_ACCEPTANCE.json`: verified source digest, all inspected artifact hashes, known blockers, per-domain evidence level, pinned actual toolchain names, strict software-only readiness.
- `ATLAS_CAPABILITY.json`: portable `hardware_splicer.external_capability.v1` contract containing identity, verified domains, evidence digest, reproduction entrypoints, dependencies and restrictions. No Atlas runtime/database needed.

## Engineering and commercial comparison

This PR proves no new business advantage and makes no claims of outperformance. The next stage is an **equal-input comparison** across HS, a skilled engineer using KiCad/PlatformIO/OpenSCAD manually, and a general-purpose coding agent with those exact tools. Independent comparison results, time, effort, correction count and inference/tool spend are **pending**, not estimated as measured.

## Review decision

**CONSOLIDATE.** The narrow PR is stacked on #229 to avoid duplicating or incorrectly merging #230, #224 and other open capabilities. It should remain draft until all three native/acceptance jobs pass on its latest commit. Even after passing, the intended release tier is `software_candidate_only`; no print, power-on, firmware flash, manufacture or physical performance claim is authorized.
