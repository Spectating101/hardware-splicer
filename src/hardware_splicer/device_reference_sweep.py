"""Open-source whole-device designs by category, found by GitHub's own signals and checked for what they really contain.

    PYTHONPATH=src python -m hardware_splicer.device_reference_sweep examples/device_references/sweep.json [--per-query 20] [--probe 12]

A robot vacuum, a mower, a drone, an ROV, an arm: for each category a fixed set of repository searches is run, every
repository is scored with ``github_data_sources.score`` (reach, activity, licence), and the best of each category are
probed through the git tree API for the files a whole device needs:

* ``cad``: STEP, STL, 3MF, Fusion, FreeCAD, OpenSCAD, SolidWorks, IGES, DXF
* ``pcb``: KiCad, Eagle, Altium, EasyEDA files or Gerbers
* ``firmware``: PlatformIO, Arduino sketches, ESP-IDF/Zephyr/CMake sources, ROS packages
* ``bom``: a bill of materials file
* ``assembly``: build, assembly or instructions documents
* ``sim``: URDF, Xacro, SDF or MJCF robot models

``completeness`` counts the first five. A repository with all five is an open design HS can measure its own device designs
against, subsystem by subsystem; one with only firmware is a software project. Stars and pushes say what is popular, not
what works; files present say a design was published, not that it was built.
"""
from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .github_data_sources import _gh, licence_class, score

SCHEMA = "hardware_splicer.device_reference_sweep.v1"
CATEGORIES: dict[str, list[str]] = {
    "robot_vacuum": ["robot vacuum open source hardware", "diy robot vacuum cleaner", "robot vacuum ros lidar"],
    "mopping_floor_robot": ["mopping robot", "floor cleaning robot open source"],
    "window_pool_cleaner": ["window cleaning robot", "pool cleaning robot open source"],
    "lawn_mower": ["robotic lawn mower open source", "autonomous lawn mower rtk"],
    "multirotor_drone": ["open source quadcopter", "diy drone flight controller pcb", "fpv drone frame open source"],
    "fixed_wing_vtol": ["open source fixed wing uav", "vtol drone open source"],
    "underwater_rov": ["open source rov underwater", "diy submarine robot", "auv open source"],
    "surface_vessel": ["autonomous boat open source", "unmanned surface vehicle open source"],
    "ground_rover": ["open source rover robot", "mars rover replica open source", "ros2 robot car diy"],
    "camera_security_robot": ["security patrol robot open source", "esp32 cam robot car", "telepresence robot open source"],
    "robot_arm": ["open source robot arm", "3d printed robot arm", "low cost robot arm lerobot"],
    "quadruped": ["open source quadruped robot", "robot dog diy open source"],
    "humanoid_biped": ["open source humanoid robot", "bipedal robot open source"],
    "balance_desktop_robot": ["self balancing robot open source", "desktop robot open source"],
    "robotic_hand_gripper": ["robotic hand open source", "robot gripper open source"],
    "delivery_agv": ["delivery robot open source", "agv open source hardware"],
    "machine_3dprinter_cnc": ["open source 3d printer", "diy cnc machine open source"],
}
FILE_RULES: dict[str, re.Pattern[str]] = {
    "cad": re.compile(r"\.(step|stp|stl|3mf|f3d|f3z|fcstd|scad|sldprt|sldasm|iges|igs|dxf)$", re.I),
    "pcb": re.compile(r"\.(kicad_pcb|kicad_sch|brd|pcbdoc|schdoc|gbr|gtl|gbl)$|easyeda|gerber", re.I),
    "firmware": re.compile(r"(^|/)(platformio\.ini|package\.xml|sdkconfig|prj\.conf)$|\.ino$|(^|/)(firmware|src)/.*\.(c|cpp|h|hpp|rs)$", re.I),
    "bom": re.compile(r"(^|/|_|-)bom[^/]*\.(csv|xlsx|xls|md|ods|tsv|json|html)$|bill[_ -]?of[_ -]?materials", re.I),
    "assembly": re.compile(r"(assembly|build[_ -]?guide|instructions|how[_ -]?to[_ -]?build)[^/]*\.(md|pdf|html|txt)$|(^|/)(assembly|build_guide)/", re.I),
    "sim": re.compile(r"\.(urdf|xacro|sdf|mjcf)$", re.I),
}
DESIGN_PARTS = ("cad", "pcb", "firmware", "bom", "assembly")


def classify_files(paths: list[str]) -> dict[str, int]:
    """How many files of each design kind a repository tree holds."""
    counts = {k: 0 for k in FILE_RULES}
    for path in paths:
        for kind, rx in FILE_RULES.items():
            if rx.search(path):
                counts[kind] += 1
    return counts


def completeness(counts: dict[str, int]) -> int:
    return sum(1 for k in DESIGN_PARTS if counts.get(k))


def search_categories(per_query: int, fetch: Callable[[list[str]], Any] = _gh, pause_s: float = 2.5) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for category, queries in CATEGORIES.items():
        for query in queries:
            data = fetch(["-X", "GET", "search/repositories", "-f", f"q={query}", "-f", "sort=stars", "-f", f"per_page={per_query}"])
            for item in data.get("items", []):
                entry = found.setdefault(item["full_name"], {"repo": item, "categories": set(), "queries": set()})
                entry["categories"].add(category)
                entry["queries"].add(query)
            if pause_s:
                time.sleep(pause_s)  # GitHub's search API allows 30 requests a minute
    return found


def probe(full_name: str, branch: str, fetch: Callable[[list[str]], Any] = _gh) -> dict[str, Any]:
    tree = fetch(["-X", "GET", f"repos/{full_name}/git/trees/{branch}", "-f", "recursive=1"])
    paths = [t["path"] for t in tree.get("tree", []) if t.get("type") == "blob"]
    counts = classify_files(paths)
    return {"files": len(paths), "truncated": bool(tree.get("truncated")), "counts": counts, "completeness": completeness(counts),
            "tree_sha": tree.get("sha")}


def build(found: dict[str, dict[str, Any]], *, probe_top: int, now: datetime,
          fetch: Callable[[list[str]], Any] = _gh) -> dict[str, Any]:
    by_category: dict[str, list[dict[str, Any]]] = {c: [] for c in CATEGORIES}
    rows: dict[str, dict[str, Any]] = {}
    for name, entry in found.items():
        repo = entry["repo"]
        spdx = (repo.get("license") or {}).get("spdx_id")
        row = {"repo": name, "url": repo.get("html_url"), "stars": repo.get("stargazers_count"), "pushed": repo.get("pushed_at"),
               "licence": spdx, "licence_class": licence_class(spdx), "archived": bool(repo.get("archived")),
               "default_branch": repo.get("default_branch") or "main", "description": (repo.get("description") or "")[:200],
               "categories": sorted(entry["categories"]), "score": score(repo, len(entry["queries"]), now)}
        rows[name] = row
        for c in entry["categories"]:
            by_category[c].append(row)
    probed: set[str] = set()
    for c, members in by_category.items():
        members.sort(key=lambda r: (-r["score"], r["repo"]))
        for row in members[:probe_top]:
            if row["repo"] in probed:
                continue
            probed.add(row["repo"])
            try:
                row["design"] = probe(row["repo"], row["default_branch"], fetch)
            except Exception as exc:  # noqa: BLE001 - one unreadable tree must not stop the sweep
                row["design"] = {"error": str(exc)[:200]}
    summary = {}
    for c, members in by_category.items():
        designs = [r for r in members if isinstance(r.get("design"), dict) and "completeness" in r["design"]]
        full = [r for r in designs if r["design"]["completeness"] >= 4 and r["licence_class"] != "unusable"]
        summary[c] = {"found": len(members), "probed": len(designs), "open_designs": len(full),
                      "best": [r["repo"] for r in sorted(full, key=lambda r: (-r["design"]["completeness"], -r["score"]))[:5]]}
    return {"schema": SCHEMA, "captured": now.isoformat(timespec="seconds"), "queries": CATEGORIES,
            "method": "GitHub repository search sorted by stars; score = github_data_sources.score; the top of each category "
                      "probed with the recursive git tree API; completeness counts cad, pcb, firmware, bom and assembly files",
            "limits": "Files present show a published design, not a built or working one. No licence means all rights reserved: "
                      "such repositories are listed but never absorbed.",
            "summary": summary, "repos": sorted(rows.values(), key=lambda r: (-r["score"], r["repo"]))}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("out", type=Path)
    ap.add_argument("--per-query", type=int, default=20)
    ap.add_argument("--probe", type=int, default=12, help="repositories probed per category")
    a = ap.parse_args(argv)
    now = datetime.now(timezone.utc)
    report = build(search_categories(a.per_query), probe_top=a.probe, now=now)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    for c, s in report["summary"].items():
        print(f"{c:24s} found {s['found']:3d}  probed {s['probed']:3d}  open designs {s['open_designs']:3d}  {', '.join(s['best'][:3])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
