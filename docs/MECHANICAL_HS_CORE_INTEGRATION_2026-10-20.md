# Integrating mechanical CAD/FEM into Hardware Splicer

## How it is connected

Hardware Splicer's curved contact and structural investigation now participates
in the existing Mecha-Splicer build workflow, normal risk register,
simulation summary, build recipe, HS mechanism pack, capability report and
mechanical / mechatronics release authority.

The everyday default is structural_screening="advisory": fast, no Gmsh
execution, identifies what contact models are supported and what remains to
be tested. Structural screening is opt-in on a trusted local machine.

## Opt-in inside the existing Mecha runner

Sample Python usage:

    from mecha_splicer.runner import run
    result = run(
        {
            "project_name": "repair-bracket",
            "mode": "prototype",
            "process": "fdm",
            "bracket": {
                "name": "plate", "w_mm": 60, "d_mm": 20, "t_mm": 4,
                "hole_d_mm": 3.2, "hole_spacing_mm": 40
            },
        },
        out_dir="./new-bracket-build",
        structural_screening="run",
        structural_mesh_sizes_mm=(8.,6.,5.),
        structural_pin_drive_mm=.02,
        structural_radial_clearance_mm=.005,
    )
    print(result["structural_screening"]["status"])

The pin displacement and radial clearance here are explicitly
ILLUSTRATIVE ASSUMPTIONS, not measurements.

The normal Mecha build now includes status and blockers in:
- mecha_splicer.bundle.json
- SIM_RESULTS.json
- MECH_CHECK.md
- RISK_REGISTER.md
- BUILD_RECIPE.md

Opt-in screening additionally creates STRUCTURAL_SPEC.json and:
- STRUCTURAL_SCREENING/bracket.step
- STRUCTURAL_SCREENING/evidence.json
- STRUCTURAL_SCREENING/review.html
- STRUCTURAL_SCREENING/predicted_load_curve.csv
- STRUCTURAL_SCREENING/remaining_actions.txt

Every generated STEP and spec is hash-bound; output folders must not
already contain a structural run. A failed FEM run returns an explicit
blocked structural status, not a successful result.

## HS operator CLI

Install the optional structural dependencies, then use:

    python -m pip install -e '.[dev,physics,cad-meshing,physics-validation]'
    hs-mechanical --spec-json examples/mechanical/mecha_simple_plate_bracket.json --output-dir ./pilot-001 --mesh-study-mm 8 6 5 --drive-mm .02 --clearance-mm .005

The local workbench emits independent JSON, HTML, STEP, load-curve CSV
and physical-test checklist. Exit code 2 denotes a completed
investigation with unresolved approval blockers. It is not a build
approval. Avoid interpreting even a zero exit code as a certification.

## HS project and authority flow

The salvage/electronics-to-Mecha mechanism bridge carries
structural_screening and structural_release_blocked state into
MECHANISM_PACK.json and MECHATRONICS_PACK.json.

The mechanical and mechatronics authority ledgers read attached
structural evidence. If an attached structural screen remains
inconclusive, unavailable or intentionally disabled, they refuse a
production release claim even if unrelated engineering paperwork is
complete. Other existing electrical and physical release gates remain.

The optional capability registry lists Gmsh, scikit-fem, SciPy and
NumPy. Only the actual locally installed runtime can be reported ready;
the existence of the code alone is not considered a tested result.

## Honest scope

The current validated geometry is a single rectangular plate with
two cylindrical through-holes, rigid frictionless pins and an assumed
linear isotropic material. It DOES NOT validate enclosure standoffs,
servo mounts, grippers, snap-fits, screw bosses or complete assemblies
automatically. Those geometries receive an explicit unsupported status.

Peak structural stresses and continuum contact constraints still have
unresolved numerical convergence. Physical material properties, print
orientation, actual hole/pin fit and measured load/failure testing remain
missing. No load-bearing fabrication or release is authorized.

No arbitrary-path HTTP route has been added. This integration works
through local, opt-in tools and the normal HS evidence workflow.

Future model extensions should be selected by geometry/load class and
validated separately: enclosure standoffs, repair brackets, screw bosses
and snap tabs are likely next useful cases.
