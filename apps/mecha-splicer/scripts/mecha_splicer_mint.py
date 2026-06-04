#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def main() -> int:
    ap = argparse.ArgumentParser(description="Mecha-Splicer Mint: signals → categories → bundles.")
    ap.add_argument("--signals", choices=["rss"], default="rss")
    ap.add_argument("--sources", default="docs/NEWS_SOURCES.json", help="RSS sources json")
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--max-categories", type=int, default=3)
    ap.add_argument("--max-results", type=int, default=6, help="Max exemplar signals per category")
    ap.add_argument("--out-root", default="data/opportunities/mecha_splicer_mint")
    ap.add_argument("--force-category", default=None, help="Force a single category (like 'enclosure' or 'mount').")
    ap.add_argument("--force-template", default=None, help="Force a specific template by name (see --list-templates).")
    ap.add_argument("--list-templates", action="store_true", help="List available templates and exit.")
    ap.add_argument("--use-3d-splicer", action="store_true", help="Call sibling 3d-splicer for electronics-anchored enclosure categories.")
    ap.add_argument("--render-stl", action="store_true", help="With --use-3d-splicer, request STL rendering.")
    ap.add_argument("--include-pricing", action="store_true", help="Emit BUY_LIST.csv + lock report using catalog + overrides.")
    ap.add_argument("--sku-overrides", default=None, help="SKU overrides JSON path (applies to all categories unless per-category file exists).")
    ap.add_argument("--render-openscad-stl", action="store_true", help="Try to render OpenSCAD outputs to STL (local openscad or docker).")
    ap.add_argument("--openscad-docker-image", default=None, help="Optional Docker image to use for OpenSCAD rendering (e.g. openscad/openscad:latest).")
    ap.add_argument("--report-currency", default="TWD", help="Reporting currency for COGS summary (default: TWD).")
    args = ap.parse_args()

    import sys

    sys.path.insert(0, str(_repo_root()))

    from src.mecha_splicer.signals.rss import iter_rss_signals  # type: ignore
    from src.mecha_splicer.templates.mint_templates import default_templates, template_for_name  # type: ignore

    if args.list_templates:
        print(json.dumps([{"category": t.category, "name": t.name} for t in default_templates()], indent=2))
        return 0

    # Load categories keywords
    cats_path = _repo_root() / "src/mecha_splicer/templates/categories.json"
    categories = json.loads(cats_path.read_text(encoding="utf-8"))["categories"]

    signals = list(iter_rss_signals(_repo_root() / args.sources, days=args.days))
    (_repo_root() / args.out_root).mkdir(parents=True, exist_ok=True)

    def _tokenize(text: str) -> str:
        return (text or "").lower()

    hits: Dict[str, int] = {k: 0 for k in categories}
    exemplars: Dict[str, List[Dict[str, Any]]] = {k: [] for k in categories}
    for s in signals:
        blob = _tokenize(f"{s.title} {s.summary}")
        for cat, keys in categories.items():
            if any(k.lower() in blob for k in keys):
                hits[cat] += 1
                if len(exemplars[cat]) < args.max_results:
                    exemplars[cat].append(asdict(s))

    ranked = sorted(((c, hits[c]) for c in hits), key=lambda x: (-x[1], x[0]))
    forced_template = None
    if args.force_template:
        forced_template = template_for_name(str(args.force_template))
        if forced_template is None:
            raise SystemExit(f"Unknown template: {args.force_template}. Use --list-templates.")

    if args.force_category:
        picked = [str(args.force_category)]
    elif forced_template is not None:
        picked = [forced_template.category]
    else:
        picked = [c for c, n in ranked if n > 0][: args.max_categories]

    out_dir = _repo_root() / args.out_root / _utc_stamp()
    out_dir.mkdir(parents=True, exist_ok=True)

    # Build bundles for each picked category using default templates.
    from src.mecha_splicer.runner import run  # type: ignore
    from src.mecha_splicer.templates.mint_templates import spec_for_category, spec_for_template  # type: ignore

    report: Dict[str, Any] = {"picked_categories": picked, "ranked": ranked, "signals_total": len(signals), "bundles": []}
    (out_dir / "signals.json").write_text(json.dumps([asdict(s) for s in signals], indent=2), encoding="utf-8")
    for cat in picked:
        dir_name = str(forced_template.name) if forced_template is not None else str(cat)
        cat_dir = out_dir / dir_name
        cat_dir.mkdir(parents=True, exist_ok=True)

        if forced_template is not None:
            spec = spec_for_template(str(forced_template.name))
        else:
            spec = spec_for_category(cat)
        if not spec:
            continue
        # Per-category overrides file convention: config/sku_overrides_<category>.json
        per_cat_over = _repo_root() / "config" / f"sku_overrides_{cat}.json"
        use_overrides = args.sku_overrides
        if per_cat_over.exists():
            use_overrides = str(per_cat_over)
        elif use_overrides is None:
            # If example exists and nothing else is provided, copy it into bundle for editing.
            ex = _repo_root() / "config" / "sku_overrides_example.json"
            if ex.exists():
                (cat_dir / "SKU_OVERRIDES.json").write_text(ex.read_text(encoding="utf-8"), encoding="utf-8")
                use_overrides = str(cat_dir / "SKU_OVERRIDES.json")

        bundle = run(
            spec,
            out_dir=cat_dir,
            use_3d_splicer=bool(args.use_3d_splicer),
            render_stl=bool(args.render_stl),
            include_pricing=bool(args.include_pricing),
            sku_overrides_path=use_overrides,
            render_openscad_stl=bool(args.render_openscad_stl),
            openscad_docker_image=args.openscad_docker_image,
            report_currency=str(args.report_currency),
        )
        (cat_dir / "signals.json").write_text(json.dumps(exemplars.get(cat, []), indent=2), encoding="utf-8")
        (cat_dir / "spec.json").write_text(json.dumps(spec, indent=2), encoding="utf-8")
        report["bundles"].append({"category": cat, "template": (forced_template.name if forced_template else ""), "bundle": bundle})

    (out_dir / "mint.report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    _write_mint_summary(out_dir, report)
    _write_latest_pointer(_repo_root() / "dist_ready_for_sale", out_dir)
    _write_dist_bundle(_repo_root() / "dist_ready_for_sale", out_dir)
    print(json.dumps(report, indent=2))
    return 0


def _write_mint_summary(out_dir: Path, report: Dict[str, Any]) -> None:
    md = []
    md.append("# Mecha-Splicer Mint Summary\n")
    md.append(f"- Bundle root: `{out_dir}`")
    md.append(f"- Signals total: {report.get('signals_total')}")
    md.append(f"- Picked categories: {', '.join(report.get('picked_categories') or [])}\n")
    for b in report.get("bundles") or []:
        cat = b.get("category")
        md.append(f"## {cat}")
        md.append(f"- Path: `{out_dir / str(cat)}`")
        md.append(f"- Outputs: `{', '.join((b.get('bundle') or {}).get('outputs') or [])}`")
        if (b.get("bundle") or {}).get("procurement"):
            md.append(f"- Est. COGS (USD): {(b.get('bundle') or {}).get('procurement', {}).get('cogs_usd')}")
        md.append("")
    (out_dir / "MINT_SUMMARY.md").write_text("\n".join(md).strip() + "\n", encoding="utf-8")


def _write_latest_pointer(dist_dir: Path, out_dir: Path) -> None:
    dist_dir.mkdir(parents=True, exist_ok=True)
    p = dist_dir / "mecha_splicer_mint.latest.md"
    p.write_text(f"# Latest Mecha-Splicer Mint\n\n- `{out_dir}`\n", encoding="utf-8")


def _write_dist_bundle(dist_dir: Path, out_dir: Path) -> None:
    """
    Copy the mint summary + signals list into dist_ready_for_sale for easy sharing.
    (We do not zip by default to avoid large binaries; the directory itself is the bundle.)
    """
    dist_dir.mkdir(parents=True, exist_ok=True)
    (dist_dir / "MINT_SUMMARY.latest.md").write_text((out_dir / "MINT_SUMMARY.md").read_text(encoding="utf-8"), encoding="utf-8")
    (dist_dir / "signals.latest.json").write_text((out_dir / "signals.json").read_text(encoding="utf-8"), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
