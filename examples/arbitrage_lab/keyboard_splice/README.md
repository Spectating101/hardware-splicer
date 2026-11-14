# Keyboard PCB recycling: virtual cut and reconnection feasibility (2026-11-15)

**Customer objective:** turn a legally acquired, end-of-life rigid-PCB mechanical keyboard into a useful split keyboard while retaining the original controller, functional switches and as much copper as possible. This is a **merchant's refurbishment experiment**, not a request to design an entirely new keyboard.

**Outcome:** HS successfully imported a real open-source keyboard PCB and created a source-bound candidate **pin/pad harness map**, but did **NOT** establish a physically safe straight cut or an electrically sufficient set of reconnection jumpers. This is a reference-only test; nothing physical was acquired, cut, soldered, sold or powered.

## Real inputs and reproducibility

- Source: [komar007/gh60 / keyboard.kicad_pcb](https://github.com/komar007/gh60/blob/master/keyboard.kicad_pcb) (legacy KiCad v4-format reference, not a specific salvaged board).
- SHA-256 of **exact downloaded original**: a99aafb9f1ca77c5cac67037d161fa849b9b200de5dec9f63964520af3ff3daf.
- KiCad/pcbnew version: 9.0.2 (legacy board converted on a best-effort basis).
- HS code: keyboard_splice.py, keyboard_splice_extract.py, CLI hs_keyboard_splice_probe.py; the original PCB is **not vendored or modified** in this project.
- Run in an environment where /usr/bin/python3 can import pcbnew:

        PYTHONPATH=src python scripts/hs_keyboard_splice_probe.py \
          --pcb /path/to/keyboard.kicad_pcb \
          --out /tmp/hs_keyboard_splice.json \
          --harness-csv /tmp/hs_keyboard_splice_candidate_pads.csv

## Observed scan (not a plan to physically cut at these coordinates)

| Evidence item | Result |
|---|---:|
| Native KiCad copper track segments | 3,305 |
| Pads | 912 |
| Vias | 179 |
| Switch footprint candidates (includes layout alternates) | 84 |
| Copper zone objects | 7 |
| Approximate straight cut positions (30–70% of board width, 1 mm increments) | 115 |
| Positions passing modeled pad/via/switch clearances | **0** |
| Midpoint: trace segments / distinct affected nets | 42 / 33 |
| Best-scoring blocked straight line: x coordinate | 224.77 mm |
| Best-scoring line: affected nets / matrix nets | **31 / 11** |
| Best line: optional lighting / power / other unknown nets | 12 / 2 / 6 |
| Best line: switch centers / pads at risk | 3 / 9 |
| Best line: matrix-net candidate pad pairs found | **11 / 11** |

The file evidence/gh60_virtual_cut_20261115.json contains every crossed-net classification and pad reference; evidence/gh60_candidate_harness_20261115.csv contains 31 potential solder-pad **references**, not a wiring/fabrication authorization. Example: /Matrix/col10 has proposed IC1/29 on the left and D46/1 on the right. Actual component marking and post-cut pad continuity remain unverified.

**Do not interpret 11 as an exact conductor count.** It is the number of *distinct source-net names* classified as matrix connections at one blocked cut. Several of those nets cross the saw corridor more than once, and the connectivity of copper islands after removal is not computed. Returning one theoretical pad per side is not a proof that one jumper reconnects all required islands.

## What HS already had, what was missing

| Capability needed | HS status |
|---|---|
| Exact source identity and revision evidence | Existing provenance + SHA conventions, reused |
| Read real KiCad board, pads, copper segments and net names | Existing KiCad integration, used through native pcbnew |
| Detect where a cut will sever the original copper | **New experimental bounded scan** |
| Identify candidate original pads on each side for a bridge | **New reference-only pad map** |
| Enforce a physical/merchant release boundary | Existing HS doctrine; probe always returns BLOCKED_REFERENCE_ONLY |
| Choose a manufacturable stepped/sacrificial cut | **Missing** (straight-seam screen found no clear line) |
| Reconstruct connected copper islands after kerf and calculate exact rejoin topology | **Missing** |
| Design and route a strain-relieved, tested bridge cable / interposer | Existing KiCad/CAD pieces available, **not integrated** into this workflow |
| Identify a real donated keyboard board revision from two-sided photos | **Missing actual physical donor**; no safe model-specific registration |
| Validate an intact original firmware scan, every key, USB/ESD and enclosure | **Needs real bench measurements** |
| Handle flexible membrane keyboards | **Different process**; this PCB analyzer does not apply to silver-ink membrane traces |

## Concrete next prototype

For a salvaged **rigid-PCB** mechanical keyboard:

1. Record legal ownership, exact model, keyboard layout, switch condition, both PCB sides and controller area; preserve original USB connectivity and its mechanical support.
2. Register both PCB sides to real mm dimensions. Identify which optional switch footprints are **actually populated**, and which RGB/LED circuits can be intentionally retired.
3. Solve a stepped or sacrificial cut path based on true switch/keycap/plate/body keepouts; if it cannot avoid essential devices, reject that donor.
4. Model copper-island connectivity on both sides of a modeled kerf, including filled copper zones, vias and pad drills. Every required remaining keyboard switch and the original controller must remain in valid nets.
5. Generate a **physical** flex harness or small mating interposer with exact compatible connectors, solder-pad access and strain relief; check it with KiCad and an independent electrical review.
6. Physically test unpowered shorts/continuity **on the actual donor first**, then controlled USB power and full-matrix keypress tests; build a case only when functionality is proven.
7. Record all new parts, disassembly time, conversion hours, yield and saleable QA grade before claiming profitable resale.

**Decision:** no fundamental architectural prohibition in HS. The gap is a specialized, evidence-bound *subtractive manufacturing + net restoration* operator, a real matched donor, and independent electrical/physical acceptance. The first pilot proves a meaningful subset and honestly fails the rest.

## 2026-11-15 extension: native post-cut copper-island reconstruction and HS release integration

This phase upgrades the original crossing-net worksheet to a **bounded subtractive electrical topology model**. It is a prototype using actual KiCad copper geometry, not a replacement for board reverse engineering or continuity tests.

### What was integrated

- **KiCad pcbnew extraction:** Width-aware copper tracks, pad size/type/rotation, vias and 2-layer attributes are imported from the same revision-bound reference board. No source PCB is modified.
- **Shapely island engine:** Polygonal material removal is applied to pads, vias and traces for a given straight kerf. The graph distinguishes preexisting disconnected copper from newly separated islands and joins plated-through-hole connectivity between layers when not severed.
- **Bridge graph candidates:** The original copper groups that split are represented as model islands; the engine proposes edges only when both sides expose intact candidate pads from the **same original connected component**.
- **Closed-loop graph replay:** The proposed bridge edges are virtually applied back to the modeled geometry. Any remaining disconnected groups remain blockers; nothing is silently marked repaired.
- **MachineProject release integration:** The original reference, virtual model digest, unresolved two-half electrical interface and blocked physical verification are recorded in HS's canonical project structure. A real BUILD_READY release is denied.

For clean setups, install the optional keyboard-splice dependency with pip install -e '.[dev,keyboard-splice]' in the normal HS environment, and pass --topology-python /path/to/hs-venv/bin/python. Native KiCad pcbnew may remain in /usr/bin/python3. If no topology interpreter with Shapely is available, this step fails explicitly; it never generates fake successful topology evidence. The outer operator requires its normal HS environment for Pydantic and project release assessment.

Run a complete evaluation (no hardware modification):

    PYTHONPATH=src python scripts/hs_keyboard_splice_probe.py \
      --pcb /path/to/known-reference.kicad_pcb \
      --out /tmp/hs_cut.json \
      --topology-python /path/to/hs-venv/bin/python \
      --harness-csv /tmp/hs_original_crossing_candidates.csv \
      --postcut-islands-json /tmp/hs_postcut_islands.json \
      --postcut-edges-csv /tmp/hs_model_bridge_edges.csv \
      --machine-project-json /tmp/hs_machine_handoff.json

### Actual GH60 integrated run

| Electrical-model metric | Observation |
|---|---:|
| Original track/pad/via-only connected components (for 31 affected net labels) | 105 |
| Post-cut components after modeled 1 mm straight kerf | 146 |
| Original copper groups split by the virtual kerf | 31 |
| Candidate bridge edges where intact solder pads exist | 22 |
| Split groups remaining disconnected when those edges are replayed | **11** |
| Matrix signal source names crossing the kerf | 11 |
| Matrix groups without fully anchored bridge candidates | **6** |
| Source warning / copper pours | Legacy-format translation / 7 zone objects |
| Source model physical authorization | **DENIED** |
| Canonical HS requested vs achieved release | BUILD_READY requested; DESIGN_READY modeled; **not allowed** |

These numbers do **not** imply 105 independent physical circuits or a 22-wire real repair. Missing copper-pour conductivity and approximate pad polygons can alter apparent connectivity, and the reference board includes several alternative switch layouts. Among the 11 matrix signals crossing the selected virtual cut, five row groups have bridgeable pads in the track-only model; other matrix groups are unanchored or fragmented into additional islands. Nothing should be cut from this report.

Proof files:
- evidence/gh60_integrated_cut_20261115.json: source-bound overview and canonical blocked release.
- evidence/gh60_postcut_islands_20261115.json: source-bound model islands, candidate pads and graph replay.
- evidence/gh60_postcut_bridge_candidates_20261115.csv: candidate model island edges, NOT a soldering harness.
- evidence/gh60_canonical_machine_handoff_20261115.json: HS MachineProject with declared electrical interface, blocked bench test and simulated evidence.

### Remaining indispensable engineering gaps

1. **Zone-aware connectivity:** Native filled copper shapes, return paths, thermal spokes and any custom-pad primitives need an independent per-layer reconstruction before cut wires can be counted.
2. **Actual populated donor:** The GH60 reference file includes alternative switch footprints and is not a verified used physical board. Exact model, mounting and revision must be established.
3. **Stepped cut / sacrificial-key optimizer:** A clear cut may require sacrificing a few keys or stepping around occupied zones. Straight paths were blocked on GH60; the island tool currently models vertical kerfs only.
4. **Manufacturable bridge:** Real ribbon connector footprints, copper preparation points, strain relief, insulation and an actual KiCad interposer/flex board must be generated and tested.
5. **Electrical + functional acceptance:** Every retained switch, original MCU, USB/ESD/power return and safe isolation need real bench evidence, plus long-term key/hinge durability and recycling costs.
6. **Membrane keyboards:** Silver-ink membrane circuits are not rigid-PCB copper. They require a distinct conductor/connector and mechanical-process model.

**Commerce outcome:** no donor acquisition, no recovered products and no validated resale economics. This is an engineering-enablement milestone for a future merchant conversion workflow, not proof that conversions are economically viable.


## Stage III: copper pours, stepped cuts, native KiCad bridge PCB (2026-11-15)

This section **supersedes the limitations in Stages I–II** above. Their frozen results remain unchanged as a baseline. The native system now models the source's filled copper zones, optimizes a bounded non-straight saw path, virtually cuts the copper geometry, computes disconnected islands, generates proposed bridge channels, and builds a real editable KiCad 9 board with standard-library 2.54-mm pin-header footprints.

**No physical keyboard, cable, PCB, part order, soldering, or real test has occurred.**

### One-command engineering replay

Run within Hardware Splicer using a PCB reference previously confirmed compatible with native KiCad 9. An optional Shapely/NumPy Python and a separate KiCad Python may be used:

    python -m pip install -e '.[dev,keyboard-splice]'

    PYTHONPATH=src python scripts/hs_keyboard_splice_probe.py \
      --pcb /path/to/reference.kicad_pcb \
      --system-python /usr/bin/python3 \
      --topology-python /path/to/hs-venv/bin/python \
      --out /tmp/reuse/CUT_OVERVIEW.json \
      --postcut-islands-json /tmp/reuse/POSTCUT_ISLANDS.json \
      --postcut-edges-csv /tmp/reuse/BRIDGE_CANDIDATES.csv \
      --machine-project-json /tmp/reuse/MACHINE_PROJECT_HANDOFF.json \
      --optimize-stepped \
      --stepped-path-json /tmp/reuse/STEPPED_CUT.json \
      --interposer-out /tmp/reuse/interposer

This produces hash-linked reports and a native `reference_bridge_interposer.kicad_pcb`, with native KiCad DRC verification. It **does not** produce a fabrication-authorized package, a physically valid cable pinout, an ordered PCB, or proof of electrical function.

### Reproduced GH60 comparison

| Metric | Original straight/track-only model | New zone-aware optimized path |
|---|---:|---:|
| Proposed cut form | 1 mm straight kerf | 1 mm stepped polyline |
| Original model islands | 105 | 77 |
| Model islands after material removal | 146 | 110 |
| Original groups split | 31 | 25 |
| Candidate solderable bridge channels | 22 | 19 |
| Groups still disconnected after virtual bridge replay | 11 | **8** |
| Path risk | Not clear of switches/pads | 1 pad, 2 switch keepouts; 0 vias, 0 critical controller keepouts |
| Native interposer | Not generated | KiCad 9 PCB; DRC: 0 errors, 0 warnings, 0 unconnected |
| Physical/fabrication release | DENIED | **DENIED** |

These are **different models and cuts**, so the count reductions combine better copper representation and a changed cut route; they are not evidence of measured labor savings. The stepped path affects 25 named reference nets and is 116.4 mm long. The 19-channel PCB is a real, DRC-clean, research-only pass-through *interposer preview*. The second-stage track-only result had omitted copper pours, while the new importer includes two filled GND copper zones and correctly treats five rule areas as nonconducting.

KiCad 9's import of the old GH60 copper fill contains self-intersecting zone boundaries. Shapely repairs their polygonal geometry for analysis, but zero-width contact topology is uncertain, and **ZONE_BOUNDARY_RECONSTRUCTED_WITH_GEOMETRY_REPAIR** remains an explicit blocker. Oval-pad geometry is also approximate. The source includes unverified alternative key footprints, and no physical model registration exists.

The interposer J1/J2 use actual KiCad standard-library `Connector_PinHeader_2.54mm` footprints. This is **not an established mating connector choice for a split keyboard**. The 2.54-mm pitch is a routing demonstration, not a validated physical interface; no cable, locking mechanism, strain relief, connector MPN, enclosure, IPC manufacturing review, bench test, or supplier quote is provided. Repeated source nets are deliberately routed on independent channel nets rather than shorted indiscriminately.

### Frozen proof and tests

- `evidence/gh60_round2/CUT_OVERVIEW.json`: result plus blocked canonical release.
- `evidence/gh60_round2/STEPPED_CUT.json`: immutable proposed route and collision inventory.
- `evidence/gh60_round2/POSTCUT_ISLANDS.json`: zone-aware island graph, source hash, candidate pads and bridge replay.
- `evidence/gh60_round2/BRIDGE_CANDIDATES.csv`: modeled bridge edges, not a soldering instruction.
- `evidence/gh60_round2/MACHINE_PROJECT_HANDOFF.json`: canonical HS blocked physical requirements and verification.
- `evidence/gh60_round2/interposer/reference_bridge_interposer.kicad_pcb`: actual editable PCB preview.
- `evidence/gh60_round2/interposer/INTERPOSER_CHANNEL_MAP.json`: source-island to independent prototype-channel mapping.
- `evidence/gh60_round2/interposer/INTERPOSER_NATIVE_DRC.json` and `INTERPOSER_VERIFICATION.json`: original KiCad results and source-bound compact receipt.
- New tests cover filled/unfilled copper zones, incomplete pads, invalid zone repair, stepped path collision/receipt tampering, unique-channel KiCad DRC and no physical-authority promotion. Two distinct CI jobs test pure topology and the native KiCad board.

**Commercial verdict:** this is now a working *electrical feasibility and parametric interposer generator*, not a physically validated keyboard recycler. The next highest-value software work is (i) exact physical switch-population verification and custom-pad/zone reliability, (ii) optional-key sacrifice/path scoring tied to final recovered function, and (iii) true flexible/locking ribbon-harness and enclosure/strain-relief design, followed by physical acceptance only when a real donor is available.
