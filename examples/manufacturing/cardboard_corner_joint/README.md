# HS Manufacturing Challenge 01 — 90° cardboard connector

**Purpose:** test whether Hardware Splicer can deliver an actual reproducible fabrication package with independent quantitative digital checks. This is a low-load alignment prototype, **not** a load-rated functional structural joint or physically verified print.

## Printable deliverable

A one-piece printed connector holding two nominal **3.0 mm** cardboard panels perpendicular to one another. CAD has two through-height sockets **3.6 mm** wide (0.30 mm designed clearance per side), **24 mm** tall, **30 mm** insertion depth, and a central **4.2 mm** through-hole intended for a possible M4 fastener (not dimensionally checked against an actual bolt).

Reuse CadQuery/OpenCascade as the geometry engine. Generated files: one actual STL, one STEP, 3 fit coupons at 0.15/0.30/0.45 mm radial clearance, SHA-256 manifest and digital acceptance report. STL unit convention is mm *by source code*, not encoded in the STL file.

Local execution:
\`\`\`bash
python -m pip install cadquery trimesh numpy pytest
python generate.py outputs
pytest -q test_geometry.py
\`\`\`
Run with a compatible Python/CadQuery environment. Generated STLs/STEP are in the separate challenge download; no binaries are checked into the repository PR.

### Digital result (real execution)

- Joint BREP solid volume **11,417.894 mm³**; **46.2 × 46.2 × 24 mm** bounds.
- Exported STL: **560 triangles**, 1 connected watertight oriented solid, mesh volume **11,418.031 mm³** (within 0.002% of CAD volume).
- STEP re-import preserved volume **11,417.894 mm³**.
- Exact CAD collision for inserted 3 mm test sheets: **0.0 mm³ each**.
- Oversized **3.8 mm sheet** causes **141.36 mm³ collision**, demonstrating that the negative-fit control is not silently ignored.
- Three coupon STLs pass watertight mesh checks. 9 geometry parameter combinations plus invalid-parameter controls exercised.
- Illustrative **14.16 g** nominal PLA full-solid mass upper bound from 1.24 g/cm³ density. **Not measured filament, not actual slicer consumption or cost**.

## Actual physical trial still to run

1. Measure actual cardboard thickness in at least five positions; record median and range.
2. Slice and print the **three small coupons first** on the intended printer; record printer model, material, nozzle, layer height, temperature, time, supports, slicer mass and actual mass.
3. Measure three inner-gap locations with calipers; trial insertion of the *actual* sheet; select clearance based on observed sliding fit without crushing and repeated removal.
4. Re-parameterize the main connector, slice and print in flat XY orientation (vertical channels and mounting hole); check actual print time, first-layer issues, warping and support requirements.
5. Insert both panels; measure approximate corner angle using square/protractor. Initial experiment targets: fully seated with no cracking, corner within **90° ± 2°** at no external load, and no objectionable permanent deformation after repeated insertion.
6. Record physical photos, instrument IDs, operator/inspection notes, failures, actual cost and iterations. Do not treat this as structural-strength proof.
7. Run identical material and fit test against the best practical external CAD solution, including assembly labor and edits. The competitive evaluation is **pending**, not passed.

**No 3D printer, physical stock, measurement, machine-specific slicer or durability test was used to produce these files.** This is verified digital geometry, not successful physical manufacture.

Reference on trial-only clearance: Prusa recommends starting moving-part fits around 0.3 mm, but printer-specific geometry, material and calibration matter: https://help.prusa3d.com/article/modeling-with-3d-printing-in-mind_164135
