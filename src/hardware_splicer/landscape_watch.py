"""Weekly watch of the hardware-AI and open-hardware landscape, so new tools, sites and projects are known, not stumbled on.

    python -m hardware_splicer.landscape_watch [--days 8] [--state DIR]

Free sources only, no keys, no paid APIs: Hacker News search (Algolia API), GitHub repository search (gh CLI), RSS feeds
(Hackaday, Hackster.io, The Robot Report, TechniaHQRobot, Product Hunt), and Cite-Refinery's atlas of mapped open-source
products, read from its local working data (``HS_ATLAS_DIR``, default ~/.local/share/atlas-discovery). CNX Software and Reddit refuse automated readers
and are not worked around. Items are matched against topic keywords, deduplicated against a running register, and the new ones
written to a dated digest. Fetched text is treated as untrusted data: only titles, links, dates and short summaries are
kept, nothing is executed or followed further.

State (outside the repository, kept between runs): register.json (every item ever seen, first-seen date) and
digests/YYYY-MM-DD.md (what was new that week). Default directory ~/.local/share/hs-landscape.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

UA = {"User-Agent": "hardware-splicer-landscape-watch/1.0 (weekly, low volume)"}
TOPICS = {
    "ai_hardware_design": r"\b(ai|llm|agent|copilot|gpt|claude|gemini)\b.{0,60}\b(pcb|circuit|schematic|kicad|cad|hardware|electronics|firmware)\b|\b(pcb|kicad|schematic|cad)\b.{0,60}\b(ai|llm|agent)\b",
    "open_hardware_hub": r"open[- ]source hardware|open hardware|board (library|repository|registry)|kicad project|boardrepo|kitspace",
    "robot_arm": r"robot(ic)? arm|manipulator|so-?arm|lerobot|dynamixel|feetech",
    "mobile_robot": r"\brover\b|mobile robot|inspection robot|patrol robot|robot (car|chassis)",
    "drone": r"\b(drone|quadcopter|multirotor|fpv|betaflight|inav|px4|ardupilot)\b",
    "eda_tooling": r"\bkicad\b|freerouting|autorout|\bskidl\b|atopile|tscircuit|\bmcp\b.{0,40}(kicad|cad|freecad|pcb)",
    "cad_tooling": r"text[- ]to[- ]cad|cadquery|build123d|freecad|openscad|parametric cad",
    "physical_ai": r"physical ai|embodied ai|humanoid",
    "embedded_device": r"\besp32\b|\besp8266\b|\brp2040\b|\brp2350\b|raspberry pi|\bpico\b|microcontroller|\bm5stack\b",
    "other_robot": r"quadruped|walking robot|legged robot|humanoid robot|mobile manipulator|desk(top)? robot|robot (kit|pet|toy)",
    "salvage_reuse": r"salvag|e-?waste|recycl|repurpos|upcycl|hoverboard|robot vacuum|roomba|vacuum|old (phone|android|laptop)|smartphone|second.?hand",
}
RSS = {
    "hackaday": "https://hackaday.com/feed/",
    "hackster": "https://www.hackster.io/news.atom",
    "product_hunt": "https://www.producthunt.com/feed",
    "the_robot_report": "https://www.therobotreport.com/feed/",
    "techniahqrobot": "https://techniahqrobot.com/feed.xml",
}
HN_QUERIES = ["kicad", "pcb ai", "hardware agent", "ai cad", "robot arm", "open source drone", "open hardware", "physical ai",
              "circuit board ai", "text to cad"]
GITHUB_QUERIES = ["kicad mcp", "ai pcb", "ai hardware design", "robot arm open source", "text to cad", "pcb agent",
                  "drone flight controller kicad", "open source rover", "freecad mcp", "electronics agent"]
# Established projects, most-starred first, by GitHub topic: new-only searches never surface a 2020 staple such as
# OpenBot, which HS then rebuilt by hand on 2026-11-26.
ESTABLISHED_TOPICS = [["smartphone", "robot"], ["robot", "vacuum"], ["hoverboard"], ["roomba"], ["robot-arm"], ["rover"],
                      ["drone", "open-source"], ["kicad"], ["openwrt"], ["e-waste"], ["upcycling"], ["salvage"], ["lerobot"]]
# Cite-Refinery's atlas: open-source products from the Signals feed, each mapped to its purpose, inputs and outputs from its
# own source. Read locally from that project's published working data; nothing is fetched or run.
ATLAS_DIR = Path(os.environ.get("HS_ATLAS_DIR") or os.path.expanduser("~/.local/share/atlas-discovery"))
REDDIT: list[str] = []  # Reddit refuses unauthenticated readers (403/404 on JSON and RSS); not worked around


def _get(url: str, timeout: int = 30) -> str:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as resp:  # noqa: S310 - fixed hosts
        return resp.read().decode("utf-8", "replace")


def _clean(text: str, limit: int = 240) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    return re.sub(r"\s+", " ", text).strip()[:limit]


def _topics(text: str) -> list[str]:
    low = text.lower()
    return [k for k, rx in TOPICS.items() if re.search(rx, low)]


def hacker_news(since: datetime) -> list[dict[str, Any]]:
    out = []
    for q in HN_QUERIES:
        url = ("https://hn.algolia.com/api/v1/search_by_date?tags=story&hitsPerPage=50&numericFilters=created_at_i>"
               f"{int(since.timestamp())}&query=" + urllib.parse.quote(q))
        for h in json.loads(_get(url)).get("hits", []):
            link = h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}"
            out.append({"source": "hacker_news", "title": _clean(h.get("title", ""), 160), "url": link,
                        "date": (h.get("created_at") or "")[:10], "points": h.get("points"),
                        "discussion": f"https://news.ycombinator.com/item?id={h.get('objectID')}"})
        time.sleep(0.5)
    return out


def github(since: datetime) -> list[dict[str, Any]]:
    gh = shutil.which("gh")
    if not gh:
        return []
    out = []
    for q in GITHUB_QUERIES:
        run = subprocess.run([gh, "search", "repos", q, "--created", f">={since.date().isoformat()}", "--limit", "20",
                              "--json", "fullName,description,url,stargazersCount,createdAt,license"],
                             capture_output=True, text=True, timeout=60)
        if run.returncode != 0:
            continue
        for r in json.loads(run.stdout or "[]"):
            out.append({"source": "github", "title": f"{r['fullName']}: {_clean(r.get('description') or '', 140)}", "url": r["url"],
                        "date": (r.get("createdAt") or "")[:10], "stars": r.get("stargazersCount"),
                        "licence": (r.get("license") or {}).get("key")})
        time.sleep(1.0)
    return out


def github_established(_since: datetime) -> list[dict[str, Any]]:
    gh = shutil.which("gh")
    if not gh:
        return []
    out = []
    for topics in ESTABLISHED_TOPICS:
        run = subprocess.run([gh, "search", "repos", "--sort", "stars", "--limit", "15", "--json",
                              "fullName,description,url,stargazersCount,pushedAt,license"] + [a for t in topics for a in ("--topic", t)],
                             capture_output=True, text=True, timeout=60)
        if run.returncode != 0:
            continue
        for r in json.loads(run.stdout or "[]"):
            out.append({"source": "github_established", "title": f"{r['fullName']}: {_clean(r.get('description') or '', 140)} [{' '.join(topics)}]",
                        "url": r["url"], "date": (r.get("pushedAt") or "")[:10], "stars": r.get("stargazersCount"),
                        "licence": (r.get("license") or {}).get("key"), "established": True})
        time.sleep(1.0)
    return out


def atlas(_since: datetime, root: Path | None = None) -> list[dict[str, Any]]:
    """Every product in Cite-Refinery's atlas (its newly-possible products.json files, newest run last so it wins); the topic
    filter in ``run`` keeps the hardware ones."""
    root = root or ATLAS_DIR
    files = sorted(root.glob("signals-*/newly-possible*/products.json"), key=lambda p: p.stat().st_mtime) if root.is_dir() else []
    seen: dict[str, dict[str, Any]] = {}
    for path in files:
        try:
            products = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for p in products if isinstance(products, list) else []:
            cid = str(p.get("catalog_id") or "")
            if not cid.startswith("github:"):
                continue
            slug = cid.split(":", 1)[1]
            seen[slug] = {"source": "cite_refinery_atlas", "title": f"{slug}: {_clean(str(p.get('purpose') or ''), 160)}",
                          "url": f"https://github.com/{slug}", "date": "", "stars": int(p.get("stars") or 0) if str(p.get("stars") or "0").isdigit() else None,
                          "summary": _clean(f"in: {p.get('inputs', '')} out: {p.get('outputs', '')}", 240), "atlas_post": p.get("post")}
    return list(seen.values())


def rss(since: datetime) -> list[dict[str, Any]]:
    out = []
    for name, url in RSS.items():
        try:
            root = ET.fromstring(_get(url))
        except Exception:  # noqa: BLE001 - one dead feed must not stop the watch
            out.append({"source": name, "error": "feed unreadable", "url": url})
            continue
        for item in root.iter():
            tag = item.tag.split("}")[-1]
            if tag not in ("item", "entry"):
                continue
            fields = {c.tag.split("}")[-1]: c for c in item}
            link = fields.get("link")
            href = (link.get("href") if link is not None and link.get("href") else (link.text if link is not None else "")) or ""
            # An element with no children is falsy, so pick the first one that exists explicitly.
            date_text = next((fields[k] for k in ("pubDate", "published", "updated") if fields.get(k) is not None), None)
            date = _parse_date(date_text.text if date_text is not None else "")
            if date and date < since:
                continue
            desc = next((fields[k] for k in ("description", "summary") if fields.get(k) is not None), None)
            out.append({"source": name, "title": _clean(fields["title"].text if "title" in fields else "", 160), "url": href.strip(),
                        "date": date.date().isoformat() if date else "", "summary": _clean(desc.text if desc is not None else "")})
    return out


def reddit(since: datetime) -> list[dict[str, Any]]:
    out = []
    for sub in REDDIT:
        try:
            data = json.loads(_get(f"https://www.reddit.com/r/{sub}/top.json?t=week&limit=50"))
        except Exception:  # noqa: BLE001
            out.append({"source": f"reddit/{sub}", "error": "unreadable"})
            continue
        for c in data.get("data", {}).get("children", []):
            d = c.get("data", {})
            created = datetime.fromtimestamp(d.get("created_utc", 0), tz=timezone.utc)
            if created < since:
                continue
            out.append({"source": f"reddit/{sub}", "title": _clean(d.get("title", ""), 160),
                        "url": d.get("url_overridden_by_dest") or f"https://www.reddit.com{d.get('permalink', '')}",
                        "date": created.date().isoformat(), "score": d.get("score"),
                        "discussion": f"https://www.reddit.com{d.get('permalink', '')}"})
        time.sleep(2.0)
    return out


def _parse_date(text: str) -> datetime | None:
    text = (text or "").strip()
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            d = datetime.strptime(text.replace("Z", "+0000") if fmt.endswith("%z") else text, fmt)
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def run(days: int, state: Path) -> dict[str, Any]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    state.mkdir(parents=True, exist_ok=True)
    (state / "digests").mkdir(exist_ok=True)
    register_path = state / "register.json"
    register = json.loads(register_path.read_text()) if register_path.is_file() else {"items": {}}
    items, errors = [], []
    for fetch in (hacker_news, github, github_established, rss, reddit, atlas):
        try:
            for it in fetch(since):
                (errors if it.get("error") else items).append(it)
        except Exception as exc:  # noqa: BLE001
            errors.append({"source": fetch.__name__, "error": f"{type(exc).__name__}: {exc}"[:200]})
    today = datetime.now().date().isoformat()
    new = []
    for it in items:
        it["topics"] = _topics(f"{it.get('title', '')} {it.get('summary', '')}")
        if not it["topics"] or not it.get("url"):
            continue
        key = re.sub(r"[?#].*$", "", it["url"].rstrip("/").lower())
        if key in register["items"]:
            continue
        register["items"][key] = {**it, "first_seen": today}
        new.append(it)
    register_path.write_text(json.dumps(register, indent=1, ensure_ascii=False))
    by_topic: dict[str, list[dict[str, Any]]] = {}
    for it in new:
        by_topic.setdefault(it["topics"][0], []).append(it)
    lines = [f"# Landscape watch {today} (last {days} days)", "",
             f"{len(new)} new items across {len(by_topic)} topics; register holds {len(register['items'])}. "
             "Fetched text is untrusted: open the link and check the original before relying on anything.", ""]
    for topic, its in sorted(by_topic.items(), key=lambda kv: -len(kv[1])):
        lines += [f"## {topic.replace('_', ' ')} ({len(its)})", ""]
        for it in sorted(its, key=lambda i: -(i.get("stars") or i.get("points") or i.get("score") or 0))[:25]:
            extra = " ".join(f"{k}={it[k]}" for k in ("stars", "points", "score", "licence") if it.get(k) is not None)
            lines.append(f"- [{it['title']}]({it['url']}) · {it['source']} · {it.get('date', '')} {extra}".rstrip())
        lines.append("")
    if errors:
        lines += ["## Sources that failed this run", ""] + [f"- {e.get('source')}: {e.get('error')}" for e in errors]
    digest = state / "digests" / f"{today}.md"
    digest.write_text("\n".join(lines) + "\n")
    return {"new": len(new), "register": len(register["items"]), "digest": str(digest), "errors": errors,
            "by_topic": {k: len(v) for k, v in by_topic.items()}}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--days", type=int, default=8)
    ap.add_argument("--state", type=Path, default=Path(os.path.expanduser("~/.local/share/hs-landscape")))
    a = ap.parse_args(argv)
    print(json.dumps(run(a.days, a.state), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
