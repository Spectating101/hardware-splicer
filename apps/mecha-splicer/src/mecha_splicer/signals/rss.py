from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import feedparser
import httpx


@dataclass(frozen=True)
class SignalItem:
    source: str
    category: Optional[str]
    title: str
    url: str
    summary: str
    published: Optional[str]


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _parse_date(entry: Any) -> Optional[datetime]:
    t = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if not t:
        return None
    try:
        return datetime(*t[:6], tzinfo=timezone.utc)
    except Exception:
        return None


def iter_rss_signals(sources_path: str | Path, *, days: int = 14) -> Iterable[SignalItem]:
    sources = json.loads(Path(sources_path).read_text(encoding="utf-8")).get("sources", [])
    cutoff = _now_utc() - timedelta(days=days)

    for s in sources:
        name = str(s.get("name", "Unknown"))
        category = str(s.get("category") or "").strip() or None
        url = str(s.get("url", "")).strip()
        if not url:
            continue

        try:
            r = httpx.get(
                url,
                timeout=15.0,
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (MechaSplicer/1.0)"},
            )
            xml = r.text if r.status_code == 200 else ""
        except Exception:
            xml = ""

        parsed = feedparser.parse(xml or url)
        for e in parsed.entries or []:
            dt = _parse_date(e)
            if dt and dt < cutoff:
                continue
            title = (getattr(e, "title", "") or "").strip()
            link = (getattr(e, "link", "") or "").strip()
            summary = (getattr(e, "summary", "") or "").strip()
            if not title or not link:
                continue
            yield SignalItem(
                source=name,
                category=category,
                title=title,
                url=link,
                summary=summary,
                published=dt.isoformat() if dt else None,
            )
