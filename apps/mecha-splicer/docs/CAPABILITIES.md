# Mecha-Splicer Capabilities (v1)

Mecha-Splicer is a **mechanical “spec → artifacts” pipeline**: you describe a mechanism or enclosure at a high level, and it produces **printable CAD (OpenSCAD)** + **DFM sanity checks** + **BOM/procurement scaffolding**.

## What it can do well (today)
- Generate printable **enclosures** (with cutouts, standoffs, lid screw holes).
- Generate printable **brackets/mount plates**.
- Generate printable **servo mounting plates** (SG90/MG996R-sized).
- Generate printable **robotics primitives**:
  - **GT2 belt linear axis** (motor/idler mounts, carriage, belt clamp, rod holders, endstop mount, assembly preview)
  - **T8 lead-screw linear axis** (motor mount, screw end support, nut carriage mount, rod holders, endstop mount, assembly preview)
  - **Bearing-supported rotary joint** (bearing block + arm plate + preview)
  - **GT2 belt reduction stage** (mounting plate + belt length guidance)
  - **Servo scissor gripper** (base + jaws + link + preview)
  - **Servo pan/tilt** (base + bracket + platform + preview)
- Generate an **assembly placement file** (`ASSEMBLY.scad`) that imports part modules and places them by transforms.

## Module naming (important for assemblies)
Most generated `.scad` outputs define a module with the **same name as the filename stem** (e.g. `motor_mount.scad` → `module motor_mount(){...}`), so `ASSEMBLY.scad` can `use<>` and call them reliably.
- Emit **DFM heuristics** (fit/wall/clearance + simple load/torque/rpm sanity checks).
- Emit **BOM heuristics** (fasteners + common motion parts) and optional **procurement locking** (`BUY_LIST*.csv`).
- Emit **print/export artifacts**: `PARTS.json` + `PRINT_PLAN.md` (heuristic), optional STL renders.
- Run a **Mint pipeline** (RSS → category ranking → generate “digital pack” bundles).
- Provide a small **API** for bundling/minting (FastAPI).

## What it is not (yet)
- Not a full CAD system (no STEP/FreeCAD-native constraint solving).
- Not a simulator/FEA (checks are conservative heuristics, not guarantees).
- Not an “auto-layout” machine designer (won’t automatically produce a finished product with perfect packaging and cable routing).
- Not a replacement for real frame/fixture engineering (it generates key printed parts + checklists, but you still choose frame material and iterate).

## Practical workflows (how you’d actually use it)
### 1) Mechanism-first (robotics/prototyping)
1. Start from an example spec in `examples/`.
2. Generate a bundle with `scripts/mecha_splicer_spec.py`.
3. Read `MECH_CHECK.md` and tune the spec (clearance, wall thickness, travel, load).
4. Print parts → test-fit → iterate.

### 4) Export for printing
1. Generate bundle to a folder.
2. Use `PRINT_PLAN.md` + `PARTS.json` as your part list.
3. Optionally run with `--render-openscad-stl` to produce STL files.

### 2) PCB-first (enclosure)
1. Provide `electronics` (PCB W/H + mount holes + ports).
2. Let Mecha-Splicer auto-fill a conservative enclosure around the PCB.
3. Iterate cutouts + clearances until it fits your real connectors/cables.

### 3) Market signals → product pack (Mint)
1. Run `scripts/mecha_splicer_mint.py` to generate bundles from RSS categories.
2. Use `--force-template` to mint a specific mechanism pack (e.g. lead-screw axis).
3. Zip the latest mint for distribution with `scripts/package_latest_mint.py`.
