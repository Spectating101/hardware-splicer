"""Independent directed-edge and signed-volume audit for triangulated STL solids.

The original HS device_case mesh_report algorithm is retained without pulling
in the discontinued device-case planning dependency. Coordinates are integer
hundredths of a millimetre, as required by the upstream printed casing script.
"""
from __future__ import annotations
from typing import Any


def mesh_report(triangles) -> dict[str, Any]:
    edges = {}
    volume6 = 0
    low = [None, None, None]
    high = [None, None, None]
    for tri in triangles:
        for index in range(3):
            a, b = tri[index], tri[(index + 1) % 3]
            edges[(a, b)] = edges.get((a, b), 0) + 1
        a, b, c = tri
        volume6 += a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0]) + a[2] * (b[0] * c[1] - b[1] * c[0])
        for vertex in tri:
            for axis in range(3):
                low[axis] = vertex[axis] if low[axis] is None else min(low[axis], vertex[axis])
                high[axis] = vertex[axis] if high[axis] is None else max(high[axis], vertex[axis])
    closed = bool(edges) and all(count == 1 and edges.get((b, a)) == 1 for (a, b), count in edges.items())
    return {
        "triangles": len(triangles),
        "closed_manifold": closed,
        "volume_mm3": round(volume6 / 6 / (100**3), 2),
        "size_mm": [round((high[i] - low[i]) / 100, 2) for i in range(3)] if triangles else [0, 0, 0],
    }
