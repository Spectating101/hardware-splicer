# P010 · 6×6 camera-scanning carrier

A 90 × 84 mm freestanding holder supports developed 120 film over a customer's diffuse light panel. The camera and macro lens sit on a separate copy stand. The operator lifts the mask, positions one frame by sight, seats the mask and takes an exposure. This design targets a Mamiya 6 MF square exposure on ILFORD HP5 PLUS. The lower and upper apertures provide some visible rebate for cropping.

The first digital trial found a problem with one universal guide. On the narrowest strip, a wide guide allowed 1.30 mm of lateral movement between reloads and left only 0.187 mm of supported edge in the adverse position. The revised carrier uses two interchangeable guide widths. Both pass the 0.85 mm lateral repeatability budget and 0.20 mm edge-bearing target. These are geometric bounds for a flat strip. A physical trial is needed to establish whether the film stays in focus and free of scratches.

## Dimensions and sources

| Input | Value | Basis |
|---|---:|---|
| Bare 120 film width | 60.70–61.70 mm | Manufacturing envelope in ISO 732:2000, Figure 1 / Table 1. Measure a processed strip before selecting rails. [ISO record](https://www.iso.org/standard/29302.html) · [Standard preview](https://standards.iteh.ai/catalog/standards/iso/41a3a055-75c1-41c6-9d1a-08b4fbbec6ca/iso-732-2000) |
| Frame | 56 × 56 mm | Mamiya's stated square negative size. Other camera gates and the optional crop masks have different apertures. [Mamiya 6 MF manufacturer brochure, specifications](https://www.darkroomdave.com/wp-content/uploads/2019/06/mamiya-6-mf-brochure-small.pdf) |
| HP5 PLUS roll-film base | 0.110 mm | ILFORD describes the acetate base. The coated strip thickness must be measured. The model allows a total processed thickness of 0.16 mm. [Manufacturer technical data](https://www.ilfordphoto.com/amfile/file/download/file/1903/product/694/?___from_store=ilford_uk&___store=ilford_brochure) |
| Operating envelope | Frame center within ±0.15 mm of strip center across the strip, manual longitudinal centering within ±0.45 mm, skew up to ±0.08°, rays within ±10° per axis | HS design assumptions. Inspect the actual negatives and optical setup. Film curl, shrinkage, field curvature and light-panel uniformity require measurement. |

## Stock, contours and assembly

Use full-scale SVG paths for vector cutting. Matching binary STLs use millimetres for CAD placement or a printed trial. Verify the material's finished opacity and clean film-contact faces before loading a sample.

| Part | Quantity and stock target | Geometry |
|---|---|---|
| Lower plate | 1 × 1.50 mm opaque black sheet | 61.0 mm square window. [SVG](base.svg) · [STL](base.stl) |
| Support ledges | 2 × 0.80 mm smooth sheet | Flip the second rail end-for-end in plane. The assembled ledges leave a 58.50 mm open gap below the film. [SVG](support.svg) · [STL](support.stl) |
| Narrow guide rails | 2 × 0.30 mm smooth shim stock | For a 60.70–61.20 mm strip. Finished gap 61.45 mm. [SVG](guide-narrow.svg) · [STL](guide-narrow.stl) |
| Wide guide rails | 2 × 0.30 mm smooth shim stock | For a 61.20–61.70 mm strip. Finished gap 61.95 mm. [SVG](guide-wide.svg) · [STL](guide-wide.stl) |
| Removable top mask | 1 × 1.50 mm opaque black sheet | 58.80 mm square window. [SVG](mask.svg) · [STL](mask.stl) |

From the light upward, stack the base, two support ledges, one pair of guides and the mask. Film sits on the smooth inner edges of the support ledges, between the guides. Both short ends are open. The design assumes a strip long enough to span the 90 mm channel during insertion. Support any length extending beyond the carrier.

Use four approximately 3 mm locating posts matching the 3.2 mm holes on a 76 × 76 mm pattern. Use removable retention on top of the mask. Provide four non-marking feet outside the light opening and clearance for bottom fasteners. The buyer supplies a diffuse illuminated area covering the lower window, an overspill mask if needed, and a copy stand that can focus at the carrier height. No proprietary mounting interface is required. Edge holding relies on clean, smooth ledges and measured alignment. Lift the cover for each advance, move the strip by its rebates, and keep guides and ledges free of burrs and debris.

The contours describe finished dimensions. Compensate for the cutter's kerf in CAM and measure each installed pair. The installed guide gap must lie within ±0.05 mm, the support gap and aperture sizes within ±0.10 mm, and each optical layer center within ±0.15 mm of the guide center. The shim height must be 0.25–0.35 mm including any attachment layer. The ray calculation assumes plate thickness up to 1.50 mm and support ledges up to 0.80 mm. Locating-hole clearance by itself does not establish these tolerances. The narrow and wide strips are similar in size. Mark their outer ends for the operator.

## Digital results

The verifier reads the exported SVG outlines, aperture offsets and locator coordinates. It reconstructs each assembled channel and applies adverse film width, cut width, relative layer shift, media centering, skew and ray angle. It also reads back every STL, checks opposite edge pairs, bounding dimensions and signed volume against the planned material section.

| Worst case within design assumptions | Narrow guide | Wide guide |
|---|---:|---:|
| Remaining total lateral room during skewed loading | 0.074 mm | 0.074 mm |
| Maximum lateral reload span at center | 0.800 mm | 0.800 mm |
| Vertical headroom above the assumed thickest flat strip | 0.090 mm | 0.090 mm |
| Smallest optical margin around a full frame, at lower ledges | 0.258 mm | 0.258 mm |
| Minimum width of film supported at an edge | 0.437 mm | 0.687 mm |

The control cases included a loose universal guide, a wide strip inserted in the narrow guide, a 58 mm exposure, 0.35° skew, 0.27 mm thick media and a 20° optical ray. Each violated its intended acceptance limit. The 58 mm frame lost up to 0.743 mm of optical clearance at a ledge. The 0.074 mm residual loading room is especially sensitive to cutting error, dust and curl. [Checks and negative results](verification.json)

From this directory, regenerate the SVGs and STLs, then rerun the checks. STL regeneration uses Python with Shapely 2.1+ and GEOS 3.10+ for constrained triangulation. The verifier and SVG generator use Python's standard library. The five exported meshes are included.

```sh
python3 build.py --stl
python3 verify.py
```

To change stock, edit [design.json](design.json), regenerate, and inspect the output contours before use. The saved verification bounds concern planar geometry. The carrier has no automatic frame-indexing mechanism and supplies no measured focus or film-flatness result.

## First physical decision

Gauge the actual gap and rail straightness at both ends and at the center. Inspect expendable processed strips with transmitted and raking light before and after ten lift–advance–reseat cycles. Record the maximum lateral displacement using image landmarks and check that all four frame edges remain visible. Compare center and corner sharpness on a flat, detailed test negative against the same locations individually refocused on the same stand. Agree the allowed loss with the user before testing. Record any scratches, edge contact, film bow and illumination falloff. Measure time spent polishing, sorting guides, gauging and reworking the carrier.

The catalog budgets NT$164.74 for materials and NT$98.84 for processing, plus 17.5 active minutes per unit. This trial produced digital shapes and identified a second guide pair. A supplier basket and actual finishing time are still needed to validate those allowances. If finishing adds 20 minutes at NT$600/hour and the second pair and inspection add NT$120 in variable cost, the 25-sale profit falls from NT$14,702 to about NT$6,702 at the same selling price. No physical production or new demand evidence was collected.
