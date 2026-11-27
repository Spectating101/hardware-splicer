"""Call one HS function inside the native interpreter (CadQuery, Gmsh, PyBullet) and print its JSON result.

    echo '{"path": "part.step", ...}' | python -m hardware_splicer.native_call hardware_splicer.mechanical_cad_fem run_cad_screening [--out result.json]

The engine toolbelt runs in the ordinary interpreter; functions that need the native CAD and physics libraries run here,
in the interpreter named by HARDWARE_SPLICER_DIGITAL_PYTHON. Any HS function that takes JSON-able keyword arguments and
returns JSON-able data becomes callable this way, with no command-line wrapper of its own. Only HS modules may be called.
Native libraries (PyBullet, Gmsh) print to stdout from C, so a caller should pass ``--out`` and read the file.
"""
from __future__ import annotations

import importlib
import json
import math
import sys
from typing import Any


def _clean(value: Any) -> Any:
    """JSON has no NaN or infinity: say so as text instead of emitting invalid JSON."""
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    if hasattr(value, "model_dump"):
        return _clean(value.model_dump(mode="json"))
    return value


def call(module: str, function: str, kwargs: dict[str, Any]) -> Any:
    if module != "hardware_splicer" and not module.startswith("hardware_splicer."):
        raise ValueError("only hardware_splicer modules can be called")
    return getattr(importlib.import_module(module), function)(**kwargs)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    out, wants_out = None, "--out" in argv
    if wants_out:
        i = argv.index("--out")
        out = argv[i + 1] if i + 1 < len(argv) else None
        argv = argv[:i] + argv[i + 2:]
    if len(argv) != 2 or (wants_out and not out):
        print("usage: python -m hardware_splicer.native_call MODULE FUNCTION [--out FILE] < kwargs.json", file=sys.stderr)
        return 2
    kwargs = json.loads(sys.stdin.read() or "{}")
    text = json.dumps(_clean(call(argv[0], argv[1], kwargs)), allow_nan=False, default=str)
    if out:
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(text)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
