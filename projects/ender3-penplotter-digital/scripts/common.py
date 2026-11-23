"""GPL-3.0-only. Digital study utilities, authored 2026-11-17."""
from pathlib import Path
import hashlib
import json
import math

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = {"drawing_width_mm": 100.0, "drawing_height_mm": 80.0,
            "pen_diameter_mm": 10.0, "pen_lift_mm": 3.0}
BOUNDS = {"drawing_width_mm": (60., 140.), "drawing_height_mm": (40., 140.),
          "pen_diameter_mm": (8., 12.), "pen_lift_mm": (2., 5.)}


def read_requirements():
    req = json.loads((ROOT / "requirements.json").read_text())
    if set(req) != set(DEFAULTS):
        raise ValueError("Requirement keys must be exactly " + str(sorted(DEFAULTS)))
    for key, (lo, hi) in BOUNDS.items():
        value = req[key]
        if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
            raise ValueError("Finite numeric requirement required: " + key)
        if not lo <= value <= hi:
            raise ValueError(f"{key} outside {lo}..{hi}")
    return req


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def constraint(ident, actual, limit, passed, unit, basis):
    return dict(id=ident, passed=bool(passed), actual=float(actual), limit=float(limit),
                unit=unit, basis=basis)
