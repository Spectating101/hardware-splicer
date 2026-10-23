# External capability convergence — 2026-10-23

**Status:** Experimental implementation on `agent/oss-capability-convergence-20261023`, stacked on draft PR #193. Not deployed, not released and not physical build authorization.

## Why

Hardware Splicer should **use excellent external engineering tools**, rather than force itself to reproduce every circuit-design, CAD, firmware, routing and manufacturing capability. Schemr, Cirkit and commercial generators are examples only; do not depend on unverified proprietary APIs or partnerships.

This patch adds an operator-controlled bridge to HS's **existing** electrical interchange and project-review spine, not another platform.

## What was connected

| Provider/source | Integration route | Status |
|---|---|---|
| **tscircuit** MIT `@tscircuit/core` | Current generator -> genuine Circuit JSON -> existing HS `/v1/interchange/circuit-json/inspect` and `/electrical-design` -> review | **Live interoperable** in isolated test; optional example, not installed by default |
| **KiCad, SKiDL, atopile** exported netlists | Existing `/v1/netlist-compile`; new file chooser for trusted `.net` drafts | **File-assisted reuse**; actual atopile end-to-end still not retested in this PR |
| **External CSV BOM** | Local RFC 4180-compatible parser -> quantity checks -> exact-label comparison with active project `PROJECT_PACKAGE.bom.lines` | **New**; does not accept aliases, does not change BOM or evidence |
| **build123d** Apache-2.0 | Optional source script generates STEP+binary STL -> new STL inspection (mesh and bounds) | **Live example verified**; no new default mechanical worker; CAD files not persisted or fit-checked |
| **CadQuery** | Existing isolated execution worker | Retained, no duplication |
| **STEP / STL / .ino** from other tools | Source file chooser, local reference; binary STL gets structural mesh inspection | **Reference only**; STEP and firmware neither parsed nor compiled here |
| **Schemr** commercial | Public UI explored; new generation requires account | **Not connected**: no user-owned export or public generation API verified |

### Actual live test results

**tscircuit → HS:**
- Installed pinned `@tscircuit/core@0.0.2199`, `react@19.3.1`.
- Generated a live 4-component, 6-trace RC design using upstream API; **96 Circuit JSON records**.
- Existing HS FastAPI TestClient `POST /v1/interchange/circuit-json/inspect`: HTTP **200**, `review_required`, `compilable: true`.
- Canonical HS `electrical-design` projection: **4 components, 4 nets, 1 ERC issue, 0 unresolved identities, authority `proposed`**. Warnings retained; no fabrication clearance.

**build123d → STL → HS structural inspection:**
- Executed `build123d@0.13.0` in an isolated Python environment and generated a 45×35×3 mounting plate with 6-mm through-hole.
- Real outputs: **26,084-byte STL and 19,166-byte STEP**, source manifest with SHA-256.
- HS browser import helper read actual exported STL: **520 triangles**, bounds **45×35×3 file-coordinate units**, `manufacturable:false`, `physicallyVerified:false`.
- Important: STL carries **no unit metadata**. Source script claims mm, but imported STL does not establish mm, geometric fit, tolerance or actual physical condition.

**Software checks:**
- UI Vitest: **92/92** passing, including source-file UI actions, BOM 2-motor vs 1-motor mismatch, malformed source handling and invalid mesh.
- Frontend production build: passed during implementation (rerun at final commit).
- Python `tests/test_electrical_interchange.py`: **5/5** passing.
- Live external-generator/HS proof: successful.

## Operator workflow

In HS UI:
1. Start a project and open **Design** or open **Interface Lab**.
2. In `External tools → HS engineering review`, choose an actual export (max 4 MB).
3. For `.json`, click **Inspect in HS (no build)**. See retained components, nets, ERC and upstream structural warnings.
4. For `.csv`, inspect line/quantity totals and conflicts against the active HS compiled BOM; if no HS BOM exists, the app says the comparison is unavailable.
5. For `.stl`, see binary triangle count and numeric bounds. For STEP and Arduino code, only source provenance and file recognition; no editing or compilation here.
6. If appropriate, explicitly click **Compile draft**; it goes through existing KiCad compile routes and remains subject to existing gates. Never treat compilation as physical authorization.

To reproduce the tscircuit probe:
```bash
python -m pip install -e '.[dev]'
cd examples/integrations/tscircuit
npm install
npm run generate
python verify_hs.py
```

To reproduce the independent build123d → HS mesh proof:
```bash
python -m pip install build123d==0.13.0
python examples/integrations/build123d/generate.py /tmp/hs-cad
cd apps/splice-ui
node --input-type=module -e 'import {readFileSync} from "node:fs"; import {inspectBinaryStlArtifact} from "./src/components/externalArtifactIntake.js"; const b=readFileSync("/tmp/hs-cad/mounting_plate.stl"); console.log(inspectBinaryStlArtifact(b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength)))'
```
On Linux, build123d/OCP may require system OpenGL libraries such as `libgl1`. The native CAD dependency is optional and not a requirement for normal HS.

## Engineering caveats / scope limits

- These are **read-only reviews, opt-in draft compile and local file references**. There is no automatic cross-discipline import that persists the source into `MachineProject`; no source-to-machine authority escalation.
- Exact-label BOM comparison is intentionally conservative: differently named equivalents will be marked unmatched, rather than treated as safe substitutions.
- 4 MB file limit and binary STL only; ASCII STL and huge STEP files are outside this slice.
- Uploaded file digest uses Web Crypto where available. A hash and a verified upstream publisher are separate concepts.
- Source-file processing never executes uploaded JavaScript/Python or external APIs.
- Real dimensions and motion, chemical exposure, thermal compatibility and power rails still require engineering review and physical evidence.
- **Issue #194** (rover source BOM and power topology) remains an independent blocker.
- The `tscircuit` example may emit warnings because no real power source is present; `review_required` is the correct outcome.
- No Schemr integration, partner API, billing dependency, live device testing, or deployment was added.

## Next integration choices

Advance only what improves an actual end-to-end project:
1. Promote external source data into canonical project proposals with durable source IDs, explicitly separate from verified facts.
2. Compare CadQuery versus build123d on constrained hinges, 3D printed connectors, fit and tolerance before selecting a default.
3. Use existing atopile, KiCad, firmware compiler and simulation engines through their supported formats.
4. Fix #194; then benchmark external vs internal design consistency on real donor rover and greenfield sensor cases.

**Decision rule:** Add an external tool only when it reduces engineering effort, expands supported design space, or measurably improves correctness. Do not substitute count of integrations for genuine capability.
