"""Route a placed KiCad board with Copper (copper-kicad-mcp, MIT), run as a separate program in KiCad 10's container.

On HS-BUS-A's placement (2026-11-27) HS's own FreeRouting step finished 2 of 5 runs (each failure left one connection);
Copper finished 5 of 5 with 0 DRC errors, because its guided router completes what Freerouting leaves. Copper edits
boards through KiCad 10's pcbnew, so it runs in the official ``kicad/kicad:10.0.x`` image with no network; the routed
board comes back in KiCad 10's format next to the original, which is never touched.

Configuration (all paths on this machine):

* ``HARDWARE_SPLICER_COPPER_SRC``: a checkout of github.com/claynicholson/copper-kicad-mcp, its ``src`` folder;
* ``HARDWARE_SPLICER_COPPER_JAVA``: a Java 25 runtime's ``bin/java`` (Freerouting 2.2.3 needs class file 69);
* ``HARDWARE_SPLICER_COPPER_FREEROUTING_JAR``: freerouting-2.2.3.jar;
* ``HARDWARE_SPLICER_KICAD10_IMAGE``: the container image, default ``kicad/kicad:10.0.8``.

    PYTHONPATH=src python -m hardware_splicer.copper_route board.kicad_pcb OUT_DIR [--ignore-net /GND]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

SCHEMA = "hardware_splicer.copper_route.v1"
BOUNDARY = ("Routing by an outside tool (Copper, MIT) with KiCad 10's own DRC afterwards. A routed board is a layout to review, "
            "not a fabrication approval: impedance, current capacity and placement quality are not judged here.")
DRIVER = r'''
import json, sys, time
sys.path.insert(0, sys.argv[1])
from copper_kicad.tools import pcb_tools
t0 = time.time()
try:
    r = pcb_tools.pcb_route(project=sys.argv[2], render=False, timeout=900, ignore_nets=json.loads(sys.argv[3]) or None)
    out = {"route": r.data if hasattr(r, "data") else r}
    pour = sys.argv[4] if len(sys.argv) > 4 else ""
    if pour:   # Copper's 2-layer flow: the ground net is left to a pour on both layers, stitched
        p = pcb_tools.pcb_pour(project=sys.argv[2], net=pour, layers=["F.Cu", "B.Cu"], stitch=True, render=False)
        out["pour"] = p.data if hasattr(p, "data") else p
except Exception as exc:
    out = {"error": f"{type(exc).__name__}: {exc}"[:800]}
out["seconds"] = round(time.time() - t0, 1)
print("COPPER_RESULT " + json.dumps(out, default=str))
'''


class CopperRouteError(RuntimeError):
    pass


def config() -> dict[str, str]:
    cfg = {"src": os.environ.get("HARDWARE_SPLICER_COPPER_SRC", ""), "java": os.environ.get("HARDWARE_SPLICER_COPPER_JAVA", ""),
           "jar": os.environ.get("HARDWARE_SPLICER_COPPER_FREEROUTING_JAR", ""),
           "image": os.environ.get("HARDWARE_SPLICER_KICAD10_IMAGE", "kicad/kicad:10.0.8")}
    missing = [f"HARDWARE_SPLICER_COPPER_{k.upper() if k != 'jar' else 'FREEROUTING_JAR'}" for k in ("src", "java", "jar")
               if not cfg[k] or not Path(cfg[k]).exists()]
    if missing:
        raise CopperRouteError("Copper is not configured: set " + ", ".join(missing) + " (see hardware_splicer.copper_route)")
    if not shutil.which("docker"):
        raise CopperRouteError("docker is needed to run KiCad 10's container")
    return cfg


def route_with_copper(pcb: Path, out_dir: Path, *, ignore_nets: list[str] | None = None, pour_net: str | None = None,
                      timeout_s: int = 1200) -> dict[str, Any]:
    """Route ``pcb`` (copied, never touched); with ``pour_net`` that net is also poured, stitched, on both layers."""
    pcb = Path(pcb).resolve()
    if not pcb.is_file() or pcb.suffix != ".kicad_pcb":
        raise CopperRouteError(f"not a KiCad board: {pcb}")
    cfg = config()
    out_dir = Path(out_dir).resolve()
    project = out_dir / "copper_project"
    if project.exists():
        shutil.rmtree(project)
    project.mkdir(parents=True)
    stem = "board"
    shutil.copy(pcb, project / f"{stem}.kicad_pcb")
    for suffix in (".kicad_pro", ".kicad_sch"):
        if pcb.with_suffix(suffix).is_file():
            shutil.copy(pcb.with_suffix(suffix), project / f"{stem}{suffix}")
    if not (project / f"{stem}.kicad_pro").exists():
        (project / f"{stem}.kicad_pro").write_text("{}\n")
    for table in ("fp-lib-table", "sym-lib-table"):
        if (pcb.parent / table).is_file():
            shutil.copy(pcb.parent / table, project / table)
    (out_dir / "copper_driver.py").write_text(DRIVER)
    mounts = {str(out_dir), str(Path(cfg["src"]).resolve()), str(Path(cfg["java"]).resolve().parents[1]), str(Path(cfg["jar"]).resolve().parent)}
    base = ["docker", "run", "--rm", "--network", "none", "--user", f"{os.getuid()}:{os.getgid()}", "-e", "HOME=/tmp",
            "-e", "COPPER_HOME=/tmp/copper", "-e", f"COPPER_JAVA={Path(cfg['java']).resolve()}",
            "-e", f"COPPER_FREEROUTING_JAR={Path(cfg['jar']).resolve()}", "-e", "COPPER_NO_UPDATE_CHECK=1"]
    for m in sorted(mounts):
        base += ["-v", f"{m}:{m}"]
    base += ["-w", str(project), cfg["image"]]
    up = subprocess.run(base + ["kicad-cli", "pcb", "upgrade", str(project / f"{stem}.kicad_pcb")], capture_output=True, text=True, timeout=300)
    if up.returncode != 0:
        raise CopperRouteError(f"KiCad 10 could not upgrade the board: {(up.stderr or up.stdout).strip()[-300:]}")
    # Every net is routed, the pour net included, and the pour goes on top: on HS-BUS-A, leaving ground to the pour alone
    # (Copper's documented 2-layer flow) left one ground fragment unconnected, while routing it first came back clean.
    ignore = list(ignore_nets or [])
    run = subprocess.run(base + ["python3", str(out_dir / "copper_driver.py"), str(Path(cfg["src"]).resolve()),
                                 str(project / f"{stem}.kicad_pro"), json.dumps(ignore), pour_net or ""],
                         capture_output=True, text=True, timeout=timeout_s)
    line = next((ln for ln in run.stdout.splitlines() if ln.startswith("COPPER_RESULT ")), None)
    if line is None:
        raise CopperRouteError(f"Copper did not report (exit {run.returncode}): {(run.stderr or run.stdout).strip()[-400:]}")
    raw = json.loads(line[len("COPPER_RESULT "):])
    if raw.get("error"):
        raise CopperRouteError(raw["error"])
    r = raw["route"]
    drc = (r.get("verify") or {}).get("drc") or {}
    if raw.get("pour"):
        drc = ((raw["pour"].get("verify") or {}).get("drc")) or drc
    routed = project / f"{stem}.kicad_pcb"
    result = {"schema_version": SCHEMA, "claim_boundary": BOUNDARY, "router": r.get("router"), "source_board": str(pcb),
              "routed_board": str(routed), "kicad_format": "KiCad 10", "unrouted_before": r.get("unrouted_before"),
              "unrouted_after": r.get("unrouted_after"), "drc_errors": drc.get("errors"), "drc_unconnected": drc.get("unconnected"),
              "drc_warnings": drc.get("warnings"), "vias_added": r.get("vias_added"), "track_length_mm": r.get("track_length_mm"),
              "seconds": raw.get("seconds"), "rounds": r.get("rounds"), "elegance": r.get("elegance"),
              "poured": {"net": pour_net, **{k: v for k, v in (raw.get("pour") or {}).items() if k in ("zones", "stitch", "stitched", "changed")}}
                        if pour_net else None,
              "complete": r.get("unrouted_after") == 0 and drc.get("errors") == 0 and drc.get("unconnected") == 0}
    (out_dir / "copper_route.json").write_text(json.dumps(result, indent=1, default=str))
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("pcb", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--ignore-net", action="append", default=[])
    a = ap.parse_args(argv)
    try:
        res = route_with_copper(a.pcb, a.out, ignore_nets=a.ignore_net)
    except CopperRouteError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps({k: v for k, v in res.items() if k not in ("rounds", "elegance")}, indent=1, default=str))
    return 0 if res["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
