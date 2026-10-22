"""Conservative source-driven connector-access screen for an OPEN-TOP SPI shell.

KiCad courtyard is *not* the volume of a mating plug or cable. This module
checks only projected accessibility, mounting boss interference, and net/pin
traceability. It does not approve connectors or enclosure manufacturing.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .assembly_plan import build_assembly_plan

SCHEMA = "hardware_splicer.source_connector_access.v1"
EXPECTED_CONNECTORS = {"J1": 6, "JP1": 2}
SIDE_MARGIN_MM = 2.0  # additional *screening* margin, not validated mating clearance
CAVITY = {"x_min": 3.0, "x_max": 107.0, "y_min": 3.0, "y_max": 67.0}
SHELL_CENTER = (55.0, 35.0)
BOSS_RADIUS_MM = 3.3
BOARD_UNDERSIDE_Z_MM = 5.2
SHELL_TOP_Z_MM = 25.0
PCB_THICKNESS_MM = 1.6


def _source_hash(source: bytes) -> str:
    return "sha256:" + hashlib.sha256(source).hexdigest()


def _number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("missing or nonnumeric connector coordinate")
    answer = float(value)
    if not math.isfinite(answer):
        raise ValueError("nonfinite connector coordinate")
    return answer


def _aabb_circle_separation(aabb: Mapping[str, float], cx: float, cy: float) -> float:
    closest_x = max(aabb["x_min"], min(cx, aabb["x_max"]))
    closest_y = max(aabb["y_min"], min(cy, aabb["y_max"]))
    return math.hypot(cx - closest_x, cy - closest_y)


def inspect_connector_access(*, pcb_path: str | Path,
                             mounting_manifest_path: str | Path,
                             output_path: str | Path | None = None,
                             side_margin_mm: float = SIDE_MARGIN_MM) -> dict:
    margin = _number(side_margin_mm)
    if margin < 0 or margin > 10:
        raise ValueError("bounded source connector clearance margin required")
    pcb_bytes = Path(pcb_path).read_bytes()
    board = build_assembly_plan(pcb_bytes.decode("utf-8"), pcb_sha256=_source_hash(pcb_bytes))
    manifest_bytes = Path(mounting_manifest_path).read_bytes()
    mounts = json.loads(manifest_bytes)
    if mounts.get("schema") != "hardware_splicer.pcb_derived_mounting_cad.v1":
        raise ValueError("unrecognized mounting manifest")
    if mounts.get("input_pcb_sha256") != _source_hash(pcb_bytes):
        raise ValueError("mount/connector KiCad source hashes disagree")
    if len(mounts.get("mounts", [])) != 4:
        raise ValueError("expected four source-authenticated mounting anchors")
    edges = board["board"]["outline"]["bbox"]
    mid_x = (edges["x0"] + edges["x1"]) / 2
    mid_y = (edges["y0"] + edges["y1"]) / 2

    def cad_xy(x: Any, y: Any) -> tuple[float, float]:
        return (round(SHELL_CENTER[0] + _number(x) - mid_x, 3),
                round(SHELL_CENTER[1] + _number(y) - mid_y, 3))

    connectors = [p for p in board["parts"]
                  if p["kind"] == "connector" and not p["do_not_populate"]]
    refs = [part["ref"] for part in connectors]
    if len(refs) != len(EXPECTED_CONNECTORS) or set(refs) != set(EXPECTED_CONNECTORS):
        raise ValueError("unexpected populated connector identities")
    findings: list[dict] = []
    for part in sorted(connectors, key=lambda p: p["ref"]):
        ref = part["ref"]
        # The reference design has VERTICAL THT pin headers, accessible
        # from above when the shell truly has an open top.
        if (part["side"] != "front" or part["mounting"] != "through_hole"
                or "_Vertical" not in part["footprint"]
                or abs(_number(part["rotation_deg"])) > 1e-5):
            raise ValueError(f"{ref}: unsupported mating direction or board side")
        if part["pad_count"] != EXPECTED_CONNECTORS[ref]:
            raise ValueError(f"{ref}: connector pad count changed")
        if len(part["pads"]) != EXPECTED_CONNECTORS[ref]:
            raise ValueError(f"{ref}: missing source pad/net identity")
        pins = [pin["number"] for pin in part["pads"]]
        if len(set(pins)) != len(pins):
            raise ValueError(f"{ref}: duplicated electrical pin numbers")
        points = part.get("corners")
        if not isinstance(points, list) or len(points) != 4:
            raise ValueError(f"{ref}: missing source courtyard geometry")
        xs, ys = [], []
        for xy in points:
            if not isinstance(xy, list) or len(xy) != 2:
                raise ValueError(f"{ref}: missing courtyard point")
            x, y = cad_xy(xy[0], xy[1])
            xs.append(x)
            ys.append(y)
        keepout = {
            "x_min": round(min(xs)-margin, 3), "x_max": round(max(xs)+margin, 3),
            "y_min": round(min(ys)-margin, 3), "y_max": round(max(ys)+margin, 3),
        }
        fits_cavity_xy = all(
            keepout[k] >= CAVITY[k] if k.endswith("min") else keepout[k] <= CAVITY[k]
            for k in keepout
        )
        boss_distances = []
        for mount in mounts["mounts"]:
            mx, my = mount["cad_shell_center_xy_mm"]
            distance = _aabb_circle_separation(keepout, _number(mx), _number(my))
            boss_distances.append({"ref": mount["ref"],
                                   "min_distance_from_courtyard_keepout_mm": round(distance, 3),
                                   "nominal_boss_overlap": distance < BOSS_RADIUS_MM})
        boss_clear = not any(row["nominal_boss_overlap"] for row in boss_distances)
        findings.append({
            "ref": ref,
            "connector_footprint": part["footprint"],
            "geometry_basis": part["outline_basis"],
            "mating_direction_from_footprint": "vertical_from_open_top_inferred",
            "cad_origin_xy_mm": list(cad_xy(part["x"], part["y"])),
            "pcb_relative_pin_positions": [
                {"number": pin["number"], "cad_xy_mm": list(cad_xy(pin["x"], pin["y"])),
                 "net": pin["net"]}
                for pin in sorted(part["pads"], key=lambda p: int(p["number"]))
            ],
            "nominal_courtyard_plus_margin_mm": keepout,
            "margin_mm": margin,
            "clear_of_cavity_walls_xy": fits_cavity_xy,
            "clear_of_proposed_bosses_xy": boss_clear,
            "nominal_open_top_space_above_board_mm":
                SHELL_TOP_Z_MM-(BOARD_UNDERSIDE_Z_MM+PCB_THICKNESS_MM),
            "boss_proximities": boss_distances,
            "exact_manufacturer_connector_body_authenticated": False,
            "mating_cable_or_shroud_envelope_authenticated": False,
            "lid_aperture_modeled": False,
            "physical_connect_disconnection_tested": False,
        })
    nominal_clear = all(x["clear_of_cavity_walls_xy"] and x["clear_of_proposed_bosses_xy"]
                        for x in findings)
    report = {
        "schema": SCHEMA,
        "status": ("nominal_open_top_projection_clear_unverified" if nominal_clear
                   else "blocked_source_connector_courtyard_projection"),
        "pcb_source_sha256": _source_hash(pcb_bytes),
        "mount_manifest_sha256": _source_hash(manifest_bytes),
        "nominal_open_top": True,
        "connector_count": len(findings),
        "connectors": findings,
        "inferred_vertical_mating_envelope_only": True,
        "electrical_net_pin_traceability_from_kicad": True,
        "source_backed_manufacturer_mating_geometry": False,
        "lid_and_side_cutouts_not_required_for_this_open_top_only": True,
        "cable_bend_radius_and_strain_relief_verified": False,
        "fabrication_authorized": False,
        "release_authorized": False,
    }
    if output_path:
        dest = Path(output_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(report, indent=2, allow_nan=False)+"\n",
                        encoding="utf-8")
    return report
