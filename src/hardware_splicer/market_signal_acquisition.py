"""Read-only, bounded public-source acquisition for HS commercial evidence.

The output is a hs.market_signals.v1 candidate pack consumable by the PR #294
bridge. Github issues are self-reported problems, Ruten prices are seller asks.
Neither supplies verified buyers, orders, supplier quotes or build authority.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import os
import re
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

SCHEMA = "hs.discovery_plan.v1"
SEARCH = "https://rtapi.ruten.com.tw/api/search/v3/index.php/core/prod"
DETAIL = "https://rtapi.ruten.com.tw/api/prod/v2/index.php/prod"
GITHUB = "https://api.github.com/search/issues"
HOSTS = {"api.github.com", "rtapi.ruten.com.tw"}
Fetch = Callable[[str, Mapping[str, str]], Any]


class AcquisitionError(ValueError):
    """Invalid plan or unusable source response."""


def fetch_json(url: str, headers: Mapping[str, str]) -> Any:
    """Read only from two fixed public API origins, with bounded requests."""
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in HOSTS or parsed.username or parsed.password:
        raise AcquisitionError("disallowed acquisition origin")
    request = Request(url, headers={"User-Agent": "HS-public-market-research/1", "Accept": "application/json", **dict(headers)})
    try:
        with urlopen(request, timeout=15) as response:
            final = urlparse(response.geturl())
            if final.scheme != "https" or final.hostname not in HOSTS:
                raise AcquisitionError("untrusted API redirect")
            return json.load(response)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise AcquisitionError(f"source request failed: {type(exc).__name__}") from exc


def _check_plan(plan: Mapping[str, Any]) -> None:
    if not isinstance(plan, Mapping) or plan.get("schema") != SCHEMA:
        raise AcquisitionError("invalid discovery plan schema")
    if not re.fullmatch(r"[a-z][a-z0-9_-]{4,90}", str(plan.get("target_architecture", ""))):
        raise AcquisitionError("invalid target architecture")
    jobs = plan.get("jobs")
    if not isinstance(jobs, list) or not 1 <= len(jobs) <= 12:
        raise AcquisitionError("discovery requires 1-12 bounded jobs")
    ids = set()
    for job in jobs:
        if not isinstance(job, dict) or not re.fullmatch(r"[a-z][a-z0-9-]{2,49}", str(job.get("id", ""))):
            raise AcquisitionError("invalid job ID")
        if job["id"] in ids:
            raise AcquisitionError("duplicate job ID")
        ids.add(job["id"])
        for key in ("github_queries", "ruten_queries"):
            queries = job.get(key, [])
            if not isinstance(queries, list) or len(queries) > 5:
                raise AcquisitionError("too many queries")
            for q in queries:
                if not isinstance(q, str) or not 2 <= len(q.strip()) <= 100 or any(c in q for c in ("\n", "\r")):
                    raise AcquisitionError("invalid search query")
        if not job.get("github_queries") and not job.get("ruten_queries"):
            raise AcquisitionError("job must search at least one source")
    for key, limit in (("max_pages", 3), ("github_per_page", 30), ("ruten_limit", 40)):
        n = plan.get(key, 1 if key == "max_pages" else 10)
        if type(n) is not int or not 1 <= n <= limit:
            raise AcquisitionError(f"invalid {key} request budget")


def _time(observed: datetime) -> str:
    if observed.tzinfo is None:
        raise AcquisitionError("observation timestamp must include timezone")
    return observed.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def _public_url(value: Any, host: str, segment: str) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme == "https" and parsed.hostname == host and segment in parsed.path and not parsed.username and not parsed.password


def _github(row: Any, stamp: str) -> dict[str, Any] | None:
    if not isinstance(row, dict) or "pull_request" in row:
        return None
    url = row.get("html_url")
    if not _public_url(url, "github.com", "/issues/") or not isinstance(row.get("number"), int):
        return None
    # No usernames, bodies, or arbitrary source text are treated as verified demand.
    raw = {"url": url, "title": str(row.get("title", ""))[:180], "updated_at": row.get("updated_at")}
    return {"id": "github-" + _digest(url)[:18], "kind": "anecdotal_problem", "relation": "general",
            "source_url": url, "observed_at_utc": stamp, "summary": raw["title"],
            "source_metadata": {"source": "github_public_issue", "source_record_sha256": _digest(raw),
                                "source_updated_at": row.get("updated_at"), "not_a_customer_interview": True}}


def _ruten(row: Any, stamp: str) -> dict[str, Any] | None:
    if not isinstance(row, dict):
        return None
    pid = str(row.get("ProdId", ""))
    if not re.fullmatch(r"\d{8,20}", pid):
        return None
    prices = row.get("PriceRange")
    if not isinstance(prices, list) or not prices or type(prices[0]) not in (int, float):
        return None
    price = prices[0]
    if price <= 0 or price >= 100000 or any(type(v) not in (int, float) or v < price for v in prices):
        return None  # reject masked, teaser, or corrupt variant prices
    url = f"https://www.ruten.com.tw/item/{pid}/"
    raw = {"id": pid, "title": str(row.get("ProdName", ""))[:180], "prices": prices,
           "sold_qty": row.get("SoldQty"), "stock": row.get("StockQty")}
    qty = row.get("SoldQty")
    qty = qty if type(qty) is int and qty >= 0 else None
    return {"id": "ruten-" + pid, "kind": "marketplace_asking_price", "relation": "adjacent",
            "source_url": url, "observed_at_utc": stamp, "summary": raw["title"],
            "source_metadata": {"source": "ruten_public_listing", "source_record_sha256": _digest(raw),
                                "asking_price_twd": price, "seller_reported_cumulative_sold": qty,
                                "unverified_variant_and_stock": True}}


def acquire(plan: Mapping[str, Any], *, observed: datetime,
            getter: Fetch = fetch_json, github_token: str | None = None) -> dict[str, Any]:
    """Acquire bounded source observations. Partial provider failures are explicit.

    Queries represent researcher-seeded jobs, not open-world opportunity discovery.
    No LLM, buyer contact, order, manufacturer call or physical control occurs.
    """
    _check_plan(plan)
    stamp = _time(observed)
    token = github_token if github_token is not None else os.environ.get("GITHUB_TOKEN", "")
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    observed_signals: dict[str, dict[str, Any]] = {}
    failures: list[dict[str, str]] = []
    coverage: list[dict[str, Any]] = []
    job_counts: dict[str, dict[str, int]] = {job["id"]: {"github": 0, "ruten": 0} for job in plan["jobs"]}

    def add(signal: dict[str, Any] | None, job: str, source: str) -> None:
        if signal is None:
            return
        if signal["id"] not in observed_signals:
            observed_signals[signal["id"]] = {**signal, "discovery_job_ids": []}
        linked = observed_signals[signal["id"]]["discovery_job_ids"]
        if job not in linked:
            linked.append(job)
            job_counts[job][source] += 1

    for job in plan["jobs"]:
        for query in job.get("github_queries", []):
            seen = 0
            total = None
            pages_done = 0
            for page in range(1, plan.get("max_pages", 1) + 1):
                url = GITHUB + "?" + urlencode({"q": query + " is:issue", "per_page": plan.get("github_per_page", 10),
                                              "page": page, "sort": "updated", "order": "desc"})
                try:
                    data = getter(url, headers)
                    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
                        raise AcquisitionError("unexpected GitHub response")
                    total = data.get("total_count")
                    if type(total) is not int or total < 0:
                        raise AcquisitionError("missing GitHub total count")
                    rows = data["items"]
                    pages_done += 1
                    for row in rows:
                        add(_github(row, stamp), job["id"], "github")
                    seen += len(rows)
                    if len(rows) < plan.get("github_per_page", 10):
                        break
                except (AcquisitionError, KeyError, TypeError, ValueError) as exc:
                    failures.append({"job": job["id"], "source": "github", "query": query,
                                     "error": str(exc)[:150]})
                    break
            coverage.append({"job": job["id"], "source": "github", "query": query,
                             "pages_fetched": pages_done, "rows_fetched": seen,
                             "provider_total_count": total, "truncated": total is None or seen < total})

        for query in job.get("ruten_queries", []):
            rows_seen = 0
            details_seen = 0
            try:
                search_url = SEARCH + "?" + urlencode({"q": query, "type": "direct", "sort": "rnk/dc",
                                                     "offset": 1, "limit": plan.get("ruten_limit", 10)})
                search = getter(search_url, {})
                if not isinstance(search, dict) or not isinstance(search.get("Rows"), list):
                    raise AcquisitionError("unexpected Ruten search response")
                ids = [str(x.get("Id", "")) for x in search["Rows"] if isinstance(x, dict)]
                ids = list(dict.fromkeys(x for x in ids if re.fullmatch(r"\d{8,20}", x)))[:plan.get("ruten_limit", 10)]
                rows_seen = len(ids)
                for k in range(0, len(ids), 20):
                    detail_url = DETAIL + "?" + urlencode({"id": ",".join(ids[k:k + 20])})
                    details = getter(detail_url, {})
                    if not isinstance(details, list):
                        raise AcquisitionError("unexpected Ruten detail response")
                    details_seen += len(details)
                    for detail in details:
                        add(_ruten(detail, stamp), job["id"], "ruten")
            except (AcquisitionError, KeyError, TypeError, ValueError) as exc:
                failures.append({"job": job["id"], "source": "ruten", "query": query,
                                 "error": str(exc)[:150]})
            coverage.append({"job": job["id"], "source": "ruten", "query": query,
                             "search_ids": rows_seen, "details_fetched": details_seen,
                             "truncated": rows_seen >= plan.get("ruten_limit", 10)})

    signals = sorted(observed_signals.values(), key=lambda s: s["id"])
    for signal in signals:
        signal["discovery_job_ids"].sort()
    candidates = [{"id": job["id"], "problem_to_investigate": job.get("problem_to_investigate", ""),
                   "source_observations": job_counts[job["id"]],
                   "status": "EVIDENCE_COLLECTION_ONLY", "qualified_buyers": 0,
                   "next_validation": "Interview actual users and test price-specific willingness to pay"}
                  for job in plan["jobs"]]
    return {"schema": "hs.market_signals.v1", "target_architecture": plan["target_architecture"],
            "scope": "Automated bounded public-source discovery; source interest is NOT exact-product demand",
            "captured_at_utc": stamp, "plan_sha256": _digest(plan),
            "signals": signals, "discovery": {"jobs": candidates, "coverage": coverage, "failures": failures,
                                         "acquisition_status": "partial" if failures else "complete_with_bounded_queries",
                                         "exact_product_customers_verified": 0,
                                         "source_type_limits": ["GitHub issues are public self-reports, not buyer interviews",
                                                                "Ruten asking prices and seller counters are not verified sales",
                                                                "Open-world market discovery and SKU verification remain unimplemented"]}}
