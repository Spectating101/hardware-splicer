"""Find hardware data worth absorbing by GitHub's own signals, instead of a hand-picked list.

It runs a fixed set of GitHub repository searches (pinouts, board definitions, component and footprint libraries, device
configurations, breakout board files, part databases, simulator parts), scores every repository found on public signals,
and writes the top ones as a pinned ``hardware_splicer.github_signal_feed.v1`` feed that ``github_signal_pipeline`` admits as
discovered-only. Scoring:

* reach: log of stars, so a 50,000-star repository does not drown everything else;
* activity: pushed within the last 6 or 18 months;
* licence: whether HS may absorb the data (MIT, Apache, BSD, ISC, CC0, Unlicense), may only review it in place (GPL, LGPL,
  AGPL, EPL, MPL, CC-BY, CC-BY-SA), or neither (no licence: all rights reserved);
* breadth: how many of the searches found it.

Stars and pushes are popularity and activity, not quality or correctness; the feed decides what to look at, never what is
true. Searching needs an authenticated ``gh``; the scoring and feed are pure functions and are tested without the network.

    PYTHONPATH=src python -m hardware_splicer.github_data_sources out/feed.json [--per-query 30] [--top 100]
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

FEED_SCHEMA = "hardware_splicer.github_signal_feed.v1"
REPORT_SCHEMA = "hardware_splicer.github_data_source_sweep.v1"
QUERIES = {
    "pinouts": ["esp32 pinout", "microcontroller pinout reference", "rp2040 pinout"],
    "board_definitions": ["platformio boards", "arduino board definitions variants", "esp32 board definitions"],
    "component_libraries": ["electronic component library json", "kicad library", "kicad symbols footprints", "fritzing parts"],
    "device_configurations": ["esphome devices", "tasmota templates", "esphome configs collection"],
    "breakout_board_files": ["breakout board eagle pcb", "open source hardware pcb sensor breakout", "qwiic stemma pcb"],
    "part_databases": ["electronic parts database", "i2c address list", "sensor database datasheet"],
    "simulator_parts": ["wokwi", "circuit simulator parts library", "breadboard simulator components"],
    "example_projects": ["esp32 projects collection", "arduino projects wiring diagrams", "home assistant diy sensors"],
}
# CC-BY (without SA or NC) only asks for attribution, so its data can be absorbed with the licence and credit kept beside it.
ABSORB = {"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "CC0-1.0", "Unlicense", "0BSD", "Zlib", "BSL-1.0", "CC-BY-4.0", "CC-BY-3.0"}
REVIEW_ONLY_PREFIXES = ("GPL", "LGPL", "AGPL", "EPL", "MPL", "CC-BY", "CERN-OHL", "OFL")


def licence_class(spdx: str | None) -> str:
    if spdx in ABSORB:
        return "absorb"
    if spdx and spdx.startswith(REVIEW_ONLY_PREFIXES):
        return "review_only"
    return "unusable" if spdx in (None, "", "NOASSERTION", "NONE") else "review_only"


def score(repo: dict[str, Any], hits: int, now: datetime) -> float:
    stars = repo.get("stargazers_count") or 0
    pushed = repo.get("pushed_at")
    months = (now - datetime.fromisoformat(pushed.replace("Z", "+00:00"))).days / 30.4 if pushed else 999
    activity = 1.0 if months <= 6 else 0.6 if months <= 18 else 0.2
    licence = {"absorb": 1.0, "review_only": 0.5, "unusable": 0.0}[licence_class((repo.get("license") or {}).get("spdx_id"))]
    archived = 0.3 if repo.get("archived") else 1.0
    if licence == 0.0:
        return 0.0  # no licence: all rights reserved, so nothing to absorb or run
    return round(math.log10(stars + 1) * activity * (0.5 + licence) * archived * (1 + 0.25 * (hits - 1)), 3)


def rank(found: dict[str, dict[str, Any]], *, now: datetime) -> list[dict[str, Any]]:
    """``found`` maps full_name to {"repo": search item, "categories": set, "queries": set}."""
    rows = []
    for name, entry in found.items():
        repo = entry["repo"]
        spdx = (repo.get("license") or {}).get("spdx_id")
        rows.append({"repository": name, "score": score(repo, len(entry["queries"]), now), "stars": repo.get("stargazers_count", 0),
                     "pushed_at": repo.get("pushed_at"), "license_spdx_id": spdx or "NONE", "licence_class": licence_class(spdx),
                     "archived": bool(repo.get("archived")), "categories": sorted(entry["categories"]), "queries": sorted(entry["queries"]),
                     "description": (repo.get("description") or "")[:200], "default_branch": repo.get("default_branch")})
    rows.sort(key=lambda r: (-r["score"], r["repository"].lower()))
    return rows


def _gh(args: list[str]) -> Any:
    run = subprocess.run(["gh", "api", *args], capture_output=True, text=True, timeout=60, check=False)
    if run.returncode != 0:
        raise RuntimeError(run.stderr.strip()[:300])
    return json.loads(run.stdout)


def search(per_query: int = 30, fetch: Callable[[list[str]], Any] = _gh) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for category, queries in QUERIES.items():
        for query in queries:
            data = fetch(["-X", "GET", "search/repositories", "-f", f"q={query}", "-f", "sort=stars", "-f", f"per_page={per_query}"])
            for item in data.get("items", []):
                entry = found.setdefault(item["full_name"], {"repo": item, "categories": set(), "queries": set()})
                entry["categories"].add(category)
                entry["queries"].add(query)
    return found


def feed(rows: list[dict[str, Any]], pins: dict[str, str], *, top: int = 100) -> dict[str, Any]:
    """The pipeline's feed: usable licences only, pinned to the commit each repository's default branch had when swept."""
    from .github_signal_pipeline import ID_PATTERN

    # The pipeline's own name rule (it refuses names such as dotfile repositories), applied before anything is written.
    chosen = [r for r in rows if r["licence_class"] != "unusable" and r["repository"] in pins and ID_PATTERN.fullmatch(r["repository"])][:top]
    return {"schema_version": FEED_SCHEMA, "source": "github_repository_search",
            "candidates": [{"repository": r["repository"], "commit_sha": pins[r["repository"]], "license_spdx_id": r["license_spdx_id"],
                            "intended_use": "absorb_data" if r["licence_class"] == "absorb" else "review_in_place",
                            "research_role": r["categories"][0]} for r in chosen]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out", type=Path)
    ap.add_argument("--per-query", type=int, default=30)
    ap.add_argument("--top", type=int, default=100)
    args = ap.parse_args(argv)
    now = datetime.now(timezone.utc)
    rows = rank(search(args.per_query), now=now)
    pins = {}
    for row in [r for r in rows if r["licence_class"] != "unusable"][: args.top]:
        try:
            sha = _gh([f"repos/{row['repository']}/commits/{row['default_branch']}"])["sha"]
        except (RuntimeError, KeyError, ValueError, subprocess.SubprocessError, OSError):
            continue
        pins[row["repository"]] = sha
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(feed(rows, pins, top=args.top), indent=1) + "\n", encoding="utf-8")
    report = args.out.with_name(args.out.stem + "_ranking.json")
    report.write_text(json.dumps({"schema_version": REPORT_SCHEMA, "swept_at": now.isoformat(), "queries": QUERIES,
                                  "repositories_found": len(rows), "ranking": rows,
                                  "note": "Stars and pushes are popularity and activity, not quality or correctness."}, indent=1) + "\n",
                      encoding="utf-8")
    print(json.dumps({"found": len(rows), "feed": len(pins), "ranking": str(report)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
