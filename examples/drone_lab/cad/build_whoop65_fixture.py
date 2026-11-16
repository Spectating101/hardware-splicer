"""HS WHOOP65 — real printable fabrication tooling in Atech Atelier / FreeCAD.

Creates two editable FreeCAD parts and exports STEP/STL, not just test logs.
Run inside the official FreeCAD Python interpreter bundled with Atech Atelier:

    FreeCADCmd examples/drone_lab/cad/build_whoop65_fixture.py

or in FreeCAD's Python console:
    exec(open('/absolute/path/to/build_whoop65_fixture.py').read())

Outputs go to HS_CAD_OUTPUT or ./hs-whoop65-cad-exports.
A 26x26 board mount jig is a BENCH TOOL, not a flight component.
The 11.7 x 6.8 battery-cage go gauge is a TEST PIECE; it is NOT a battery.
"""

import json
import os
from pathlib import Path

import FreeCAD as App
import Part
import Mesh

OUT = Path(os.environ.get("HS_CAD_OUTPUT", "./hs-whoop65-cad-exports")).expanduser().resolve()
OUT.mkdir(parents=True, exist_ok=True)

PITCH_MM = 26.0
JIG_SIZE_MM = 38.0
PLATE_THICKNESS_MM = 2.4
MOUNT_CLEARANCE_DIAMETER_MM = 1.8  # non-threaded test; confirm exact FC holes
WINDOW_MM = 17.0
CAGE_SOURCE_X_MM = 11.9  # from vsergeev's actual 65mm_26x26_whoop.scad
CAGE_SOURCE_Z_MM = 7.0
GAUGE_X_MM = 11.7  # printable test gauge leaves 0.2mm total clearance
GAUGE_Z_MM = 6.8
GAUGE_LENGTH_MM = 17.0

def bbox_mm(shape):
    bb = shape.BoundBox
    return [round(float(bb.XLength), 3), round(float(bb.YLength), 3), round(float(bb.ZLength), 3)]

def out_part(doc_name, label, shape):
    assert not shape.isNull(), f"{label}: null geometry"
    assert shape.isValid(), f"{label}: invalid BREP"
    assert len(shape.Solids) == 1, f"{label}: must be one solid"
    doc = App.newDocument(doc_name)
    obj = doc.addObject("Part::Feature", "PrintableSolid")
    obj.Label = label
    obj.Shape = shape.removeSplitter()
    doc.recompute()
    files = {
        "fcstd": OUT / (doc_name + ".FCStd"),
        "step": OUT / (doc_name + ".step"),
        "stl": OUT / (doc_name + ".stl"),
    }
    doc.saveAs(str(files["fcstd"]))
    Part.export([obj], str(files["step"]))
    Mesh.export([obj], str(files["stl"]))
    data = {
        "part": doc_name,
        "label": label,
        "dimensions_mm": bbox_mm(obj.Shape),
        "volume_mm3": round(float(obj.Shape.Volume), 4),
        "faces": len(obj.Shape.Faces),
        "valid_brep": obj.Shape.isValid(),
        "solid_count": len(obj.Shape.Solids),
        "outputs": {key: path.name for key,path in files.items()},
        "fabrication_status": "CAD exported; NOT printed, installed or fit-tested",
    }
    App.closeDocument(doc.Name)
    return data

# 26mm-pitch board mounting inspection jig: four real through-holes, 17mm
# central observation aperture, corners retained for tactile squareness.
# Verify the actual Matrix 1S AIO hole diameters before using this as a
# drilling or screw alignment guide.
origin = -JIG_SIZE_MM/2
plate = Part.makeBox(JIG_SIZE_MM, JIG_SIZE_MM, PLATE_THICKNESS_MM,
                     App.Vector(origin, origin, 0))
view_cut = Part.makeBox(WINDOW_MM, WINDOW_MM, PLATE_THICKNESS_MM + 2,
                        App.Vector(-WINDOW_MM/2, -WINDOW_MM/2, -1))
plate = plate.cut(view_cut)
for x in (-PITCH_MM/2, PITCH_MM/2):
    for y in (-PITCH_MM/2, PITCH_MM/2):
        tool = Part.makeCylinder(MOUNT_CLEARANCE_DIAMETER_MM/2,
                                 PLATE_THICKNESS_MM + 2, App.Vector(x,y,-1))
        plate = plate.cut(tool)
jig = out_part("whoop65_26x26_board_fit_jig",
               "26x26mm AIO alignment plate, 4×Ø1.8 holes", plate)

# Physical GO/NO-GO test for source frame battery cage 11.9 × 7.0mm.
# Gauge mimics a slightly undersized pack cross-section, not a certified pack.
# Main prism is along Y, handle attached with overlapping solid.
prism = Part.makeBox(GAUGE_X_MM, GAUGE_LENGTH_MM, GAUGE_Z_MM,
                     App.Vector(-GAUGE_X_MM/2,0,0))
handle = Part.makeBox(18,4,10,
                      App.Vector(-9,GAUGE_LENGTH_MM-0.5,-1.6))
gauge_shape = prism.fuse(handle)
gauge = out_part("whoop65_battery_pocket_go_gauge",
                 "11.7×6.8mm cage-fit dummy; do not mount on aircraft", gauge_shape)

manifest = {
    "schema_version": "hs.whoop65.freecad_real_exports.v1",
    "source_design": "https://github.com/vsergeev/3d-parametric-whoop",
    "source_frame_parameters_mm": {
        "wheelbase": 65, "fc_mount_pitch": PITCH_MM,
        "battery_cage_x": CAGE_SOURCE_X_MM,
        "battery_cage_z": CAGE_SOURCE_Z_MM,
    },
    "design_authority": "Original airframe and electronics remain vsergeev's 65mm source build",
    "cad_engine": "Atech Atelier official FreeCAD 1.1.3 (unmodified FreeCAD core)",
    "notes": [
        "Two real CAD solids, STEP and STL for manufacturing/inspection, native FCStd for edits.",
        "Jig is bench fixture, not part of flying mass.",
        "Battery gauge is a 3D-printed dummy, not a charger and not a cell.",
        "Accuracy depends on printer calibration, material and actual purchased board/pack dimensions.",
        "Do not claim functional physical fit before testing the printed pieces.",
    ],
    "parts": [jig, gauge],
    "physical_print_completed": False,
    "physical_drone_assembled": False,
}
(OUT / "whoop65_cad_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
print("HS_WHOOP65_REAL_CAD_EXPORTS=" + str(OUT))
print(json.dumps(manifest,indent=2))
