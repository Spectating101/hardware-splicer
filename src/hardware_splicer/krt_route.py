"""Route a placed KiCad board with KiCadRoutingTools (drandyhaas/KiCadRoutingTools, MIT), run as a separate program.

On three open 2-layer boards stripped to their designers' placements (2026-11-28, KiCad 10 DRC with zones refilled) it
finished all three: SNAP clean, IP5328P with every connection made, PiUPS adding one short and one clearance error, where
Copper left two connections on IP5328P and added 7 shorts and 30 mask bridges on PiUPS. On HS-BUS-A it routed clean in
17-49 s. Its whole-board ``autoroute.py`` caps every net class at its own fab tier and power nets at 0.3 mm, so a 5 A rail
came out 0.3 mm wide; HS therefore calls its ``route.py`` with the board's net-class widths passed explicitly as power-net
widths, which gave HS-BUS-A's 2.5 mm and 1.2 mm tracks. The board stays in its own KiCad format.

Configuration: ``HARDWARE_SPLICER_KRT_SRC`` (a checkout, with ``build_router.py`` run once) and
``HARDWARE_SPLICER_KRT_PYTHON`` (an interpreter with its requirements.txt).

    PYTHONPATH=src python -m hardware_splicer.krt_route placed.kicad_pcb routed.kicad_pcb [--width '*VIN*=2.5' ...]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

SCHEMA = "hardware_splicer.krt_route.v1"
BOUNDARY = ("Routing by an outside tool (KiCadRoutingTools, MIT). The routed board is a layout to review: HS's own DRC with "
            "schematic parity and its track-current check judge it, not the router's report.")


class KrtRouteError(RuntimeError):
    pass


def config() -> dict[str, str]:
    src, py = os.environ.get("HARDWARE_SPLICER_KRT_SRC", ""), os.environ.get("HARDWARE_SPLICER_KRT_PYTHON", "")
    if not src or not (Path(src) / "py_router" / "route.py").is_file():
        raise KrtRouteError("KiCadRoutingTools is not configured: set HARDWARE_SPLICER_KRT_SRC to a checkout (see hardware_splicer.krt_route)")
    if not py or not Path(py).is_file():
        raise KrtRouteError("set HARDWARE_SPLICER_KRT_PYTHON to an interpreter with KiCadRoutingTools' requirements")
    return {"src": src, "python": py}


def route_with_krt(pcb: Path, out_pcb: Path, *, power_widths: dict[str, float] | None = None, rules: dict[str, float] | None = None,
                   layers: tuple[str, ...] = ("F.Cu", "B.Cu"), timeout_s: int = 1800) -> dict[str, Any]:
    cfg = config()
    pcb, out_pcb = Path(pcb).resolve(), Path(out_pcb).resolve()
    if pcb.suffix != ".kicad_pcb" or not pcb.is_file():
        raise KrtRouteError(f"not a KiCad board: {pcb}")
    cmd = [cfg["python"], "py_router/route.py", str(pcb), str(out_pcb), "--nets", "*", "--layers", *layers]
    rules = rules or {}
    for key, flag in (("track", "--track-width"), ("clearance", "--clearance"), ("via_d", "--via-size"), ("via_drill", "--via-drill")):
        if rules.get(key):
            cmd += [flag, str(rules[key])]
    widths = {p: w for p, w in (power_widths or {}).items() if w}
    if widths:
        cmd += ["--power-nets", *widths, "--power-nets-widths", *(str(w) for w in widths.values())]
    start = time.time()
    run = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s, cwd=cfg["src"], check=False)
    tail = (run.stdout or run.stderr).strip().splitlines()[-6:]
    if run.returncode != 0 or not out_pcb.is_file():
        raise KrtRouteError(f"KiCadRoutingTools failed (exit {run.returncode}): {' | '.join(tail)[-400:]}")
    return {"schema_version": SCHEMA, "claim_boundary": BOUNDARY, "router": "KiCadRoutingTools route.py", "complete": True,
            "routed_board": str(out_pcb), "power_widths_mm": widths, "seconds": round(time.time() - start, 1), "log_tail": tail}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("pcb", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--width", action="append", default=[], help="NET_PATTERN=mm, e.g. '*VIN_12V=2.5'")
    a = ap.parse_args(argv)
    widths = {k: float(v) for k, _, v in (w.partition("=") for w in a.width)}
    try:
        print(json.dumps(route_with_krt(a.pcb, a.out, power_widths=widths), indent=1))
    except KrtRouteError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
