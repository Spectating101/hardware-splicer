# OpenBlueprint → Hardware Splicer compatibility bridge

Status: **experimental, read-only integration; not an OpenBlueprint engine fork**.

## Source and license

- Upstream: https://github.com/noobianlabs/openblueprint
- Upstream DesignPackage contract: `src/lib/design/schema.ts`
- Upstream license: MIT, Copyright (c) 2026 OpenBlueprint contributors.
- OpenBlueprint is **independent of proprietary Blueprint.io**.
- HS imports OpenBlueprint's public `DesignPackage` JSON structure and adopts
  its useful Info/Parts/Architecture/Wiring/Mechanical/Instructions navigation
  *pattern*. HS does not vendor OpenBlueprint's proprietary dependencies, source
  assets, generator, community designs, Next.js app, or approximated 3D geometry.
- Keep this notice and the upstream MIT attribution with any substantial
  copied code. No OpenBlueprint source files are copied verbatim in this patch.
  `blueprintBridge` is a native HS Vite/React adapter and view.

## Why selective integration

HS already ships `apps/splice-ui`: a React 18/Vite interface with a
project wizard, async builds, React Flow, KiCanvas, source-bound project
packages, bench evidence, and versioned project sessions. OpenBlueprint is a
React 19/Next.js 15 application. Vendoring it wholesale would create another
frontend, duplicate parts and wiring UIs, and separate project authority from
the actual HS engine.

Instead, this bridge adds **three connected paths**:

1. **Prompt-first HS home**: describe a goal directly on the landing page.
   It is carried into the existing HS project session and clarification wizard.
   This is real intake state, not a claim that an AI has already designed or
   validated a device.
2. **OpenBlueprint import**: download an OpenBlueprint project ZIP and extract
   `design.json` (the upstream `buildProjectZip` export writes that filename).
   In the HS Home view choose `Inspect an OpenBlueprint DesignPackage` and
   select that JSON. This is local, requires no HS API, and shows Overview,
   Parts, Architecture, Wiring, Mechanical, Code, Build, Verify. Only
   source-supplied pin-level connections render as wires. The input never
   becomes an HS project, modifies source history, or opens safety gates.
3. **Native HS explorer**: compile or load an existing HS project. The existing
   project workspace shows a unified explorer above the current Intake/Design/
   Verify/Bench/Package workflow. This explorer normalizes the actual
   `PROJECT_PACKAGE` BOM, topology, assembly steps, firmware scaffold and
   reported DRC/bench state. The existing HS engine remains the authority.
   `PROJECT_PACKAGE.wiring.topology_operators` is **not** silently converted
   into fictional pin-to-pin connections.

### Running and testing

```bash
cd apps/splice-ui
npm ci
npm test
npm run build
npm run dev
```

Open http://127.0.0.1:5178 and import an OpenBlueprint `design.json` while
the backend is offline, or run `hs-serve --host 127.0.0.1 --port 8787` and
open a compiled HS project to test the same explorer with real HS output.

### Honest limits

- This is **not** live Blueprint.io or OpenBlueprint API integration, AI
  generation, automatic schematic conversion, or OpenBlueprint-to-KiCad
  manufacturing conversion.
- Imported BOM costs are **source estimates**, not real-time offers.
- OpenBlueprint assembly nodes are **schematic**. This integration displays
  the tree and explicitly does not generate or pretend to verify CAD/STEP/STL.
- HS project packages often contain topology operators and prose rather than
  structured pin-level nets. Wiring view shows those honestly, without
  inventing wires.
- Firmware shown here is a scaffold, not a compiled/tested binary.
- The imported design cannot authorize fabrication, power-on, motion or
  release. Only existing HS evidence and operator-authority systems can
  determine those states. A UI preview is never a substitute.
- The bridge has no direct photo upload, sourcing backend or third-party
  service dependency. These are later functional benchmark questions, not
  silently shipped capabilities.

### Test plan

1. Import an actual OpenBlueprint `design.json` and verify the parts,
   architecture lanes, source pin graph, assembly hierarchy and build phases.
2. Import malformed, oversized and conflicting JSON; verify rejection with no
   project mutation or authority upgrade.
3. Open the existing HS RC donor rover package and verify that DRC is
   explicitly *reported*, missing pin-level wiring is labeled missing, costs
   are unknown where unspecified and power-on remains blocked.
4. Run the full existing Splice UI test suite and production build in CI.
5. Only after this passes: evaluate a genuine 3D viewer using **real**
   dimensional/STEP artifacts and evaluate an external generator adapter,
   rather than copying approximate geometry into a manufacturing workflow.

## Boundary to production

This PR is an integration/UX spike, not a physical build, competitor parity
claim, or authorization bypass. Keep it draft until CI and actual import +
HS build demonstrations have been inspected.
