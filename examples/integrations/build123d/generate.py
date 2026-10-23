"""Optional real build123d CAD producer for the HS external-artifact intake.

Use this to evaluate an external parametric CAD engine. It does not replace
HS's existing isolated CadQuery worker or establish manufacturing clearance.

python -m pip install build123d==0.13.0
python examples/integrations/build123d/generate.py [output_directory]
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from build123d import Box, Cylinder, export_step, export_stl

out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent
out.mkdir(parents=True, exist_ok=True)

# mm are known only because this script supplies them; STL itself is unitless.
dimensions_mm = {"width": 45.0, "height": 35.0, "thickness": 3.0, "through_hole_diameter": 6.0}
part = Box(dimensions_mm["width"], dimensions_mm["height"], dimensions_mm["thickness"]) - Cylinder(
    dimensions_mm["through_hole_diameter"] / 2.0, dimensions_mm["thickness"] + 2
)
files = {"stl": out / "mounting_plate.stl", "step": out / "mounting_plate.step"}
export_stl(part, str(files["stl"]))
export_step(part, str(files["step"]))

manifest = {
    "source": "build123d/0.13.0",
    "units_claim": "mm (script-defined; not encoded by STL)",
    "dimensions_mm": dimensions_mm,
    "modeled_volume_mm3": round(part.volume, 6),
    "artifact_authority": "proposed",
    "physical_fit_verified": False,
    "manufacturability_verified": False,
    "files": {
        kind: {
            "name": path.name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "bytes": path.stat().st_size,
        } for kind, path in files.items()
    },
}
(out / "source_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print(json.dumps(manifest, indent=2))
