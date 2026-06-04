#!/usr/bin/env python3
"""
Idea Economics: RSS inspiration → profitability triage.

This is intentionally conservative. It is a *ranking tool*, not a business oracle.

Usage:
  python3 scripts/idea_economics.py --days 14 --out /tmp/idea_scores.md
  python3 scripts/idea_economics.py --days 30 --format json --out /tmp/idea_scores.json

Overrides:
  Create a JSON file mapping "link" (or "title") to overrides, then:
  python3 scripts/idea_economics.py --overrides data/idea_economics/overrides.example.json
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import feedparser


DEFAULT_PLATFORM_FEES = {
    "gumroad": 0.10,  # rough; varies by plan/processor
    "etsy": 0.12,  # rough blended fee; varies by category/ads
    "tindie": 0.10,  # rough; varies
    "whop": 0.10,  # rough; varies
}


RISK_TAGS = [
    ("mains", re.compile(r"\b(110v|120v|220v|230v|240v|mains|ac\s*line|line\s*voltage)\b", re.I)),
    ("lithium", re.compile(r"\b(lipo|li-?ion|lithium)\b", re.I)),
    ("charger", re.compile(r"\b(charge|charger|charging)\b", re.I)),
    ("rf", re.compile(r"\b(rf|lora|ble|bluetooth|wifi|zigbee|gnss|gps|antenna)\b", re.I)),
    ("medical", re.compile(r"\b(medical|health|diagnos)\b", re.I)),
    ("safety_critical", re.compile(r"\b(aircraft|rocket|drone|autonomous|safety)\b", re.I)),
]

SUPPORT_MAGNETS = [
    ("wifi", re.compile(r"\bwifi\b", re.I)),
    ("bluetooth", re.compile(r"\b(bluetooth|ble)\b", re.I)),
    ("mobile_app", re.compile(r"\b(android|ios|iphone|app)\b", re.I)),
    ("calibration", re.compile(r"\b(calibrat|tune|alignment)\b", re.I)),
    ("mechanical", re.compile(r"\b(3d\s*print|enclosure|mechanical|mount|bearing|gear)\b", re.I)),
]

COMPLEXITY_HINTS = [
    ("fpga", re.compile(r"\bfpga\b", re.I)),
    ("high_speed", re.compile(r"\b(usb\s*3|pcie|ddr)\b", re.I)),
    ("robotics", re.compile(r"\b(robot|arm|cnc)\b", re.I)),
    ("power_electronics", re.compile(r"\b(inverter|smps|buck|boost|pfc)\b", re.I)),
]


@dataclass
class Idea:
    source: str
    title: str
    link: str
    published: Optional[str] = None
    summary: Optional[str] = None
    category: Optional[str] = None

    # Economics (can be overridden)
    shape: str = "digital"  # digital|service|kit
    price_usd: float = 29.0
    platform_fee_rate: float = 0.10
    cogs_usd: float = 0.0
    assembly_minutes: float = 0.0
    support_minutes: float = 5.0
    labor_usd_per_hour: float = 20.0
    chargeback_rate: float = 0.02
    payment_processor_rate: float = 0.03

    # Scoring
    score_total: float = 0.0
    score_breakdown: Optional[Dict[str, float]] = None
    flags: Optional[List[str]] = None
    confidence: float = 0.5  # 0..1 (heuristic)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _parse_date(entry: Any) -> Optional[datetime]:
    # feedparser exposes published_parsed/updated_parsed as time.struct_time
    t = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if not t:
        return None
    try:
        return datetime(*t[:6], tzinfo=timezone.utc)
    except Exception:
        return None


def _text(entry: Any) -> str:
    title = (getattr(entry, "title", "") or "").strip()
    summary = (getattr(entry, "summary", "") or "").strip()
    return f"{title}\n{summary}".strip()


def _detect_flags(text: str) -> List[str]:
    flags: List[str] = []
    for tag, pat in RISK_TAGS:
        if pat.search(text):
            flags.append(f"risk:{tag}")
    for tag, pat in SUPPORT_MAGNETS:
        if pat.search(text):
            flags.append(f"support:{tag}")
    for tag, pat in COMPLEXITY_HINTS:
        if pat.search(text):
            flags.append(f"complexity:{tag}")
    return flags


def _infer_shape(text: str) -> str:
    t = text.lower()
    if "kit" in t or "assembly" in t:
        return "kit"
    # Bias toward digital unless explicitly “build for me” / consulting language
    if any(w in t for w in ["consult", "hire", "freelance", "contract"]):
        return "service"
    return "digital"


def _estimate_default_pricing(shape: str) -> Tuple[float, float]:
    # (price_usd, support_minutes)
    if shape == "digital":
        return 29.0, 7.0
    if shape == "service":
        return 250.0, 30.0
    if shape == "kit":
        return 79.0, 20.0
    return 29.0, 7.0


def _estimate_risk_penalty(flags: List[str]) -> float:
    penalty = 0.0
    if "risk:mains" in flags:
        penalty += 0.45
    if "risk:lithium" in flags or "risk:charger" in flags:
        penalty += 0.25
    if "risk:medical" in flags:
        penalty += 0.35
    if "risk:safety_critical" in flags:
        penalty += 0.30
    if "risk:rf" in flags:
        penalty += 0.12
    return min(0.80, penalty)


def _estimate_support_multiplier(flags: List[str]) -> float:
    mult = 1.0
    for f in flags:
        if f.startswith("support:"):
            mult *= 1.25
    for f in flags:
        if f.startswith("complexity:"):
            mult *= 1.20
    return min(3.0, mult)


def _gross_profit_usd(idea: Idea) -> float:
    revenue = idea.price_usd
    # Platform fee + payment processing
    fees = revenue * (idea.platform_fee_rate + idea.payment_processor_rate)
    # Chargeback risk modeled as expected loss of revenue (conservative)
    chargebacks = revenue * idea.chargeback_rate
    labor = (idea.assembly_minutes / 60.0) * idea.labor_usd_per_hour
    support = (idea.support_minutes / 60.0) * idea.labor_usd_per_hour
    return revenue - fees - chargebacks - idea.cogs_usd - labor - support


def _score(idea: Idea) -> Tuple[float, Dict[str, float]]:
    flags = idea.flags or []
    gp = _gross_profit_usd(idea)
    margin = gp / max(1e-6, idea.price_usd)

    # A) gross margin potential (0..25)
    a = 25.0 * max(0.0, min(1.0, margin))

    # B) support burden (0..20): fewer minutes is better
    b = 20.0 * (1.0 - max(0.0, min(1.0, idea.support_minutes / 30.0)))

    # C) regulatory/platform risk (0..15): apply penalties
    risk_penalty = _estimate_risk_penalty(flags)
    c = 15.0 * (1.0 - risk_penalty)

    # D) differentiation (0..15): heuristically unknown → mid, penalize “generic”
    title = idea.title or ""
    is_corp_news = bool(re.search(r"\b(launches|announces|claims|acquires|facility|foundry|quarter|earnings)\b", title, re.I))
    is_howto = bool(re.search(r"\b(build|how to|tutorial|project)\b", title, re.I))
    generic_penalty = 0.20 if re.search(r"\b(weather|temp|humidity|monitor)\b", title, re.I) else 0.0
    if is_corp_news:
        d = 15.0 * 0.20
    elif is_howto:
        d = 15.0 * 0.70
    else:
        d = 15.0 * 0.55
    d -= 15.0 * generic_penalty
    d = max(0.0, min(15.0, d))

    # E) build complexity/failure rate (0..15): penalize complexity flags
    complexity_flags = [f for f in flags if f.startswith("complexity:")]
    e = 15.0 * (1.0 - min(0.70, 0.15 * len(complexity_flags)))

    # F) Circuit-AI leverage (0..10): digital/service score higher
    f = 10.0
    if idea.shape == "kit":
        f = 6.5
    if any("risk:mains" == x for x in flags):
        f -= 1.0
    f = max(0.0, min(10.0, f))

    total = a + b + c + d + e + f
    return total, {"margin": a, "support": b, "risk": c, "diff": d, "complexity": e, "circuit_ai": f}


def _load_overrides(path: Optional[str]) -> Dict[str, Dict[str, Any]]:
    if not path:
        return {}
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Overrides must be a JSON object mapping link/title → overrides.")
    return {str(k): (v if isinstance(v, dict) else {}) for k, v in data.items()}


def _apply_overrides(idea: Idea, overrides: Dict[str, Dict[str, Any]]) -> None:
    key = idea.link or idea.title
    ov = overrides.get(key) or overrides.get(idea.title) or overrides.get(idea.link)
    if not ov:
        return
    for k, v in ov.items():
        if hasattr(idea, k):
            setattr(idea, k, v)
    idea.confidence = max(idea.confidence, 0.85)


def _fetch_feed(url: str) -> feedparser.FeedParserDict:
    # feedparser can do HTTP itself, but some sites need headers/timeout. Keep it simple here.
    return feedparser.parse(url)


def _iter_ideas(sources_path: str, days: int) -> Iterable[Idea]:
    sources = json.loads(Path(sources_path).read_text(encoding="utf-8")).get("sources", [])
    cutoff = _now_utc() - timedelta(days=days)

    for s in sources:
        name = str(s.get("name", "Unknown"))
        category = str(s.get("category") or "").strip() or None
        url = str(s.get("url", "")).strip()
        if not url:
            continue

        parsed = _fetch_feed(url)
        entries = parsed.entries or []
        for e in entries:
            dt = _parse_date(e)
            if dt and dt < cutoff:
                continue
            title = (getattr(e, "title", "") or "").strip()
            link = (getattr(e, "link", "") or "").strip()
            summary = (getattr(e, "summary", "") or "").strip() or None
            published = None
            if dt:
                published = dt.isoformat()
            yield Idea(source=name, category=category, title=title, link=link, published=published, summary=summary)


def _finalize_idea(idea: Idea, overrides: Dict[str, Dict[str, Any]]) -> Idea:
    text = _text(type("E", (), {"title": idea.title, "summary": idea.summary or ""})())
    idea.flags = _detect_flags(text)
    idea.shape = _infer_shape(text)
    idea.price_usd, base_support = _estimate_default_pricing(idea.shape)
    idea.support_minutes = base_support * _estimate_support_multiplier(idea.flags)
    idea.platform_fee_rate = DEFAULT_PLATFORM_FEES["gumroad"] if idea.shape == "digital" else 0.0
    if idea.shape == "kit":
        idea.platform_fee_rate = DEFAULT_PLATFORM_FEES["tindie"]
        idea.cogs_usd = 25.0  # placeholder assumption (overrides should replace)
        idea.assembly_minutes = 25.0
    if idea.shape == "service":
        idea.platform_fee_rate = 0.10  # e.g., Upwork-ish; override if you want

    _apply_overrides(idea, overrides)

    total, breakdown = _score(idea)
    idea.score_total = round(total, 2)
    idea.score_breakdown = {k: round(v, 2) for k, v in breakdown.items()}
    return idea


def _to_markdown(ideas: List[Idea]) -> str:
    lines = []
    lines.append("# Idea Economics (Auto-Triage)\n")
    lines.append("This output is heuristic and conservative. Use overrides to improve accuracy.\n")
    lines.append("| Score | Shape | Est. profit/sale | Price | Source | Title | Flags |")
    lines.append("|---:|---|---:|---:|---|---|---|")
    for i in ideas:
        gp = _gross_profit_usd(i)
        flags = ", ".join(i.flags or [])
        title = (i.title or "").replace("|", " ")
        src = (i.source or "").replace("|", " ")
        lines.append(
            f"| {i.score_total:.1f} | {i.shape} | ${gp:.2f} | ${i.price_usd:.0f} | {src} | [{title}]({i.link}) | {flags} |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sources", default="NEWS_SOURCES.json", help="Path to NEWS_SOURCES.json")
    ap.add_argument("--days", type=int, default=14, help="Only include posts from last N days")
    ap.add_argument(
        "--categories",
        default="projects,project_blueprints",
        help="Comma-separated source categories to include (from NEWS_SOURCES.json). Use 'all' to disable filtering.",
    )
    ap.add_argument(
        "--require-howto",
        action="store_true",
        default=True,
        help="Only keep entries that look like build/tutorial/project content (filters out most corporate news).",
    )
    ap.add_argument(
        "--no-require-howto",
        dest="require_howto",
        action="store_false",
        help="Disable the how-to filter.",
    )
    ap.add_argument("--overrides", default=None, help="JSON overrides mapping link/title → field overrides")
    ap.add_argument("--format", choices=["md", "json"], default="md")
    ap.add_argument("--out", default=None, help="Output file path (default: stdout)")
    ap.add_argument("--limit", type=int, default=50, help="Max ideas to output")
    args = ap.parse_args()

    overrides = _load_overrides(args.overrides)

    wanted_categories: Optional[set[str]]
    if str(args.categories).strip().lower() == "all":
        wanted_categories = None
    else:
        wanted_categories = {c.strip() for c in str(args.categories).split(",") if c.strip()}

    raw = list(_iter_ideas(args.sources, args.days))
    if wanted_categories is not None:
        raw = [i for i in raw if (i.category or "") in wanted_categories]

    if args.require_howto:
        def _looks_like_howto(x: Idea) -> bool:
            t = (x.title or "").lower()
            l = (x.link or "").lower()
            if any(w in t for w in ["build", "how to", "tutorial", "project", "diy"]):
                return True
            if any(p in l for p in ["/project", "/projects", "/tutorial", "/how-to", "microcontroller-projects"]):
                return True
            return False

        raw = [i for i in raw if _looks_like_howto(i)]

    ideas = [_finalize_idea(i, overrides) for i in raw if i.title and i.link]

    ideas.sort(key=lambda x: x.score_total, reverse=True)
    ideas = ideas[: max(1, args.limit)]

    if args.format == "json":
        payload = [asdict(i) for i in ideas]
        out = json.dumps(payload, indent=2, ensure_ascii=False)
    else:
        out = _to_markdown(ideas)

    if args.out:
        Path(args.out).write_text(out, encoding="utf-8")
    else:
        sys.stdout.write(out)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
