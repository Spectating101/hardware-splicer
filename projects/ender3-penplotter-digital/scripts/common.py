"""GPL-3.0-only. Digital study utilities, authored 2026-11-17."""
from pathlib import Path
import hashlib
import json
import math

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = {"drawing_width_mm": 100.0, "drawing_height_mm": 80.0,
            "pen_diameter_mm": 10.0, "pen_lift_mm": 3.0,
            "paper_width_mm": 180.0, "paper_height_mm": 180.0}
BOUNDS = {"drawing_width_mm": (60., 190.), "drawing_height_mm": (40., 140.),
          "pen_diameter_mm": (8., 12.), "pen_lift_mm": (2., 5.),
          "paper_width_mm": (100., 220.), "paper_height_mm": (100., 220.)}
LEGACY_KEYS = frozenset(DEFAULTS) - {"paper_width_mm", "paper_height_mm"}


def validate_requirements(values, *, tool_offset_xy_mm=(0., -19.2)):
    # Four-key historical inputs retain their 180 mm square paper model.
    if not isinstance(values, dict) or not LEGACY_KEYS <= set(values) or set(values) - set(DEFAULTS):
        raise ValueError("Required drawing/pen keys and optional paper dimensions expected.")
    req = {**DEFAULTS, **values}
    for key, (lo, hi) in BOUNDS.items():
        value = req[key]
        try:
            valid = not isinstance(value, bool) and isinstance(value, (float, int)) and math.isfinite(value)
        except OverflowError:
            valid = False
        if not valid:
            raise ValueError("Finite numeric requirement required: " + key)
        if not lo <= value <= hi:
            raise ValueError(f"{key} outside {lo}..{hi}")
        req[key] = float(value)
    for axis in ("width", "height"):
        if req[f"drawing_{axis}_mm"] + 20 > req[f"paper_{axis}_mm"]:
            raise ValueError("The drawing viewport needs at least 10 mm of paper on each side.")
    if len(tool_offset_xy_mm) != 2 or not all(math.isfinite(v) for v in tool_offset_xy_mm):
        raise ValueError("A finite source tool offset is required.")
    for size, offset in zip((req["drawing_width_mm"], req["drawing_height_mm"]), tool_offset_xy_mm):
        if 117.5 - size / 2 - offset < 0 or 117.5 + size / 2 - offset > 235:
            raise ValueError("The full drawing viewport exceeds the source controller travel after tool compensation.")
    return req


def read_requirements():
    values = json.loads((ROOT / "requirements.json").read_text())
    interface = json.loads((ROOT / "sources/interface.json").read_text())
    return validate_requirements(values, tool_offset_xy_mm=interface["pen_offset_from_nozzle_xy_mm"])


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def constraint(ident, actual, limit, passed, unit, basis):
    return dict(id=ident, passed=bool(passed), actual=float(actual), limit=float(limit),
                unit=unit, basis=basis)
