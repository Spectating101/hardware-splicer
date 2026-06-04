from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query

from src.mecha_splicer.runner import run
from src.mecha_splicer.signals.rss import iter_rss_signals
from src.mecha_splicer.templates.mint_templates import spec_for_category

router = APIRouter()


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


@router.post("/mint")
def mint(
    *,
    sources_path: str = Query(default="docs/NEWS_SOURCES.json"),
    days: int = Query(default=14, ge=1, le=90),
    max_categories: int = Query(default=3, ge=1, le=10),
    max_results: int = Query(default=6, ge=1, le=20),
    out_root: str = Query(default="data/opportunities/mecha_splicer_mint"),
    use_3d_splicer: bool = Query(default=False),
    render_stl: bool = Query(default=False),
):
    repo_root = Path(__file__).resolve().parents[3]

    cats_path = repo_root / "src/mecha_splicer/templates/categories.json"
    categories = json.loads(cats_path.read_text(encoding="utf-8"))["categories"]

    signals = list(iter_rss_signals(repo_root / sources_path, days=days))

    def _tokenize(text: str) -> str:
        return (text or "").lower()

    hits: Dict[str, int] = {k: 0 for k in categories}
    exemplars: Dict[str, List[Dict[str, Any]]] = {k: [] for k in categories}
    for s in signals:
        blob = _tokenize(f"{s.title} {s.summary}")
        for cat, keys in categories.items():
            if any(k.lower() in blob for k in keys):
                hits[cat] += 1
                if len(exemplars[cat]) < max_results:
                    exemplars[cat].append(asdict(s))

    ranked = sorted(((c, hits[c]) for c in hits), key=lambda x: (-x[1], x[0]))
    picked = [c for c, n in ranked if n > 0][:max_categories]

    out_dir = repo_root / out_root / _utc_stamp()
    out_dir.mkdir(parents=True, exist_ok=True)

    report: Dict[str, Any] = {"picked_categories": picked, "ranked": ranked, "signals_total": len(signals), "bundles": []}
    for cat in picked:
        cat_dir = out_dir / cat
        cat_dir.mkdir(parents=True, exist_ok=True)

        spec = spec_for_category(cat)
        if not spec:
            continue
        bundle = run(spec, out_dir=cat_dir, use_3d_splicer=use_3d_splicer, render_stl=render_stl)
        (cat_dir / "signals.json").write_text(json.dumps(exemplars.get(cat, []), indent=2), encoding="utf-8")
        (cat_dir / "spec.json").write_text(json.dumps(spec, indent=2), encoding="utf-8")
        report["bundles"].append({"category": cat, "bundle": bundle})

    (out_dir / "mint.report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report

