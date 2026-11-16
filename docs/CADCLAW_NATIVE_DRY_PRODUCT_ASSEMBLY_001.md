# CADCLAW native STEP assembly integration — ClearBench S1 dry concept

**2026-11-01**, stacks on ecosystem integration PR #241 and whole-product PR #240.

The intent is to reuse [CADCLAW](https://github.com/sunnyday-technologies/CADCLAW) (MIT) as the *actual native constraint-assembly engine*, not reproduce it in HS. Upstream Git revision is pinned to `d6d371b154abfa011f843ede9f6d150119ef42c4` (CADCLAW 0.11.0).

## Actual native outputs

On exactly one verified ClearBench digital product and source hash:

- CadQuery exports **four real STEP solids**: dry catch tray (450×260×14 mm), back panel (450×12×716 mm), the manufacturer housing *outside cylindrical envelope* (Ø118×308 mm), and a concept sample vessel (Ø66×75 mm).
- A genuine CADCLAW `assembly_spec.v0.1` and `connector_metadata.v0.1` describe the dry tray as datum and connect the panel bottom-front frame to the tray back-top frame. The panel is **constraint-placed** rather than simply assigned an arbitrary world transform.
- The housing external-envelope cylinder and sample vessel are **absolute visual placements only**. In particular, they are not mechanically fastened to the stand. No source-verified Pentair STEP or mated pressure system is available.
- Native `cadclaw assemble validate-spec` and `cadclaw assemble build` run in an independent CI job. The resulting STEP assembly is reimported via native CadQuery and checked for solids, complete bounds, true source STEP hashes, expected part inventory and fail-closed release gates.

The 4-part digital assembly's resulting overall approximate bounds are 450×260×730 mm. This is a *subset* of ClearBench S1's 11-role product BOM. It does **not** replace the richer OpenSCAD/blueprint3d whole-device visualization and does **not** prove the physical housing can be mounted or used.

## Why the assembly stays deliberately incomplete

The CADCLAW spec carries six `not_built_yet` entries marked `required_for_release: true`: bracket mounting, pressure-rated connectors, actual service clearance, functional filtration tests, real vendor STEP, and instrumentation. This prevents an engineering digital assembly from looking like a qualified filtration product. The typed connector frames belong only to the geometrically known, dry tray/back-panel solids. The unknown bracket bolt pattern, sealing details, cartridge seat and pressure loads are **never invented**.

## Native test command

```sh
python scripts/compile_cadclaw_dry_assembly_001.py \
  --product-package .cache/clearbench-s1-product-sample \
  --out .cache/hs-cadclaw-dry-product

cadclaw assemble validate-spec .cache/hs-cadclaw-dry-product/assembly.yaml
cadclaw assemble build .cache/hs-cadclaw-dry-product/assembly.yaml

python scripts/verify_cadclaw_dry_assembly_001.py \
  --assembly .cache/hs-cadclaw-dry-product
```

The CI runs CADCLAW from its pinned external Git source and retains the native STEP components, compiled assembly, contract YAML, and SHA-256 evidence. No third-party CADCLAW source code is vendored into HS.

## Next independent verification

MARB is still an *external benchmarking task*, not a score: build a fair independent STEP/connector truth fixture and compare HS's actual CADCLAW assembly to a similarly equipped coding agent and a domain engineer. We cannot derive a legitimate benchmark score simply by comparing a reference assembly to itself.

**Authority:** all physical purchases, fabrication, pressurization and human-consumption use remain unapproved. This is a digital dry assembly with a complete checklist of absent real-world controls.
