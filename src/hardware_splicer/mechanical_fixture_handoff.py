"""Source-bound mechanical fixture strategy and digital CAD evidence.

An independent, reusable HS mechanical-design adapter. This is deliberately
NOT the registered four-hole PCB nest and cannot confer physical authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

REQUEST_SCHEMA = "hardware_splicer.mechanical_fixture_request.v1"
EVIDENCE_SCHEMA = "hardware_splicer.mechanical_fixture_evidence.v1"
POLICY_SCHEMA = "policylab.mechanical_fixture_policy.v1"
_SHA = set("0123456789abcdef")


class MechanicalDesignError(ValueError):
    pass


def _only(value: Any, keys: set[str], label: str) -> dict:
    if not isinstance(value, dict):
        raise MechanicalDesignError(f"{label} must be an object")
    unknown=set(value) - keys
    required=keys - {"source_center_mm"}
    missing=required - set(value)
    if unknown or missing:
        raise MechanicalDesignError(f"{label}: unsupported fields {sorted(unknown)}; missing {sorted(missing)}")
    return value


def _number(value: Any, label: str, low: float, high: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise MechanicalDesignError(f"{label} must be finite and between {low:g} and {high:g}")
    return float(value)


def _sha(text: Any) -> str:
    if not isinstance(text, str) or len(text) != 64 or any(c not in _SHA for c in text):
        raise MechanicalDesignError("Expected a lowercase 64-character SHA-256")
    return text


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False) + "\n").encode()


def load_spec(raw: bytes, source_bytes: bytes) -> dict:
    if len(raw) > 200_000 or not raw:
        raise MechanicalDesignError("Request size is invalid")
    # Strict parsing; silently repeated object keys are not accepted.
    def unique(pairs):
        ans = {}
        for k, v in pairs:
            if k in ans:
                raise MechanicalDesignError(f"Duplicate JSON key: {k}")
            ans[k] = v
        return ans
    try:
        spec = json.loads(raw, object_pairs_hook=unique)
    except (UnicodeError, json.JSONDecodeError) as e:
        raise MechanicalDesignError("Request must be valid UTF-8 JSON") from e
    _only(spec, {"schema", "project_id", "revision", "objective", "source", "board", "interface", "requirements"}, "request")
    if spec["schema"] != REQUEST_SCHEMA:
        raise MechanicalDesignError("Wrong request schema")
    if not isinstance(spec["project_id"], str) or not 1 <= len(spec["project_id"]) <= 100 or not all(c.isalnum() or c in "-_.:" for c in spec["project_id"]):
        raise MechanicalDesignError("Invalid project ID")
    if isinstance(spec["revision"], bool) or not isinstance(spec["revision"], int) or not 1 <= spec["revision"] <= 100000:
        raise MechanicalDesignError("Invalid revision")
    if not isinstance(spec["objective"], str) or not 10 <= len(spec["objective"]) <= 500:
        raise MechanicalDesignError("Expected a bounded objective")
    source = _only(spec["source"], {"filename", "url", "sha256", "geometry_basis", "reproduction_rights"}, "source")
    if not isinstance(source.get("filename"), str) or "/" in source["filename"] or "\\" in source["filename"]:
        raise MechanicalDesignError("Source filename must be a plain name")
    if not isinstance(source.get("url"), str) or not source["url"].startswith("https://"):
        raise MechanicalDesignError("Source URL must be HTTPS")
    if source.get("geometry_basis") not in {"manufacturer_nominal_dimensions", "measured_dimensions", "reviewed_source_geometry"}:
        raise MechanicalDesignError("Unknown geometry basis")
    if source.get("reproduction_rights") != "external_reference_not_redistributed":
        raise MechanicalDesignError("Only nonredistributed reference sources are accepted in this pilot")
    if _sha(source.get("sha256")) != digest(source_bytes):
        raise MechanicalDesignError("Original source bytes differ from pinned SHA-256")
    if len(source_bytes) > 10_000_000 or not source_bytes:
        raise MechanicalDesignError("Source is empty or too large")
    board = _only(spec["board"], {"width_mm", "depth_mm", "thickness_mm", "thickness_basis", "outline_xy_mm", "source_center_mm", "mounting_holes", "mounting_holes_status", "unknown_contacts"}, "board")
    w = _number(board["width_mm"], "board.width_mm", 8, 120)
    d = _number(board["depth_mm"], "board.depth_mm", 8, 120)
    _number(board["thickness_mm"], "board.thickness_mm", 0.5, 6)
    if board["thickness_basis"] not in ("unverified_assumption", "source_dimension", "physical_measurement"):
        raise MechanicalDesignError("Unknown thickness basis")
    if not isinstance(board["unknown_contacts"], bool):
        raise MechanicalDesignError("unknown_contacts must be boolean")
    if board["mounting_holes_status"] not in ("unverified", "verified_source_geometry"):
        raise MechanicalDesignError("Invalid mounting hole state")
    holes = board["mounting_holes"]
    if not isinstance(holes, list) or len(holes) not in (0, 4):
        raise MechanicalDesignError("Holes must be [] or four reviewed locations")
    if board["mounting_holes_status"] == "unverified" and holes:
        raise MechanicalDesignError("Do not supply assumed mounting holes as if verified")
    if board["mounting_holes_status"] == "verified_source_geometry" and len(holes) != 4:
        raise MechanicalDesignError("Verified mounting route requires four sourced hole locations")
    if board["mounting_holes_status"] == "verified_source_geometry":
        if source["geometry_basis"] != "reviewed_source_geometry" or not source["filename"].endswith(".brd"):
            raise MechanicalDesignError("Verified holes require an original EAGLE board source, not a claimed anchor")
        center = board.get("source_center_mm")
        if not isinstance(center, list) or len(center) != 2:
            raise MechanicalDesignError("EAGLE source requires exact board_center_mm as source_center_mm")
        for coordinate in center:
            _number(coordinate, "source center", -10000, 10000)
    elif board.get("source_center_mm") is not None:
        raise MechanicalDesignError("Do not add an arbitrary origin to a hole-less specification")
    coords = set()
    for h in holes:
        _only(h, {"x_mm", "y_mm", "diameter_mm", "source_anchor"}, "mounting hole")
        x = _number(h["x_mm"], "hole.x", -w/2 + 2, w/2 - 2)
        y = _number(h["y_mm"], "hole.y", -d/2 + 2, d/2 - 2)
        _number(h["diameter_mm"], "hole.diameter", 2, 4)
        if not isinstance(h["source_anchor"], str) or not 1 <= len(h["source_anchor"]) <= 80 or not all(c.isalnum() or c in "-_." for c in h["source_anchor"]):
            raise MechanicalDesignError("Verified holes require a source anchor")
        if (x, y) in coords:
            raise MechanicalDesignError("Repeated hole coordinates")
        coords.add((x, y))
    # A source anchor is an identity claim, not proof on its own. Re-read the
    # original EAGLE bytes and compare each named footprint's actual drill and
    # XY location. Restrict to holes centered on their named footprints.
    if board["mounting_holes_status"] == "verified_source_geometry":
        from xml.etree import ElementTree as ET
        try:
            native = ET.fromstring(source_bytes).find("drawing/board")
            if native is None:
                raise ValueError("Missing drawing/board")
            elements={e.get("name"):e for e in native.findall("elements/element")}
            packages={(lib.get("name"),pack.get("name")):pack
                      for lib in native.findall("libraries/library")
                      for pack in lib.findall("packages/package")}
            cx,cy=board["source_center_mm"]
            for h in holes:
                anchor=h["source_anchor"]
                element=elements[anchor]
                package=packages[element.get("library"),element.get("package")]
                drills=package.findall("hole")+package.findall("pad")
                if len(drills)!=1 or abs(float(drills[0].get("x",0)))>1e-6 or abs(float(drills[0].get("y",0)))>1e-6:
                    raise ValueError("Mount-hole footprint geometry is not centered/unique")
                actual=(float(element.get("x"))-cx,float(element.get("y"))-cy,float(drills[0].get("drill")))
                expected=(h["x_mm"],h["y_mm"],h["diameter_mm"])
                if any(abs(x-y)>1e-4 for x,y in zip(actual,expected)):
                    raise ValueError("Sourced mount coordinates/diameters disagree")
        except (ET.ParseError, ValueError, KeyError, TypeError, AttributeError) as exc:
            raise MechanicalDesignError("Original EAGLE mounting source does not support the declared holes") from exc
    outline = board["outline_xy_mm"]
    if outline is not None:
        if not isinstance(outline, list) or not 4 <= len(outline) <= 24:
            raise MechanicalDesignError("Polygon requires 4-24 points")
        for p in outline:
            if not isinstance(p, list) or len(p) != 2:
                raise MechanicalDesignError("Polygon coordinates must be pairs")
            _number(p[0], "outline.x", -w/2, w/2)
            _number(p[1], "outline.y", -d/2, d/2)
        if min(p[0] for p in outline) > -w/2+0.01 or max(p[0] for p in outline) < w/2-0.01 or min(p[1] for p in outline) > -d/2+0.01 or max(p[1] for p in outline) < d/2-0.01:
            raise MechanicalDesignError("Outline bounds must match declared board dimensions")
    inter = _only(spec["interface"], {"usb_corridor_width_mm", "usb_corridor_depth_mm", "antenna_geometry_status", "edge_contacts_status"}, "interface")
    _number(inter["usb_corridor_width_mm"], "USB corridor width", 4, w)
    _number(inter["usb_corridor_depth_mm"], "USB corridor depth", 2, 12)
    if inter["antenna_geometry_status"] not in ("unknown", "source_reviewed"):
        raise MechanicalDesignError("Unknown antenna state")
    if inter["edge_contacts_status"] not in ("unknown", "source_reviewed"):
        raise MechanicalDesignError("Unknown edge-contact state")
    req = _only(spec["requirements"], {"min_nominal_edge_gap_mm", "max_base_width_mm", "max_base_depth_mm", "stationary_unpowered_only"}, "requirements")
    _number(req["min_nominal_edge_gap_mm"], "minimum nominal gap", 0.2, 2)
    _number(req["max_base_width_mm"], "maximum base width", w+3, 200)
    _number(req["max_base_depth_mm"], "maximum base depth", d+3, 200)
    if req["stationary_unpowered_only"] is not True:
        raise MechanicalDesignError("Only unpowered stationary fixtures are supported")
    return spec


def strategies(spec: dict) -> dict:
    b = spec["board"]
    r = spec["requirements"]
    holes = b["mounting_holes_status"] == "verified_source_geometry"
    w, d = b["width_mm"], b["depth_mm"]
    gap = r["min_nominal_edge_gap_mm"]
    # Reserve interface; these are chosen engineering assumptions, not actual physical footprint geometry.
    base_w, base_d = w + 20, d + 16
    return {
        "selected": "source_hole_standoffs" if holes else "holeless_gravity_support",
        "alternatives": [
            {"id": "source_hole_standoffs", "eligible": holes,
             "reason": "Four hole locations with cited source anchors" if holes else "No verified four-hole source pattern; do not invent one"},
            {"id": "holeless_gravity_support", "eligible": True,
             "reason": "Stationary, unpowered nominal envelope fit with accessible edge gaps; no clamping force"},
            {"id": "contact_edge_clamp", "eligible": not b["unknown_contacts"],
             "reason": "Unverified GPIO contacts could be crushed" if b["unknown_contacts"] else "Requires separate physical clamp-force study"},
        ],
        "design": {"base_width_mm": base_w, "base_depth_mm": base_d, "base_height_mm": 3,
                   "support_height_mm": 4.5, "edge_gap_mm": gap, "guide_wall_mm": 1.2},
        "blocked_by_footprint": base_w > r["max_base_width_mm"] or base_d > r["max_base_depth_mm"],
    }


def _source_summary(spec: dict, source: Path) -> dict:
    return {**spec["source"], "observed_sha256": digest(source.read_bytes()), "byte_count": source.stat().st_size}


def build(spec_file: Path, source_file: Path, output: Path) -> dict:
    """Generate actual CAD using reusable HS strategy + independent output checks."""
    if output.exists():
        raise MechanicalDesignError("Output already exists; never overwrite a saved run")
    spec = load_spec(spec_file.read_bytes(), source_file.read_bytes())
    choices = strategies(spec)
    if choices["blocked_by_footprint"]:
        raise MechanicalDesignError("Selected base exceeds the declared maximum footprint")
    import cadquery as cq
    import trimesh
    b=spec["board"]
    g=choices["design"]
    w,d=float(b["width_mm"]),float(b["depth_mm"])
    t=float(b["thickness_mm"])
    base_h=g["base_height_mm"]
    support_h=g["support_height_mm"]
    z=base_h+support_h
    gap=g["edge_gap_mm"]
    wall=g["guide_wall_mm"]
    def box(x,y,h,at,center=(True,True,False)):
        return cq.Workplane("XY").box(x,y,h,centered=center).val().translate(at)
    # Board digital envelope. DXF artwork not decoded as a mechanical outline here.
    if b["outline_xy_mm"] is None:
        board=box(w,d,t,(0,0,z))
    else:
        board=cq.Workplane("XY").polyline([tuple(p) for p in b["outline_xy_mm"]]).close().extrude(t).val().translate((0,0,z))
        if not board.isValid() or board.Volume()<=0:
            raise MechanicalDesignError("Invalid source-provided outline")
    base=box(g["base_width_mm"],g["base_depth_mm"],base_h,(0,0,0))
    parts=[base]
    if choices["selected"]=="source_hole_standoffs":
        for h in b["mounting_holes"]:
            x,y,diam=h["x_mm"],h["y_mm"],h["diameter_mm"]
            support=cq.Solid.makeCylinder(max(2.5,diam*0.82),support_h,cq.Vector(x,y,base_h))
            pin=cq.Solid.makeCylinder((diam-0.4)/2,1.2,cq.Vector(x,y,z))
            parts.extend([support,pin])
            # Reference board also needs *source-verified* holes for its digital collision test.
            board=board.cut(cq.Solid.makeCylinder(diam/2,t+2,cq.Vector(x,y,z-1)))
    else:
        for sx in (-1,1):
            for sy in (-1,1):
                parts.append(box(3.0,3.0,support_h,(sx*w*.27,sy*d*.25,base_h)))
        # At short ends leave a centered USB-access corridor.
        for sx in (-1,1):
            for sy in (-1,1):
                parts.append(box(2.4,wall,6.3,(sx*w*.32,sy*(d/2+gap+wall/2),base_h)))
        # Low-area guides on the long edges. Electrical contacts remain a physical hold.
        for sx in (-1,1):
            parts.append(box(wall,1.5,6.3,(sx*(w/2+gap+wall/2),0,base_h)))
    shape=parts[0]
    for component in parts[1:]:
        shape=shape.fuse(component)
    shape=shape.clean()
    # Digital USB corridors at both ends; their dimensions are declared, not vendor-verified.
    usb_w=spec["interface"]["usb_corridor_width_mm"]
    usb_d=spec["interface"]["usb_corridor_depth_mm"]
    usb_solids=[box(usb_w,usb_d,2,(0,sy*(d/2+usb_d/2),z)) for sy in (-1,1)]
    board_collision=shape.intersect(board).Volume()
    usb_collision=max(shape.intersect(item).Volume() for item in usb_solids)
    # A deliberately displaced edge stop should collide with the board.
    if choices["selected"]=="holeless_gravity_support":
        bad=box(2.4,wall,6.3,(w*.32,d/2+gap+wall/2-(gap+wall),base_h))
        control=bad.intersect(board).Volume()
    else:
        # Move a sourced mounting pin off its known hole center; the board
        # reference must detect the deliberately misplaced cylindrical pin.
        first=b["mounting_holes"][0]
        misplaced=cq.Solid.makeCylinder((first["diameter_mm"]-0.4)/2,1.2,
                      cq.Vector(first["x_mm"]+1.4,first["y_mm"],z))
        control=misplaced.intersect(board).Volume()
    output.mkdir(parents=True,exist_ok=False)
    cad=output/"fixture.step"
    stl=output/"fixture.stl"
    cq.exporters.export(shape,str(cad))
    cq.exporters.export(shape,str(stl))
    reopened=cq.importers.importStep(str(cad)).val()
    mesh=trimesh.load_mesh(str(stl))
    checks={
        "positive_valid_step": bool(shape.isValid() and reopened.isValid() and reopened.Volume()>0),
        "reopened_volume_conserved": abs(shape.Volume()-reopened.Volume())<.001,
        "stl_watertight_single_body":bool(mesh.is_volume and len(mesh.split())==1),
        "nominal_board_collision_free":board_collision<1e-5,
        "provisional_usb_corridors_clear":usb_collision<1e-5,
        "negative_shift_rejected":control>1e-4,
        "footprint_within_target":not choices["blocked_by_footprint"],
    }
    # A missing reference geometry or physical test never becomes a pass.
    physical_blocks=[
        "No physical board, printer, wear, stability, ESD, or repeatability test",
        "Source is nominal mechanical evidence only; original manufacturer DXF artwork not parsed as an exact board outline",
        "Actual connector, antenna, underside components and edge pad clearances unverified",
    ]
    if b["thickness_basis"]=="unverified_assumption":
        physical_blocks.append("Board thickness is a declared assumption")
    if b["unknown_contacts"]:
        physical_blocks.append("Electrical contacts require measured keep-outs before applied retention force")
    verification={"schema":"hardware_splicer.mechanical_fixture_verification.v1",
                  "source_sha256":spec["source"]["sha256"],"selected_strategy":choices["selected"],
                  "checks":[{"id":k,"passed":v} for k,v in checks.items()],
                  "geometry":{"nominal_board_collision_mm3":round(board_collision,6),
                             "usb_corridor_collision_mm3":round(usb_collision,6),
                             "negative_control_collision_mm3":round(control,6) if control is not None else None,
                             "fixture_volume_mm3":round(shape.Volume(),3),
                             "board_width_mm":w,"board_depth_mm":d,
                             "nominal_edge_gap_mm":gap,
                             "base_width_mm":g["base_width_mm"],"base_depth_mm":g["base_depth_mm"]},
                  "digital_checks_passed":all(checks.values()),"physical_status":"UNVERIFIED",
                  "physical_blockers":physical_blocks,
                  "boundary":"Digital collision checks against a declared nominal envelope; not physical safety/fit certification."}
    (output/"verification.json").write_bytes(_canonical(verification))
    if digest(source_file.read_bytes()) != spec["source"]["sha256"]:
        raise MechanicalDesignError("Reference source changed during CAD build")
    (output/"request.json").write_bytes(spec_file.read_bytes())
    (output/"strategies.json").write_bytes(_canonical(choices))
    facts=[
        {"id":"metric.nominal_board_collision_mm3","unit":"mm^3","basis":"computed_nominal_geometry","value":verification["geometry"]["nominal_board_collision_mm3"]},
        {"id":"metric.usb_corridor_collision_mm3","unit":"mm^3","basis":"computed_provisional_corridor","value":verification["geometry"]["usb_corridor_collision_mm3"]},
        {"id":"metric.nominal_edge_gap_mm","unit":"mm","basis":"design_requirement_not_measured","value":gap},
        {"id":"metric.base_width_mm","unit":"mm","basis":"computed_geometry","value":g["base_width_mm"]},
        {"id":"metric.base_depth_mm","unit":"mm","basis":"computed_geometry","value":g["base_depth_mm"]},
    ]
    data={"schema":EVIDENCE_SCHEMA, "implementation_sha256":digest(Path(__file__).read_bytes()), "project_id":spec["project_id"],"revision":spec["revision"],
          "source":_source_summary(spec,source_file),
          "strategy":choices, "verification":verification,"facts":facts,
          "evidence_kind":"digital_nominal_geometry","physical_authority_granted":False,
          "artifacts":{p.name:{"sha256":digest(p.read_bytes()),"bytes":p.stat().st_size}
                       for p in [cad,stl,output/"verification.json",output/"request.json",output/"strategies.json"]}}
    (output/"mechanical-evidence.json").write_bytes(_canonical(data))
    (output/"README.md").write_text(
        f"# {spec['objective']}\n\nStrategy: **{choices['selected']}**. "
        "Only digital geometry and declared nominal dimensions were checked. "
        "Original source bytes were hash-checked but are not included in this package.\n\n"
        "Physical validation needed:\n" + "".join(f"- {b}\n" for b in physical_blocks)
        + "\nNever treat the STEP or STL as approved equipment merely because digital checks pass.\n"
    )
    return {"out":str(output), "strategy":choices["selected"],"digital_checks_passed":all(checks.values()),
            "evidence_sha256":digest((output/"mechanical-evidence.json").read_bytes()),"physical_status":"UNVERIFIED"}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request",required=True,type=Path)
    parser.add_argument("--source",required=True,type=Path)
    parser.add_argument("--out",required=True,type=Path)
    a=parser.parse_args(argv)
    try:
        result=build(a.request,a.source,a.out)
    except (OSError, MechanicalDesignError, ValueError) as exc:
        parser.exit(2,f"{exc}\n")
    print(json.dumps(result))
    return 0 if result["digital_checks_passed"] else 2


if __name__=="__main__":
    raise SystemExit(main())
