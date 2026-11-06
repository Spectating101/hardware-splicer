"""Read current Ruten listings for a search query, read-only and slowly.

A listing is what a seller says: a title, an asking price and a sold count. It is not a quote, not stock, and not proof
that the item in the photo is the part in the title. HS uses listings to show that a part is obtainable and to point a
person at the page to check; the part's engineering facts come from datasheets, never from a listing title.

Ruten's public JSON endpoints need no key. Requests are spaced (one per second by default) and a dropped network
connection is retried; an HTTP error is not, because the server answered.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

SEARCH_URL = "https://rtapi.ruten.com.tw/api/search/v3/index.php/core/prod"
DETAIL_URL = "https://rtapi.ruten.com.tw/api/prod/v2/index.php/prod"
USER_AGENT = "HS-robot-parts/1 (single-user research; low volume)"
MASKED_PRICE_MIN = 100000  # some sellers show 993800-style placeholder prices; never a real price
DETAIL_BATCH = 20
TRIES = 3
BACKOFF_S = 5.0

Listing = dict[str, Any]


class RutenClient:
    """Counts requests and spaces them; one instance per research session."""

    def __init__(self, sleep: float = 1.0):
        self.sleep = sleep
        self.requests = 0

    def get(self, url: str, params: dict) -> object:
        req = urllib.request.Request(url + "?" + urllib.parse.urlencode(params), headers={"User-Agent": USER_AGENT})
        for attempt in range(1, TRIES + 1):
            try:
                with urllib.request.urlopen(req, timeout=25) as reply:
                    data = json.load(reply)
                break
            except urllib.error.HTTPError:
                raise
            except (urllib.error.URLError, TimeoutError, ConnectionError):
                if attempt == TRIES:
                    raise
                time.sleep(BACKOFF_S * attempt)
        self.requests += 1
        time.sleep(self.sleep)
        return data


def search(query: str, *, limit: int = 40, sleep: float = 1.0, client: RutenClient | None = None) -> list[Listing]:
    """Listings for ``query`` in Ruten's relevance order, at most ``limit``."""
    client = client or RutenClient(sleep)
    found = client.get(SEARCH_URL, {"q": query, "type": "direct", "sort": "rnk/dc", "offset": 1, "limit": limit})
    ids = [row["Id"] for row in found.get("Rows", [])][:limit]
    out: list[Listing] = []
    for start in range(0, len(ids), DETAIL_BATCH):
        for d in client.get(DETAIL_URL, {"id": ",".join(ids[start:start + DETAIL_BATCH])}):
            price_range = list(d["PriceRange"])
            out.append({
                "id": d["ProdId"], "title": d["ProdName"], "price_twd": price_range[0], "price_range": price_range,
                "sold_qty": d["SoldQty"], "stock": d.get("StockQty"),
                "url": f"https://www.ruten.com.tw/item/{d['ProdId']}/",
                "price_masked": price_range[0] >= MASKED_PRICE_MIN,
            })
    return out
