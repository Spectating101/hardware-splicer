"""Move footprint reference labels off copper and off other silkscreen, in KiCad's own Python.

    python clear_silk_labels.py board.kicad_pcb [REF ...]

For each named footprint (all footprints when none are named) whose reference label overlaps a pad, another part's
silkscreen or label, or the board edge, try positions around the part (above, below, left, right; upright and turned
90 degrees) and keep the first one clear of all of them, with 0.15 mm to spare. A label with no clear position is left
where it was and listed. Prints JSON: moved, already_clear, no_room. Only label positions change; parts, copper and nets
do not, so the board's routing and DRC parity stay as they were.
"""
import json
import sys

import pcbnew

MM = 1_000_000
MARGIN = int(0.15 * MM)


def _box(item):
    b = item.GetBoundingBox()
    return (b.GetX(), b.GetY(), b.GetRight(), b.GetBottom())


def _inflate(box, d):
    return (box[0] - d, box[1] - d, box[2] + d, box[3] + d)


def _hits(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _obstacles(board, own):
    out = []
    for fp in board.GetFootprints():
        out += [_box(p) for p in fp.Pads()]
        if fp.GetReference() == own:
            continue
        out += [_box(g) for g in fp.GraphicalItems() if g.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS)]
        if fp.Reference().IsVisible():
            out.append(_box(fp.Reference()))
    return out


def _clear(label, obstacles, edge):
    box = _inflate(_box(label), MARGIN)
    inside = edge is None or (box[0] >= edge[0] and box[1] >= edge[1] and box[2] <= edge[2] and box[3] <= edge[3])
    return inside and not any(_hits(box, o) for o in obstacles)


def main(argv):
    path, wanted = argv[0], set(argv[1:])
    board = pcbnew.LoadBoard(path)
    e = board.GetBoardEdgesBoundingBox()
    edge = (e.GetX() + MARGIN, e.GetY() + MARGIN, e.GetRight() - MARGIN, e.GetBottom() - MARGIN) if e.GetWidth() else None
    moved, clear, no_room = {}, [], []
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        label = fp.Reference()
        if (wanted and ref not in wanted) or not label.IsVisible():
            continue
        obstacles = _obstacles(board, ref)
        if _clear(label, obstacles, edge):
            clear.append(ref)
            continue
        start, angle = label.GetPosition(), label.GetTextAngle()
        body = _box(fp)
        cx, cy = (body[0] + body[2]) // 2, (body[1] + body[3]) // 2
        found = None
        for turn in (0.0, 90.0):
            label.SetTextAngle(pcbnew.EDA_ANGLE(turn, pcbnew.DEGREES_T))
            lb = _box(label)
            hw, hh = (lb[2] - lb[0]) // 2, (lb[3] - lb[1]) // 2
            for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
                x = cx + dx * ((body[2] - body[0]) // 2 + hw + MARGIN)
                y = cy + dy * ((body[3] - body[1]) // 2 + hh + MARGIN)
                label.SetPosition(pcbnew.VECTOR2I(int(x), int(y)))
                if _clear(label, obstacles, edge):
                    found = (x / MM, y / MM, turn)
                    break
            if found:
                break
        if found:
            moved[ref] = {"x_mm": round(found[0], 3), "y_mm": round(found[1], 3), "angle": found[2]}
        else:
            label.SetPosition(start)
            label.SetTextAngle(angle)
            no_room.append(ref)
    if moved:
        board.Save(path)
    print(json.dumps({"moved": moved, "already_clear": len(clear), "no_room": no_room}))


if __name__ == "__main__":
    main(sys.argv[1:])
