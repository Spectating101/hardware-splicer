#!/usr/bin/env python3
"""Place library footprints on a new board from a JSON spec (see kicad_component_board.pcb_spec). Runs under a
pcbnew-capable interpreter.

    build_component_board.py spec.json out.kicad_pcb            # placement, outline, rules, pre-routed tracks, keepouts
    build_component_board.py --finish spec.json in.kicad_pcb out.kicad_pcb
        # on a routed board: assign every pad's net, add the spec's late tracks, vias and zones, drop keepouts, fill
"""
from __future__ import annotations

import json
import sys

import pcbnew

MM = pcbnew.FromMM


def _vec(x: float, y: float) -> "pcbnew.VECTOR2I":
    return pcbnew.VECTOR2I(MM(x), MM(y))


def _net(board, name: str):
    net = board.FindNet(name)
    if net is None:
        net = pcbnew.NETINFO_ITEM(board, name)
        board.Add(net)
    return net


def _layer(board, name: str) -> int:
    return board.GetLayerID(name)


def _rules(board, spec) -> None:
    r = spec["rules"]
    ds = board.GetDesignSettings()
    ds.m_TrackMinWidth = MM(r["min_track"])
    ds.m_MinClearance = MM(r["clearance"])
    ds.m_ViasMinSize = MM(r["via_d"])
    ds.m_MinThroughDrill = MM(r["via_drill"])
    ds.m_CopperEdgeClearance = MM(r["edge_clearance"])
    ns = ds.m_NetSettings
    default = ns.GetDefaultNetclass()
    default.SetClearance(MM(r["clearance"]))
    default.SetTrackWidth(MM(r["track"]))
    default.SetViaDiameter(MM(r["via_d"]))
    default.SetViaDrill(MM(r["via_drill"]))
    for nc_spec in spec.get("netclasses", []):
        nc = pcbnew.NETCLASS(nc_spec["name"])
        nc.SetClearance(MM(nc_spec.get("clearance", r["clearance"])))
        nc.SetTrackWidth(MM(nc_spec["track"]))
        nc.SetViaDiameter(MM(nc_spec.get("via_d", r["via_d"])))
        nc.SetViaDrill(MM(nc_spec.get("via_drill", r["via_drill"])))
        ns.SetNetclass(nc_spec["name"], nc)
        for pattern in nc_spec.get("patterns", []):
            ns.SetNetclassPatternAssignment(pattern, nc_spec["name"])


def _outline(board, spec) -> None:
    x0, y0, x1, y1 = spec["outline_mm"]
    pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    for (ax, ay), (bx, by) in zip(pts, pts[1:] + pts[:1]):
        seg = pcbnew.PCB_SHAPE(board)
        seg.SetShape(pcbnew.SHAPE_T_SEGMENT)
        seg.SetStart(_vec(ax, ay))
        seg.SetEnd(_vec(bx, by))
        seg.SetLayer(pcbnew.Edge_Cuts)
        seg.SetWidth(MM(0.1))
        board.Add(seg)


def _footprints(board, spec) -> None:
    for part in spec["parts"]:
        lib, name = part["footprint"].split(":", 1)
        fp = pcbnew.FootprintLoad(f"{spec['footprint_dir']}/{lib}.pretty", name)
        if fp is None:
            raise SystemExit(f"footprint not found: {part['footprint']}")
        fp.SetFPID(pcbnew.LIB_ID(lib, name))
        fp.SetReference(part["ref"])
        fp.SetValue(part["value"])
        if part.get("uuid"):
            fp.SetPath(pcbnew.KIID_PATH("/" + part["uuid"]))
        board.Add(fp)
        fp.SetPosition(_vec(part["x"], part["y"]))
        if part.get("side") == "bottom":
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_TOP_BOTTOM)
        fp.SetOrientationDegrees(part.get("rot", 0))
        for pad in fp.Pads():
            net = part["nets"].get(pad.GetNumber())
            if net:
                pad.SetNet(_net(board, net))


def _assign_all(board, spec) -> None:
    by_ref = {p["ref"]: p for p in spec["parts"]}
    for fp in board.GetFootprints():
        part = by_ref.get(fp.GetReference())
        if not part:
            continue
        for pad in fp.Pads():
            net = part["nets"].get(pad.GetNumber())
            if net:
                pad.SetNet(_net(board, net))


def _tracks(board, items) -> None:
    for t in items:
        net = _net(board, t["net"])
        if t.get("pad_via"):  # a short track from a pad to a via beside it, e.g. a ground pin inside another net's pour
            px, py = _pad_xy(board, t["pad_via"])
            vx, vy = px + t["offset"][0], py + t["offset"][1]
            _tracks(board, [{"net": t["net"], "points": [(px, py), (vx, vy)], "width": t.get("width", 0.5), "layer": t.get("layer", "F.Cu")},
                            {"net": t["net"], "via": True, "at": (vx, vy), "d": t.get("d", 0.8), "drill": t.get("drill", 0.4)}])
            continue
        if t.get("via"):
            via = pcbnew.PCB_VIA(board)
            via.SetPosition(_vec(*t["at"]))
            via.SetWidth(MM(t.get("d", 0.6)))
            via.SetDrill(MM(t.get("drill", 0.3)))
            via.SetNet(net)
            via.SetLocked(True)
            board.Add(via)
            continue
        pts = t.get("points") or [_pad_xy(board, end) for end in t["pads"]]
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            tr = pcbnew.PCB_TRACK(board)
            tr.SetStart(_vec(ax, ay))
            tr.SetEnd(_vec(bx, by))
            tr.SetWidth(MM(t["width"]))
            tr.SetLayer(_layer(board, t.get("layer", "F.Cu")))
            tr.SetNet(net)
            tr.SetLocked(True)
            board.Add(tr)


def _pad_xy(board, end: str) -> tuple[float, float]:
    ref, _, number = end.partition(".")
    fp = board.FindFootprintByReference(ref)
    pad = next(p for p in fp.Pads() if p.GetNumber() == number)
    pos = pad.GetPosition()
    return (pcbnew.ToMM(pos.x), pcbnew.ToMM(pos.y))


def _polygon(zone, pts) -> None:
    outline = zone.Outline()
    outline.NewOutline()
    for x, y in pts:
        outline.Append(MM(x), MM(y))


def _keepouts(board, items) -> None:
    for k in items:
        zone = pcbnew.ZONE(board)
        zone.SetIsRuleArea(True)
        zone.SetLayer(_layer(board, k["layer"]))
        zone.SetDoNotAllowTracks(k.get("no_tracks", True))
        zone.SetDoNotAllowVias(k.get("no_vias", False))
        zone.SetDoNotAllowCopperPour(False)
        zone.SetDoNotAllowPads(False)
        zone.SetDoNotAllowFootprints(False)
        zone.SetZoneName(k.get("name", "keepout"))
        _polygon(zone, k["polygon"])
        board.Add(zone)


def _zones(board, items) -> None:
    for z in items:
        zone = pcbnew.ZONE(board)
        zone.SetLayer(_layer(board, z["layer"]))
        zone.SetNet(_net(board, z["net"]))
        zone.SetAssignedPriority(z.get("priority", 0))
        zone.SetLocalClearance(MM(z.get("clearance", 0.3)))
        zone.SetMinThickness(MM(z.get("min_width", 0.25)))
        zone.SetThermalReliefGap(MM(z.get("thermal_gap", 0.5)))
        zone.SetThermalReliefSpokeWidth(MM(z.get("spoke", 0.5)))
        if z.get("solid_pads"):
            zone.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
        zone.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        zone.SetZoneName(z.get("name", z["net"]))
        _polygon(zone, z["polygon"])
        board.Add(zone)


def _inside(pt, poly) -> bool:
    x, y = pt
    hit = False
    for (ax, ay), (bx, by) in zip(poly, poly[1:] + poly[:1]):
        if (ay > y) != (by > y) and x < ax + (y - ay) * (bx - ax) / (by - ay):
            hit = not hit
    return hit


def _seg_dist(p, a, b) -> float:
    (px, py), (ax, ay), (bx, by) = p, a, b
    dx, dy = bx - ax, by - ay
    t = 0.0 if dx == dy == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return ((px - ax - t * dx) ** 2 + (py - ay - t * dy) ** 2) ** 0.5


def _stitch(board, st, rules, outline) -> None:
    """Ground vias on a grid wherever one fits: clear of every pad (and its hole), track, via and courtyard-free of the
    board edge by the rules' clearances. DRC checks the result independently."""
    to_mm = pcbnew.ToMM
    r = st["d"] / 2
    gap = rules["clearance"] + 0.05
    obstacles = []  # (kind, geometry, half-size)
    for fp in board.GetFootprints():
        bb = fp.GetBoundingBox(False)  # the part body and courtyard, not its text: no vias under parts
        obstacles.append(("box", (to_mm(bb.GetLeft()), to_mm(bb.GetTop()), to_mm(bb.GetRight()), to_mm(bb.GetBottom()))))
        for pad in fp.Pads():
            bb = pad.GetBoundingBox()
            obstacles.append(("box", (to_mm(bb.GetLeft()), to_mm(bb.GetTop()), to_mm(bb.GetRight()), to_mm(bb.GetBottom()))))
    for t in board.GetTracks():
        if t.GetClass() == "PCB_VIA":
            p = t.GetPosition()
            obstacles.append(("pt", (to_mm(p.x), to_mm(p.y)), to_mm(t.GetWidth(pcbnew.F_Cu)) / 2))
        else:
            obstacles.append(("seg", ((to_mm(t.GetStart().x), to_mm(t.GetStart().y)), (to_mm(t.GetEnd().x), to_mm(t.GetEnd().y))),
                              to_mm(t.GetWidth()) / 2))
    x0, y0, x1, y1 = outline
    edge = rules["edge_clearance"] + r + 0.2
    placed = 0
    y = y0 + edge
    while y <= y1 - edge:
        x = x0 + edge
        while x <= x1 - edge:
            ok = not any(_inside((x, y), poly) for poly in st.get("avoid", []))
            for ob in obstacles if ok else []:
                if ob[0] == "box":
                    l, t_, rr, b = ob[1]
                    if l - r - gap <= x <= rr + r + gap and t_ - r - gap <= y <= b + r + gap:
                        ok = False
                elif ob[0] == "pt":
                    if ((x - ob[1][0]) ** 2 + (y - ob[1][1]) ** 2) ** 0.5 < r + ob[2] + gap:
                        ok = False
                elif _seg_dist((x, y), *ob[1]) < r + ob[2] + gap:
                    ok = False
                if not ok:
                    break
            if ok:
                _tracks(board, [{"net": st["net"], "via": True, "at": (x, y), "d": st["d"], "drill": st["drill"]}])
                obstacles.append(("pt", (x, y), r))
                placed += 1
            x += st["pitch"]
        y += st["pitch"]
    print(f"stitching vias: {placed}")


def _remove_dangling(board) -> int:
    """Delete router leftovers: segments lying wholly on another segment of the same net and layer (back-and-forth
    doubles), then segments with an end that touches nothing on their net, until none remain. KiCad's Python API stops
    listing tracks after a removal, so the list is kept here."""
    items = list(board.Tracks())
    pads = [pad for fp in board.GetFootprints() for pad in fp.Pads()]
    segs = [t for t in items if t.GetClass() == "PCB_TRACK"]
    vias = [t for t in items if t.GetClass() == "PCB_VIA"]
    removed = 0

    def drop(seg) -> None:
        nonlocal removed
        segs.remove(seg)
        board.Remove(seg)
        removed += 1

    changed = True
    while changed:
        changed = False
        for seg in segs:
            if any(t is not seg and t.GetNetCode() == seg.GetNetCode() and t.GetLayer() == seg.GetLayer()
                   and t.HitTest(seg.GetStart(), 1000) and t.HitTest(seg.GetEnd(), 1000) for t in segs):
                drop(seg)
                changed = True
                break

    def touches(seg, pt) -> bool:
        net = seg.GetNetCode()
        if any(v.GetNetCode() == net and (v.GetPosition() - pt).EuclideanNorm() <= v.GetWidth(pcbnew.F_Cu) / 2 for v in vias):
            return True
        if any(t is not seg and t.GetNetCode() == net and t.GetLayer() == seg.GetLayer() and t.HitTest(pt, int(seg.GetWidth() / 2))
               for t in segs):
            return True
        return any(p.GetNetCode() == net and p.IsOnLayer(seg.GetLayer()) and p.HitTest(pt) for p in pads)

    changed = True
    while changed:
        dangling = [t for t in segs if not (touches(t, t.GetStart()) and touches(t, t.GetEnd()))]
        changed = bool(dangling)
        for t in dangling:
            drop(t)
    return removed


def tidy(src: str, out: str) -> None:
    board = pcbnew.LoadBoard(src)
    print(f"dangling segments removed: {_remove_dangling(board)}")
    board.BuildConnectivity()
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(out, board)


def build(spec_path: str, out: str) -> None:
    spec = json.load(open(spec_path))
    board = pcbnew.NewBoard(out)
    board.SetCopperLayerCount(2)
    _rules(board, spec)
    _outline(board, spec)
    _footprints(board, spec)
    _tracks(board, spec.get("tracks", []))
    _keepouts(board, spec.get("keepouts", []))
    board.BuildConnectivity()
    pcbnew.SaveBoard(out, board)


def finish(spec_path: str, src: str, out: str) -> None:
    spec = json.load(open(spec_path))
    board = pcbnew.LoadBoard(src)
    _rules(board, spec)
    for zone in list(board.Zones()):
        if zone.GetIsRuleArea():
            board.Remove(zone)
    _assign_all(board, spec)
    _tracks(board, spec.get("late_tracks", []))
    if spec.get("stitch"):
        _stitch(board, spec["stitch"], spec["rules"], spec["outline_mm"])
    # Last of the item edits: after a removal KiCad's Python API no longer lists the board's items.
    print(f"dangling segments removed: {_remove_dangling(board)}")
    _zones(board, spec.get("zones", []))
    board.BuildConnectivity()
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(out, board)


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "--finish":
        finish(*args[1:4])
    elif args and args[0] == "--tidy":
        tidy(*args[1:3])
    else:
        build(*args[:2])
