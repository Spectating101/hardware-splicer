"""Read actual STEP solids and check cross-domain source revision effects."""
from __future__ import annotations
import json
import sys
from pathlib import Path
import cadquery as cq


def points(report):
    return {p["ref"]: (p["x"], p["y"]) for p in report["board_layout"]["points"]}


def check(original: Path, revised: Path) -> dict:
    a = json.loads((original / "geometry.json").read_text())
    b = json.loads((revised / "geometry.json").read_text())
    p, q = points(a), points(b)
    assert set(p) == set(q) and len(p) == 22
    assert a["contacts"] == b["contacts"] == 18
    assert a["distinct_nets"] == b["distinct_nets"] == 16
    assert a["board_sha256"] != b["board_sha256"]
    for k in p:
        if k == "TP12":
            assert p[k] == (60.0, 12.0) and q[k] == (61.0, 13.0)
        else:
            assert p[k] == q[k], (k, p[k], q[k])
    fixture_dir = Path(__file__).resolve().parents[1] / "bench-probe-fixture"
    sys.path.insert(0, str(fixture_dir))
    from build import exported_centres, PROBE_BORE
    old = set(exported_centres(original / "probe-guide.step", PROBE_BORE, 4))
    new = set(exported_centres(revised / "probe-guide.step", PROBE_BORE, 4))
    assert len(old) == len(new) == 18
    assert old - new == {(60, 12)}, old - new
    assert new - old == {(61, 13)}, new - old
    x = cq.importers.importStep(str(original / "board-carrier.step")).val()
    y = cq.importers.importStep(str(revised / "board-carrier.step")).val()
    difference = max(x.cut(y).Volume(), y.cut(x).Volume())
    assert difference <= 1e-8, difference
    return {
        "passed": True,
        "probe_bores_reopened": 18,
        "source_nets": 16,
        "moved": {"ref": "TP12", "original_xy_mm": [60, 12],
                  "new_xy_mm": [61, 13]},
        "other_source_locations_unchanged": 21,
        "carrier_symmetric_difference_mm3": difference,
        "physical_verification_performed": False,
    }


if __name__ == "__main__":
    first, second, out = map(Path, sys.argv[1:])
    result = check(first, second)
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
