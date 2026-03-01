#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_week(day_str: str) -> str | None:
    try:
        d = datetime.strptime(day_str, "%Y-%m-%d").date()
        y, w, _ = d.isocalendar()
        return f"{y:04d}-W{w:02d}"
    except Exception:
        return None


@dataclass
class GateThresholds:
    min_paying_users: int = 3
    min_repeat_weekly_users: int = 2
    min_renewal_signals: int = 1


def _default_usage_db() -> Path:
    return Path("/tmp/circuit-ai-usage.sqlite")


def _fetch_metrics(db_path: Path, window_days: int) -> Dict[str, Any]:
    if not db_path.exists():
        return {
            "db_exists": False,
            "paying_users": 0,
            "repeat_weekly_users": 0,
            "renewal_signals": 0,
            "fulfillments_in_window": 0,
            "usage_rows_in_window": 0,
            "sample_repeat_weekly_keys": [],
        }

    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    try:
        since_day = (_utc_now() - timedelta(days=max(1, window_days))).date().isoformat()

        paying_users = 0
        fulfillments_in_window = 0
        renewal_signals = 0
        repeat_weekly_users = 0
        usage_rows_in_window = 0
        sample_repeat_weekly_keys: list[str] = []

        # Paying users: distinct delivered fulfillments by key hash in window.
        row = con.execute(
            """
            SELECT
              COUNT(DISTINCT key_hash) AS paying_users,
              COUNT(*) AS fulfillments_in_window
            FROM fulfillments
            WHERE key_hash IS NOT NULL
              AND key_hash != ''
              AND created_at >= ?
              AND (
                status LIKE 'delivered%'
                OR status LIKE 'delivery_failed%'
              )
            """,
            (since_day,),
        ).fetchone()
        if row:
            paying_users = int(row["paying_users"] or 0)
            fulfillments_in_window = int(row["fulfillments_in_window"] or 0)

        # Renewal signals: same customer_email with 2+ delivered fulfillments in window.
        row = con.execute(
            """
            SELECT COUNT(*) AS renewal_signals
            FROM (
              SELECT customer_email
              FROM fulfillments
              WHERE customer_email IS NOT NULL
                AND customer_email != ''
                AND created_at >= ?
                AND status LIKE 'delivered%'
              GROUP BY customer_email
              HAVING COUNT(*) >= 2
            ) t
            """,
            (since_day,),
        ).fetchone()
        if row:
            renewal_signals = int(row["renewal_signals"] or 0)

        # Weekly repeat users: key hashes active in 2+ distinct weeks.
        rows = con.execute(
            """
            SELECT key_hash, day, count
            FROM usage
            WHERE day >= ?
            """,
            (since_day,),
        ).fetchall()
        usage_rows_in_window = len(rows)
        weeks_by_key: Dict[str, set[str]] = {}
        for r in rows:
            kh = str(r["key_hash"] or "")
            week = _iso_week(str(r["day"] or ""))
            if not kh or not week:
                continue
            weeks_by_key.setdefault(kh, set()).add(week)
        repeat_keys = sorted([k for k, weeks in weeks_by_key.items() if len(weeks) >= 2])
        repeat_weekly_users = len(repeat_keys)
        sample_repeat_weekly_keys = repeat_keys[:10]

        return {
            "db_exists": True,
            "paying_users": paying_users,
            "repeat_weekly_users": repeat_weekly_users,
            "renewal_signals": renewal_signals,
            "fulfillments_in_window": fulfillments_in_window,
            "usage_rows_in_window": usage_rows_in_window,
            "sample_repeat_weekly_keys": sample_repeat_weekly_keys,
        }
    finally:
        con.close()


def _build_report(db_path: Path, window_days: int, thresholds: GateThresholds) -> Dict[str, Any]:
    m = _fetch_metrics(db_path, window_days)
    gate_c_pass = (
        m["paying_users"] >= thresholds.min_paying_users
        and m["repeat_weekly_users"] >= thresholds.min_repeat_weekly_users
        and m["renewal_signals"] >= thresholds.min_renewal_signals
    )
    return {
        "generated_at_utc": _utc_now().isoformat(),
        "inputs": {
            "usage_db": str(db_path),
            "window_days": window_days,
            "thresholds": {
                "min_paying_users": thresholds.min_paying_users,
                "min_repeat_weekly_users": thresholds.min_repeat_weekly_users,
                "min_renewal_signals": thresholds.min_renewal_signals,
            },
        },
        "metrics": m,
        "gate_c_pass": gate_c_pass,
    }


def _write_json(path: Path, report: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_md(path: Path, report: Dict[str, Any]) -> None:
    t = report["inputs"]["thresholds"]
    m = report["metrics"]
    lines = [
        "# Subscription KPI Report",
        "",
        f"- Generated (UTC): `{report['generated_at_utc']}`",
        f"- Usage DB: `{report['inputs']['usage_db']}`",
        f"- Window (days): `{report['inputs']['window_days']}`",
        f"- Gate C Pass: **`{report['gate_c_pass']}`**",
        "",
        "## Thresholds",
        f"- paying_users >= `{t['min_paying_users']}`",
        f"- repeat_weekly_users >= `{t['min_repeat_weekly_users']}`",
        f"- renewal_signals >= `{t['min_renewal_signals']}`",
        "",
        "## Metrics",
        f"- db_exists: `{m['db_exists']}`",
        f"- paying_users: `{m['paying_users']}`",
        f"- repeat_weekly_users: `{m['repeat_weekly_users']}`",
        f"- renewal_signals: `{m['renewal_signals']}`",
        f"- fulfillments_in_window: `{m['fulfillments_in_window']}`",
        f"- usage_rows_in_window: `{m['usage_rows_in_window']}`",
        f"- sample_repeat_weekly_keys: `{m['sample_repeat_weekly_keys']}`",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Report subscription KPIs for Gate C readiness.")
    ap.add_argument("--usage-db", type=Path, default=_default_usage_db())
    ap.add_argument("--window-days", type=int, default=30)
    ap.add_argument("--min-paying-users", type=int, default=3)
    ap.add_argument("--min-repeat-weekly-users", type=int, default=2)
    ap.add_argument("--min-renewal-signals", type=int, default=1)
    ap.add_argument("--out-json", type=Path, default=Path("docs/status/generated/SUBSCRIPTION_KPI_REPORT.json"))
    ap.add_argument("--out-md", type=Path, default=Path("docs/status/generated/SUBSCRIPTION_KPI_REPORT.md"))
    args = ap.parse_args()

    thresholds = GateThresholds(
        min_paying_users=max(0, args.min_paying_users),
        min_repeat_weekly_users=max(0, args.min_repeat_weekly_users),
        min_renewal_signals=max(0, args.min_renewal_signals),
    )
    report = _build_report(db_path=args.usage_db, window_days=max(1, args.window_days), thresholds=thresholds)
    _write_json(args.out_json, report)
    _write_md(args.out_md, report)
    print(f"Wrote: {args.out_json}")
    print(f"Wrote: {args.out_md}")
    print(f"Gate C Pass: {report['gate_c_pass']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

