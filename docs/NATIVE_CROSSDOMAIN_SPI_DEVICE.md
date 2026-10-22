# Hardware Splicer native PCB + mechanical CAD acceptance v1

This is the first **single, source-linked cross-domain device package** in the
experimental external-engine stack. The device is the existing
`spi_flash_adapter_v1` 3.3V-to-1.8V PCB paired with a proposed protective
*open shell* modeled by SolidCraft and inspected independently by FreeCAD.

It is a development proof, not a ready-to-fabricate case or physically
assembled gadget. Native sources belong to the respective upstream tools.

## Inputs and actual engines

- **Electrical:** canonical routed `hardware/reference_designs/spi_flash_adapter_v1/spi_flash_adapter_v1.kicad_pcb`, with a recorded KiCad 9 verification receipt bound to its exact PCB SHA-256. This CI does **not** rerun KiCad 9; the dedicated earlier reference CI does.
- **Mechanical:** native SolidCraft v0.18.4 `run` on
  `examples/external_engines/cad/spi_adapter_shell.json` to export STEP.
- **Independent verification:** FreeCAD `Part.Shape()` parses the actual
  STEP and measures volume, dimensions and valid solid count; a second FreeCAD
  native script checks six selected sample points for real floor/wall material
  and open cavity void.
- **Cross-domain:** HS derives the real board outline, FIT/DNP footprints,
  estimated part heights, connector positions and mounting-hole centers from
  KiCad and screens those against the **modeled cavity**.

## Test envelope

- Native shell design: 110 × 70 × 25 mm exterior, 3 mm nominal walls,
  2 mm bottom, 104 × 64 × 23 mm open interior.
- Source KiCad board: 90 × 50 × 1.6 mm.
- Expected net solid CAD volume: 39,412 mm³; FreeCAD must confirm the native
  result to within 0.05 mm³ and outer dimensions to within 0.02 mm.
- Positive native test-point samples: floor center and two shell walls.
- Negative native test-point samples: PCB cavity, top opening and outside
  shell. Both real material and real voids must appear in the right places.

These checks are **not** an arbitrary 3D mesh intersection test. The existing
envelope screen uses approximate component courtyards and package heights.
A nominal pass means source-linked dimensions and sample geometry agree, not
that a manufactured board fits or a connector is reachable.

## Run on trusted Linux with SolidCraft and FreeCAD installed

```bash
python scripts/run_external_engine_plan.py \
    examples/external_engines/spi_adapter_crossdomain.json \
    --workspace examples/external_engines \
    --out /tmp/hs-spi-native-shell --execute --timeout 180

export HS_SHELL_STEP=/tmp/hs-spi-native-shell/shell_cad/model.step
export HS_SHELL_TOPOLOGY_REPORT=/tmp/hs-spi-native-shell/SHELL_TOPOLOGY.json
FreeCADCmd scripts/probe_spi_shell_native.py

python scripts/assess_crossdomain_device.py \
    --engines /tmp/hs-spi-native-shell \
    --out /tmp/hs-spi-native-assessment

python scripts/build_crossdomain_device_package.py \
    --assessment /tmp/hs-spi-native-assessment/CROSS_DOMAIN_DEVICE_ASSESSMENT.json \
    --external-engines /tmp/hs-spi-native-shell/ENGINE_ORCHESTRATION_REPORT.json \
    --out /tmp/hs-spi-native-assessment/DEVICE_WORK_PACKAGE.json
```

The CI workflow `.github/workflows/hs-native-crossdomain-device.yml`
performs all of these steps, runs negative regression cases and uploads the
same native proof files. Do not count native verification as passing until
the relevant GitHub Actions run finishes successfully.

## Artifacts

- `ENGINE_ORCHESTRATION_REPORT.json`: SolidCraft/FreeCAD commands, source
  SHA-256 and each actual native artifact's SHA-256.
- `shell_cad/model.step`: native SolidCraft STEP.
- `shell_inspection/step_inspection.json`: measured native solid.
- `SHELL_TOPOLOGY.json`: source-hashed native cavity points.
- `electrical/REFERENCE_ASSEMBLY_PLAN.json`: source-derived KiCad PCB
  locations, footprints, FIT/DNP and connections.
- `electrical/REFERENCE_DEVICE_DOSSIER.json`: proposed cavity fit and
  unresolved geometry and assembly evidence.
- `MECHANICAL_FEATURE_REQUIREMENTS.json`: source PCB mounting-hole and
  connector feature positions, needed for the **next** CAD revision.
- `CROSS_DOMAIN_DEVICE_ASSESSMENT.json`: joined electronic/mechanical
  evidence and the explicit unresolved requirements.
- `DEVICE_WORK_PACKAGE.json`: proposed actions, parts and acceptance gates.

## Out-of-scope — still blocking release

The open shell deliberately **does not yet have** PCB standoffs/bosses,
screw holes, connector apertures, a lid, anti-short mounting insulation,
strain relief, source-certified 3D component bodies, an independently
verified tolerance stack, or physical assembly measurements. No live SPI
transaction or instrumented voltage/current data was collected.

Therefore no result authorizes fabrication, power-on, a repair,
manufacturing handoff or a product release. That status persists even if
every software integration test passes.

Next revision: use the extracted hole/connector map to add real mounting
features and independently validate their CAD topology, orientation and
assembly access against the board's source geometry.
