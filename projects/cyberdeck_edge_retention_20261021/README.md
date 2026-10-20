# Actual cyberdeck PCB retention design — two-model plan, CAD verification and revision

**Executed 21 October 2026 on the authorized Optiplex.** Native HS source,
model and accepted-action replay. This remains a SOFTWARE-ONLY DESIGN PROTOTYPE
and is **not print-ready or approved for physical electrical operation**.

## Original engineering failure and agent comparison

The original project is the real public [sector07-dev/RPI_DEV](https://github.com/sector07-dev/RPI_DEV)
KiCad PCB `RPI_Dev_1.kicad_pcb`, with the original companion `.kicad_pro` and
schematic. Publisher PCB SHA-256:
`ddf94ad6fdaee46a52022b20da8678cebd34cec4f4db817d090cd0e45119f042`.
HS hash-verifies these originals on every native software-side operation.
Publisher original files are not re-committed here.

Two native HS model reviewers inspected the **same original board evidence**:

| Model | Design direction | Important check it identified |
| --- | --- | --- |
| Copilot CLI (baseline) | Exterior, case-based screw retention; no fictitious holes in PCB | Registered, source-derived mounting interfaces rather than the old rectangular-envelope carrier |
| Opus 5.5 High (independent review) | Edge-captured board, separate screw-closed lid; compare with PCB revision and risky Q1 tab-hole sharing | Extract exact nominal Edge.Cuts contour and every drill; check copper near edges, component heights, connector clearances |

Original model plans and source hashes are recorded in
[COPILOT_OPUS_SOURCE_DESIGN_COMPARISON.json](./COPILOT_OPUS_SOURCE_DESIGN_COMPARISON.json).
No model established physical measurements or manufacturing approval. A hybrid
of the two source-supported proposals was selected for *software candidate*
development. New manufacturing dimensions are explicit **design assumptions**,
not claims about actual hardware or fit.

The earlier HS tool generated a **rectangular envelope-only carrier** about
**97.9 × 68.3 × 7.5 mm**. It had no verified PCB retention mechanism or
mounting holes. The new edge-capture candidate deliberately uses more X/Y
margin for screws outside the board: **106.9 × 77.3 × 6.46 mm**. This is a
physical packaging tradeoff, not necessarily a smaller or better product.

## Source-verified changes and real geometry actions

1. **KiCad original Edge.Cuts outline** was read through the actual `pcbnew`
   polygonization backend: **one closed outline, 33 sampled points**, including
   a nonrectangular semicircular notch. The publisher nominal board STEP was
   exported through KiCad and its inverted-Y coordinate frame was checked.
   Its solid has an actual nominal extent **90.9 × 61.3 × 1.51 mm**; the
   KiCad drawing stroke's earlier bbox was **90.95 × 61.35 mm**.
2. Source footprint audit: **26 footprints**, **145 pad instances**, **zero**
   explicit PCB mounting-hole footprints. The only listed NPTH is a **3.6 mm
   Q1 TO-247 transistor package** feature, **not** a verified chassis mount.
3. Initial prototype: a source-contour base and edge-capturing, screw-closed
   lid, with **four proposed screw centres outside the PCB AABB**, not through
   the original board. All **three board-only interference volumes were 0**.
4. The **next independent copper-pad proximity screen caught a real problem**:
   using 1.2 mm proposed capture overlap and a 0.45 mm caution margin,
   **23 source pad bounding boxes out of 145** required exclusion. The
   uncorrected candidate had **42.5469 mm³ summed projected keepout overlap**.
   This is the summed conservative per-pad volume, not a physically measured
   copper collision and may double-count nearby padded regions.
5. We revised both source-derived CAD parts to cut away the retaining-lip
   regions under/over those known pad envelopes while preserving the exterior
   retaining wall. The revised design had **0.0 mm³** remaining overlap with
   the 23 declared source pad keepouts and **0.0 mm³** interference with the
   board-only STEP or between base/lid.
6. The next original-source KiCad conductor pass enumerated **456 tracks and
   vias**, no source copper zones, and **7 trace segments** in or near the
   proposed retaining-lip zone (including wide 5.0 mm copper). The pad-aware
   prototype still had **29.4863 mm³** summed source trace/via keepout overlap.
   A third revision excluded those 7 trace footprints from both source-derived
   lip regions; the resulting projected nominal trace/via keepout overlap was
   **0.0 mm³**. This does not certify plating, solder mask or powered
   insulation.
7. After clarifying that these source-only CAD operations do **not** require
   a manufactured physical measurement or a persisted mechanical-layer load
   case, the **actual Copilot HS AI session** proposed
   `generate_board_edge_retention_candidate`. An operator approved ONLY that
   specific software action through HS `/decision`; HS executed its canonical
   `/execute-preview`, wrote native STEP/STL, source hashes and a persistent
   engineering project artifact. This was not arbitrary model-provided code.
8. We then **independently reimported the generated STEP parts** and compared
   against a second KiCad board-only export. All three nominal solid
   intersections remained **0.0 mm³**. A separate binary STL triangle/edge
   topology scan found **0 nonmanifold edges and 0 degenerate triangles**:
   3,724 triangles for base, 2,824 for lid. These checks are necessary sanity
   checks, not proof of printability, stiffness or material suitability.

## Generated actual CAD and inspectable records

- [Base — editable STEP](./source_edge_capture_base.step)
- [Lid — editable STEP](./source_edge_capture_lid.step)
- [Base — generated STL](./source_edge_capture_base.stl)
- [Lid — generated STL](./source_edge_capture_lid.stl)
- [CAD_REPORT.json](./CAD_REPORT.json): exact source/model hashes, nominal
  geometry dimensions, fastener hole centres, pad and trace exclusions and explicit
  authority/physical test limitations
- [INDEPENDENT_VALIDATION.json](./INDEPENDENT_VALIDATION.json): second geometry
  check, SHA-256 identity, STEP intersection and STL topology counts
- [NATIVE_AI_EXECUTION.json](./NATIVE_AI_EXECUTION.json): actual accepted
  HS Copilot AI source-CAD tool execution and result

The regenerated original board STEP is intentionally not included: it belongs
to the original publisher. STEP exports from independent KiCad executions may
have different raw SHA-256 due to serialization/metadata; the independent
verifier uses the unchanged original KiCad PCB SHA-256 as authoritative source
identity and checks CAD **geometry**, not binary equality between two exports.

## What remains unproven

- **Copper**: source 2D pad bounding boxes and PCB track/via centreline
  widths now undergo a conservative nominal retaining-lip exclusion screen:
  145 pads, 456 traces/vias and zero zone shapes inventoried. This is still
  **not** a complete electrical clearance/insulation test: KiCad solder mask,
  plating, pad stacks, populated connector bodies, PCB fabrication tolerances,
  3D assembly contact and manufacturing variations remain unqualified.
- **Populated 3D assembly**: component heights and envelope clearance, Q1
  heatsink/ground tab, cable mating, USB and connector service openings remain
  unverified. The board-only STEP omits placed component 3D models.
- **Mechanics**: clip force, screw fit/tolerances, thread strength, preload,
  board flex, vibration, impact, retention after thermal cycling and tool access
  are untested. Only nominal solid interference was performed, not valid
  PCB-specific FEM or measured forces.
- **Chemistry/materials**: nothing establishes resin, printer, temperature,
  shrinkage, flame rating, compatibility or insulation. No physical print was
  ordered or fabricated, no occupied laboratory equipment was operated.
- **Full cyberdeck system**: this remains a control/interface PCB, not a
  complete sourced Linux computer, display, charger, keyboard and enclosure.
  Its original **43 ERC and 16 DRC** results remain separate unresolved work.

**Conclusion:** source-derived retainer geometry is now substantially better
specified and obvious original-source pad AND near-edge trace keepout
conflicts have been repaired in CAD.
**Software geometry candidate: PASS. Physical/circuit/system engineering: NOT
VALIDATED.** Correct next step: original footprint-specific 3D models and
full 3D component/courtyard and connector checks, then actual mounting
interfaces and physical mechanical load/retention assessment.

## Reproduction

Tests can run in the configured HS virtual environment. The source-backed
CAD trial requires the original publicly available KiCad project and the
installed CAD/Python + system KiCad executables.

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q \
  tests/test_source_edge_retention.py tests/test_kicad_board_interface_geometry.py
HARDWARE_SPLICER_LLM_PROVIDER=copilot_cli PYTHONPATH=src .venv/bin/python \
  scripts/run_hs_edge_retention_model_plan.py
```

The test harness refuses to overwrite an existing trial project. When the
model omits a source-only CAD action because it conflates optional mechanical
load requests with source-only operations, the corrected prompt and
`scripts/retry_hs_edge_retention_agent.py` permit a new approved iteration.
Independent mesh/solid verification is in
`scripts/verify_hs_edge_retention_geometry.py`.
