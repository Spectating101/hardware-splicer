"""Standalone trusted CAD import worker invoked by HS in bounded subprocess.

Requires a separately installed Python 3.12 CAD kernel. Not a shell script.
The parent process validates source size/hash, chooses the file path, and enforces
wall clock timeout; this worker never opens network resources or writes files.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit('expected one STEP file')
    import cadquery as cq
    p = Path(sys.argv[1])
    model = cq.importers.importStep(str(p))
    shape = model.val()
    bbox = shape.BoundingBox()
    n_solids = len(model.solids().vals())
    sizes = {axis: round(getattr(bbox, axis + 'len'), 4) for axis in 'xyz'}
    lows = {axis: round(getattr(bbox, axis + 'min'), 4) for axis in 'xyz'}
    highs = {axis: round(getattr(bbox, axis + 'max'), 4) for axis in 'xyz'}
    print(json.dumps({
        'status': 'imported_brep',
        'cad_kernel': 'CadQuery/OpenCascade',
        'source_sha256': 'sha256:' + hashlib.sha256(p.read_bytes()).hexdigest(),
        'solid_count': n_solids,
        'bounding_box_mm': {'span': sizes, 'min': lows, 'max': highs},
        'coordinate_axes_are_original_source_orientation': True,
        'mounting_interfaces_verified': False,
        'physical_clearances_verified': False,
        'manufacturer_design_maturity_unverified': True,
        'fabrication_authorized': False,
    }, separators=(',', ':')))


if __name__ == '__main__':
    main()
