from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import httpx


@dataclass(frozen=True)
class FxRate:
    base: str
    quote: str
    rate: float
    fetched_at: str
    source: str

    def to_dict(self):
        return asdict(self)


def get_rate(
    base: str,
    quote: str,
    *,
    cache_path: str | Path,
    max_age_hours: int = 24,
) -> FxRate:
    """
    Fetch FX rate with caching.

    Uses exchangerate.host (no key) when available; falls back to a conservative static rate.
    """
    base = base.upper()
    quote = quote.upper()
    cache = Path(cache_path)
    cache.parent.mkdir(parents=True, exist_ok=True)

    cached = _read_cache(cache, base, quote)
    if cached and _fresh(cached.fetched_at, max_age_hours=max_age_hours):
        return cached

    try:
        r = httpx.get(
            "https://api.exchangerate.host/latest",
            params={"base": base, "symbols": quote},
            timeout=10.0,
            headers={"User-Agent": "Mozilla/5.0 (MechaSplicer/1.0)"},
        )
        if r.status_code == 200:
            data = r.json()
            rate = float((data.get("rates") or {}).get(quote) or 0.0)
            if rate > 0:
                fx = FxRate(base=base, quote=quote, rate=rate, fetched_at=_now_iso(), source="exchangerate.host")
                _write_cache(cache, fx)
                return fx
    except Exception:
        pass

    # Conservative fallback (approx); update by providing cache from online.
    fallback = 31.5 if (base, quote) == ("USD", "TWD") else 1.0
    fx = FxRate(base=base, quote=quote, rate=fallback, fetched_at=_now_iso(), source="fallback_static")
    _write_cache(cache, fx)
    return fx


def convert(amount: float, fx: FxRate) -> float:
    return float(amount) * float(fx.rate)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fresh(fetched_at: str, *, max_age_hours: int) -> bool:
    try:
        dt = datetime.fromisoformat(fetched_at)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - dt <= timedelta(hours=max_age_hours)
    except Exception:
        return False


def _read_cache(path: Path, base: str, quote: str) -> Optional[FxRate]:
    if not path.exists():
        return None
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(obj, dict):
            return None
        if obj.get("base") != base or obj.get("quote") != quote:
            return None
        return FxRate(
            base=base,
            quote=quote,
            rate=float(obj.get("rate") or 0.0),
            fetched_at=str(obj.get("fetched_at") or ""),
            source=str(obj.get("source") or "cache"),
        )
    except Exception:
        return None


def _write_cache(path: Path, fx: FxRate) -> None:
    path.write_text(json.dumps(fx.to_dict(), indent=2), encoding="utf-8")

