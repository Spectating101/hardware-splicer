# HS Filter Assembly Interface Audit 001 — source-backed fit / measurement blockers

**Date:** 2026-10-31. Draft, stacked on PR #238. No parts purchased, water or pressure testing performed, mounts drilled, or physical assembly authorized.

## Motivation

PR #238 reproduced the source-bound Pentair P5 `155014-43` media and Traditional Slim Line `158007` housing reference and independently rendered *external* dimensional clearance models. That proves only the reviewed outside dimensions and the explicitly illustrative 150 mm below-sump space.

A **nominally compatible 10-inch format is not proof of actual cartridge sealing or fit**. A housing exterior Ø118 mm cannot be used to infer the interior bore, exact cartridge seat, seal compression or safety of a pressure-containing flow path. The next meaningful artifact is a structured, source-reconciled interface and measurement ledger, not a guessed printable manifold or bracket.

## Additional published evidence and limitations

- Pentair's older [Traditional Slim Line manufacturer specification, 310050 REV F JE18](https://www.pentair.com/content/dam/extranet/web/nam/pentek/spec-sheets/310050-pentek-traditional-slimline-spec-sheet.pdf) documents four molded cap mounting bosses and lists **244047** (Slim Line zinc-plated bracket kit), **150539** (SW-1A wrench) and **151121** (EPDM size #237 O-ring). The bracket's precise compatibility with this **exact 158007** housing and actual boss/thread dimensions have not been independently verified.
- The [more recent Traditional Slim Line manufacturer specification, 310050 JL25](https://www.pentair.com/content/dam/extranet/nam/filtration/pentek/residential/spec-sheets/english/310050-pentek-slim-line-spec-sheet.pdf) says an installer must ensure enough room for wrench movement and sump/cartridge replacement. It does **not** establish that our previous 150 mm illustrated service corridor is sufficient.
- The **older** 2018 spec's NSF/ANSI 42 component material/structural certification list does **not** name **158007**. This does not prove the SKU lacks any current certification, but the selected SKU's certification has **not been established from the reviewed evidence**. Even certification of a component would not establish treatment efficacy or drinking-water safety of an assembled device.
- The component manufacturer's original initial cartridge/housing differential-pressure observations are each specified at **5 US gpm**. Neither the assembly interface study nor this test plan extrapolates them to the function-first **0.5 L/min** target. No inferred pressure budget or pump selection is offered.

## Actual six physical interfaces

| Physical interface | Link | Unverified requirement |
|---|---|---|
| Cartridge end and sump | 155014-43 → 158007 | Interior size, seat alignment, media bypass sealing |
| Cap bosses and bracket | 158007 → 244047 | Hole pitch, thread and weight/load rating |
| Inlet/outlet NPT fittings | 158007 → unspecified adapters | Exact material, 3/8-inch matching threads, pressure rating, sealing |
| Service wrench and sump | 158007 → 150539 | Exact engagement and service sweep envelope |
| Cap-sump O-ring | 158007 → 151121 | Actual groove fit, replacement seal approval, leak behavior |
| Pressure observation | 158007 → unspecified instruments | Tap design, instrument range/calibration and actual flow-dependent pressure difference |

There is **no vendor-approved drill pattern** and no pressure-containing CAD output. All accessories are `CANDIDATE_ONLY`, not SKU-fit confirmed. The mechanical system's **458 mm** combined illustrated vertical allocation (308 mm housing + 150 mm assumed below space) is just bounding-space arithmetic, not an adequate installation dimension.

## Machine-readable engineering evidence

`examples/functionality/water_filter_assembly_interfaces_001.json` identifies current manufacturer source URLs, part numbers, accessory candidates, six interfaces, seven independent evidence requests, unmeasured pressure/flow fields, certification uncertainty and false physical-authority bits.

`filter_assembly_gate.py` independently checks the exact **PR #238** component receipt, source file hashes and actual upstream native STL hashes/bounds. Then it checks that this interface catalog names the right part variants, doesn't infer service clearance or interior dimensions, and refuses invented supplier, pressure, water-quality, certification or fit claims.

The new fourth GitHub workflow job downloads the **same-run native CAD/component evidence** from `manufacturer-component-clearance`. It never substitutes a hypothetical spreadsheet for actual OpenSCAD verification. New tests intentionally use synthetic STL fixture bytes *only* to test tamper rejection; they do not claim to be a second native CAD execution.

### Reproduction

```bash
pytest -q tests/test_filter_assembly_gate.py

python scripts/audit_filter_assembly_interfaces_001.py \
  --component-package .cache/hs-filter-component-study \
  --assembly-interfaces examples/functionality/water_filter_assembly_interfaces_001.json \
  --out .cache/hs-filter-assembly-interface-gate
```

Outputs: `ASSEMBLY_SOURCE.json`, `ASSEMBLY_GATE.json`, `EVIDENCE_REQUESTS.json`, `UPSTREAM_COMPONENT_RECEIPT.json`, `UPSTREAM_NATIVE_CAD_EVIDENCE.json` and `ASSEMBLY_RECEIPT.json`.

## Exit criteria and next engineering move

Before designing or using hardware, independently obtain or inspect an exact-SKU Pentair approved bracket drawing and housing/seat fit information, a real service access dimension, compatible rated NPT fittings and seals, an actual non-potable feed head and pressure/flow test plan, and evidence of safe operating limits. A controlled paired-particle challenge remains mandatory before claiming specified turbidity reduction.

**Current verdict:** `ASSEMBLY_DESIGN_BLOCKED_PENDING_EVIDENCE`. The manufacturer-documented interfaces make the *next measurements precise*; they do not establish a functioning, purchasable, build-ready or drinkable water filter. Neither source PDF is archived as verified immutable bytes.
