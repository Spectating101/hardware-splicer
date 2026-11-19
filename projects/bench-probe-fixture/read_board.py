"""Extract millimetres from the target rectangular KiCad board using KiCad's Python."""

import json
import re
import sys
from collections import Counter

import pcbnew


def xy(point):
    return tuple(pcbnew.ToMM(value) for value in point)


def layout(path):
    board = pcbnew.LoadBoard(path)
    edges = [d for d in board.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts]
    ends = Counter(xy(point) for edge in edges for point in (edge.GetStart(), edge.GetEnd()))
    xs, ys = (sorted({point[i] for point in ends}) for i in (0, 1))
    if (len(edges) != 4 or len(xs) != 2 or len(ys) != 2 or set(ends.values()) != {2}
            or any(edge.GetShape() != pcbnew.SHAPE_T_SEGMENT or
                   (edge.GetStartX() != edge.GetEndX() and edge.GetStartY() != edge.GetEndY())
                   for edge in edges)):
        raise ValueError("This carrier supports a four-segment rectangular board outline")
    records = []
    for footprint in board.GetFootprints():
        ref = footprint.GetReference()
        if not re.fullmatch(r"(TP|H)\d+", ref):
            continue
        pad, = footprint.Pads()
        x, y = xy(pad.GetPosition())
        size_x, size_y = xy(pad.GetSize())
        if ref.startswith("TP"):
            if (pad.GetShape() != pcbnew.PAD_SHAPE_CIRCLE or size_x != size_y or
                    not (pad.IsOnLayer(pcbnew.F_Cu) and pad.IsOnLayer(pcbnew.F_Mask)) or
                    not pad.GetNetname()):
                raise ValueError(f"{ref} needs a round exposed front-side pad on a named net")
            diameter = size_x
        else:
            diameter, drill_y = xy(pad.GetDrillSize())
            if diameter != drill_y or diameter <= 0:
                raise ValueError(f"{ref} needs a round drill")
        records.append(dict(ref=ref, net=pad.GetNetname(), x=x-xs[0], y=ys[-1]-y,
                            diameter=diameter))
    return dict(width=xs[1]-xs[0], height=ys[1]-ys[0],
                points=sorted(records, key=lambda p: (p["ref"][0], int(re.search(r"\d+", p["ref"])[0]))))


if __name__ == "__main__":
    print(json.dumps(layout(sys.argv[1])))
