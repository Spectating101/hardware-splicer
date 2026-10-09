"""Find teardowns of the device a board came from, on iFixit, and link to them.

iFixit's public search needs no key and is free for non-commercial use. Its teardowns are licensed CC BY-NC-SA, so this only returns
titles and links, with credit, and never copies their content. A teardown often names the chips on a board, which is what a person
holding an unknown board wants to know.
"""

from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from typing import Any, Callable

from .text_safety import has_hidden_characters

SEARCH_URL = "https://www.ifixit.com/api/2.0/search/{query}?filter=guide&limit=10"
MAX_QUERY = 60
MAX_BYTES = 512 * 1024
CACHE_TTL_S = 900.0
ATTRIBUTION = "From iFixit, licensed CC BY-NC-SA for non-commercial use. These are links to their pages: read the teardown there."
_ALLOWED_URL = re.compile(r"^https://www\.ifixit\.com/[^\s\"'<>]{1,300}$")
_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}


class TeardownSearchError(ValueError):
    """The query cannot be searched."""


def _fetch(url: str, timeout_s: float) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "hardware-splicer/1 (teardown link search)", "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout_s) as response:  # noqa: S310 - the host is fixed by SEARCH_URL
        return response.read(MAX_BYTES + 1)


def search_teardowns(query: Any, *, fetch: Callable[[str, float], bytes] | None = None, timeout_s: float = 6.0, now: Callable[[], float] = time.monotonic) -> dict[str, Any]:
    if not isinstance(query, str):
        raise TeardownSearchError("the search must be text")
    text = " ".join(query.split())
    if len(text) < 3:
        raise TeardownSearchError("type at least 3 characters")
    if len(text) > MAX_QUERY:
        raise TeardownSearchError(f"the search may be at most {MAX_QUERY} characters")
    if has_hidden_characters(text):
        raise TeardownSearchError("the search may not contain control or invisible characters")
    key = text.lower()
    cached = _CACHE.get(key)
    if cached and now() - cached[0] < CACHE_TTL_S:
        return cached[1]
    result: dict[str, Any] = {"query": text, "attribution": ATTRIBUTION, "available": True, "results": [], "note": None}
    try:
        raw = (fetch or _fetch)(SEARCH_URL.format(query=urllib.parse.quote(text, safe="")), timeout_s)
        if len(raw) > MAX_BYTES:
            raise ValueError("response too large")
        body = json.loads(raw.decode("utf-8"))
        rows = body.get("results") if isinstance(body, dict) else None
        if not isinstance(rows, list):
            raise ValueError("unexpected shape")
    except Exception:
        # Offline, slow or changed: say so, and do not keep the failure.
        return {**result, "available": False, "note": "iFixit could not be reached just now. You can search it yourself."}
    for row in rows:
        if not isinstance(row, dict):
            continue
        url, title = row.get("url"), row.get("title")
        if not isinstance(url, str) or not isinstance(title, str) or not _ALLOWED_URL.match(url) or has_hidden_characters(title):
            continue
        summary = row.get("summary") if isinstance(row.get("summary"), str) and not has_hidden_characters(row["summary"]) else ""
        result["results"].append({"title": title[:140], "url": url, "type": str(row.get("type") or "guide")[:20], "summary": summary[:160]})
        if len(result["results"]) >= 8:
            break
    result["results"].sort(key=lambda r: (r["type"] != "teardown", r["title"].lower()))
    if not result["results"]:
        result["note"] = "No guides found. Try the device's model name."
    _CACHE[key] = (now(), result)
    return result


def clear_cache() -> None:
    _CACHE.clear()
