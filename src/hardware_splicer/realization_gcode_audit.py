"""Independent text G-code auditor. A passed file audit never permits printing."""
from __future__ import annotations
import hashlib, json, math, re
from pathlib import Path
from typing import Any

META=re.compile(r'^;\s*([^=\n]+?)\s*=\s*(.*)$')
POS=re.compile(r'(?:^|\s)([XYZE])(-?\d+(?:\.\d+)?)')

def audit_offline_gcode(path:Path,bed_xy=(250.0,210.0),margin=4.0)->dict[str,Any]:
    p=Path(path)
    if not p.is_file() or not 1000 <= p.stat().st_size <= 40_000_000:raise ValueError("invalid G-code file size")
    data=p.read_bytes()
    if b'\x00' in data[:1024]:raise ValueError("binary G-code not independently decoded")
    raw=data.decode("ascii")
    meta={}
    x=y=z=None
    coords=[]
    outside=[]
    commands=set()
    layers=0
    danger=set()
    for line in raw.splitlines():
        if line.startswith(';LAYER_CHANGE'):layers+=1
        m=META.match(line)
        if m:meta[m.group(1).strip()]=m.group(2).strip()
        s=line.split(';',1)[0].strip()
        if not s:continue
        name=s.split(maxsplit=1)[0]
        if name in ('M500','M501','M502','M997','M999','M112','M303'):danger.add(name)
        commands.add(name)
        if name not in ('G0','G1'):continue
        kv={k:float(v) for k,v in POS.findall(s)}
        x=kv.get('X',x);y=kv.get('Y',y);z=kv.get('Z',z)
        if 'E' in kv and x is not None and y is not None:
            coords.append([x,y])
            if x < 0 or y < 0 or x > bed_xy[0] or y > bed_xy[1]:
                outside.append([x,y])
    try:
        objects=json.loads(meta["objects_info"])["objects"]
    except (KeyError,ValueError,TypeError) as e:raise ValueError("G-code object metadata invalid") from e
    names={o["name"] for o in objects}
    if names!={"HS_Casing_Base","HS_Casing_Lid"}:
        raise ValueError("G-code object identity mismatch")
    bboxes={}
    for obj in objects:
        xy=obj["polygon"]
        if len(xy)<3 or any(len(v)!=2 for v in xy):raise ValueError("invalid polygon")
        xs=[v[0] for v in xy];ys=[v[1] for v in xy]
        if not all(math.isfinite(v) for v in xs+ys):raise ValueError("invalid polygon point")
        bbox=[min(xs),min(ys),max(xs),max(ys)]
        if (bbox[0]<margin or bbox[1]<margin
            or bbox[2]>bed_xy[0]-margin or bbox[3]>bed_xy[1]-margin):
            raise ValueError("model footprint too close to or beyond bed boundary")
        bboxes[obj["name"]]=bbox
    if meta.get("printer_model")!="MK4S" or meta.get("nozzle_diameter")!="0.4" or meta.get("filament_type")!="PLA":
        raise ValueError("G-code printer/nozzle/filament profile mismatch")
    if not {"G28","M104","M109","M140","M190"}.issubset(commands):
        raise ValueError("missing expected heater/homing sequence")
    if danger:raise ValueError("G-code contains disallowed machine command")
    if 'M104 S0' not in raw or 'M140 S0' not in raw:raise ValueError("no heater shutdown")
    if layers<10 or len(coords)<100:raise ValueError("no plausible layer geometry")
    mass=float(meta.get("filament used [g]","nan"))
    if not math.isfinite(mass) or not 0<mass<1000:raise ValueError("invalid material use")
    return {
        "schema_version":"hs.offline_gcode_audit.v1",
        "sha256":hashlib.sha256(data).hexdigest(),
        "bytes":len(data),
        "printer_model_from_gcode":meta["printer_model"],
        "nozzle_mm":0.4,
        "filament_type":"PLA",
        "object_bounding_boxes_mm":bboxes,
        "model_footprints_have_at_least_4mm_bed_margin":True,
        "layer_changes":layers,
        "extrusion_motion_count":len(coords),
        "estimated_filament_grams":mass,
        "estimated_print_time":meta.get("estimated printing time (normal mode)"),
        "extrusion_moves_outside_nominal_bed":len(outside),
        "out_of_bed_motion_examples":outside[:10],
        "vendor_purge_path_review_required":bool(outside),
        "printer_physically_identified":False,
        "firmware_and_profile_matched_to_real_machine":False,
        "operator_preview_checked":False,
        "real_print_authorized":False,
        "printed":False,
    }
