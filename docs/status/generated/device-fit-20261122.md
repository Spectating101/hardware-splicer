# Measured device fit across five devices (22 November 2026)

Produced by `src/hardware_splicer/scene_fit.py` (version scene-fit.v4) on each project's committed model. It runs in the native CAD interpreter with trimesh, scipy and manifold3d, is served by `GET /v1/scenes/{id}/{revision}/fit`, and is cached by model and sidecar hash. **Everything here measures the CAD model, including envelope stand-ins. Nothing here is physical proof.**

## Method

- **Interference:** the exact intersection volume of closed meshes (a manifold3d boolean). Coincident vertices are merged first, because exporters often store each triangle's corners separately and that reads as an open mesh.
- **Clearance:** the minimum distance from dense surface samples (about 0.35 mm apart). Pairs under 2 mm are then refined with exact point-to-triangle distances, so a seated face measures 0. Every gap is an upper bound: the true gap is at most `gap_mm` and at least `gap_mm - precision_mm`.
- **Pair classes:** `overlap` (above 0.5 mm³), `touching` (under 0.05 mm), `tight` (under 1 mm) and `near` (under 2 mm).
- **Stand-ins:** a pair is marked `stand_in` when either part is an envelope or of unknown shape. A clash there means the shape is not known well enough; it does not mean real parts collide.

## Results

| Device | Size (mm) | Parts | Real clashes | Stand-in overlaps | Tight | Touching | Not computed |
|---|---|---:|---:|---:|---:|---:|---|
| Fielddeck 7-inch (cyberdeck) | 310.0 × 285.7 × 72.0 | 33 | 0 | 0 | 24 | 35 | overlap volume: display |
| Ender-3 pen plotter | 434.0 × 400.0 × 465.0 | 24 | 0 | 13 | 4 | 11 | none |
| HS-3G-B drone | 155.5 × 163.6 × 74.0 | 32 | 0 | 13 | 2 | 23 | none |
| ESP32 servo board (KiCad) | 80.0 × 50.0 × 10.1 | 12 | 0 | 0 | 1 | 13 | none |
| SPI flash adapter v1 (KiCad) | 90.0 × 50.0 × 10.1 | 37 | 0 | 0 | 9 | 36 | none |

## What the numbers say

- **Fielddeck 7-inch.**
  - No clashes between real shapes; the vendor display mesh is open, so its overlap volume is not computed.
  - The display rests on both rear trays: sampling alone read 0.075 mm, and exact refinement gives 0.
  - Most tight pairs are identical 0.30 mm gaps between printed panels, which matches the recorded "faceplate halves 0.30 mm apart".
  - The keyboard envelope sits 0.17–0.22 mm from the front faces, but that keyboard is a stand-in box.
- **Ender-3.** All 13 overlaps are between reference envelopes (for example, two base boxes sharing 64,000 mm³). None is between real shapes.
- **HS-3G-B.**
  - The measured 155.5 × 163.6 × 74.0 mm matches the study's own `model.json` bounds (0.155 × 0.164 × 0.074 m) to within 0.5 mm. A test checks this.
  - All 13 overlaps involve the representative motors, props and electronics, which are envelopes.
- **Boards.**
  - Footprints seated on the board read as touching.
  - Close footprint pairs (U1 ↔ C4 at 0.12 mm on the SPI adapter) involve footprint boxes with assumed heights (`footprint-heights.json`), so they are stand-in results until real component models are attached.

## New scene projects

- **`projects/hs3g-b-drone`:** the study's assembly. Part fidelity comes from the study's own words (`geometry-basis.json`): 6 custom, 24 envelope, 2 unknown.
- **`projects/esp32-servo-board`, `projects/spi-flash-adapter-board`:** built by `scripts/build_board_scene.py` from the KiCad boards with pcbnew 9.0.2. Each board is the Edge.Cuts outline with its holes, extruded to its thickness. Each footprint is a box over its pads with an assumed height, named by its reference designator.
- **Not done:** the Holybro X500 vendor STEP was not used. Its licence review is not done, so neither it nor anything derived from it is committed.

## Verification

- Engine tests on known geometry: an exact 500 mm³ overlap, a 0.5 mm gap within its stated bound, a seated contact, a far part excluded, and an envelope overlap marked as a stand-in.
- API tests: measured once and then cached, a clean subprocess environment, fixed error messages and 404s.
- The committed sidecars are reproducible from their models.
- UI: vitest 278 passed and tsc is clean. impeccable detect found 0 issues on the new devices at 1440×900 and 390×844.

