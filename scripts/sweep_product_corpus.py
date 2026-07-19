#!/usr/bin/env python3
"""Offline capability sweep across the exhaustive Enabot-depth product corpus.

Default: fast salvage-package scoring for every product.
Optional: --compile-candidates runs KiCad compile on flagged products only.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Set

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

os.environ.setdefault("HARDWARE_SPLICER_OFFLINE_LLM", "1")
os.environ.setdefault("HARDWARE_SPLICER_OFFLINE_VISION", "1")
os.environ.setdefault("HARDWARE_SPLICER_OFFLINE_SALVAGE", "1")
os.environ.setdefault("QWEN_DISABLED", "1")
os.environ.setdefault("HARDWARE_SPLICER_SKIP_VISION_LIVE", "1")

from hardware_splicer.integrations.build_id_hints import keyword_build_id
from hardware_splicer.project_intake import splice_and_build_from_intake
from hardware_splicer.salvage_bridge import build_intake_salvage_package

GENERIC = {"generic_low_voltage_build", "", None}


def _inventory_ids(parts: List[Mapping[str, Any]], resolved: List[Mapping[str, Any]]) -> Set[str]:
    ids = {str(p.get("module_id") or "") for p in parts if p.get("module_id")}
    ids |= {str(r.get("module_id") or "") for r in resolved if r.get("module_id")}
    ids.discard("")
    return ids


def _score_package(product: Mapping[str, Any], package: Mapping[str, Any]) -> Dict[str, Any]:
    resolved = list(package.get("resolved_modules") or [])
    gap = dict(package.get("gap_analysis") or {})
    shopping = list(gap.get("shopping_list") or [])
    still_missing = list(gap.get("still_missing") or [])
    build_id = package.get("recommended_build_id") or package.get("build_id")
    preferred = list(product.get("preferred_build_ids") or [])
    inv = _inventory_ids(list(product.get("available_parts") or []), resolved)

    roles = {str(r.get("role") or "") for r in resolved if r.get("role")}
    module_ids = {str(r.get("module_id") or "") for r in resolved if r.get("module_id")}
    sources = {str(r.get("source") or "") for r in resolved}

    shop_ids = {str(s.get("module_id") or "") for s in shopping}
    dishonest = sorted(shop_ids & inv)

    donor_bound = any(
        str(r.get("source") or "") in {"donor_functional_salvage", "circuit_functional_salvage"}
        for r in resolved
    )
    gap_fill_driver = any(
        str(r.get("source") or "") == "gap_fill" and str(r.get("role") or "") == "drv" for r in resolved
    )

    keyword = keyword_build_id(
        str(product.get("goal") or ""),
        list(product.get("available_parts") or []),
    )

    family_hit = bool(preferred and build_id in preferred)
    routed = build_id not in GENERIC
    mcu_ok = "mcu" in roles or any(
        mid in module_ids for mid in ("esp32-devkit", "esp32-cam-module", "arduino-nano", "rpi-pico")
    )
    act_ok = bool(roles & {"drv", "act", "load", "mot"}) or bool(
        module_ids
        & {
            "l298n",
            "mosfet-irlz44n",
            "relay-1ch-5v",
            "a4988-stepper",
            "sg90",
            "mini-pump-5v",
            "cooling_fan_5v",
        }
    )
    ready = bool(gap.get("ready_to_compile"))

    # Grade
    checks = {
        "routed_non_generic": routed,
        "family_match": family_hit if preferred else routed,
        "mcu_resolved": mcu_ok,
        "actuator_or_driver_path": act_ok,
        "shopping_honest": not dishonest,
        "ready_to_compile": ready,
        "no_driver_gap_fill_when_donor": (not product.get("donor_fixture")) or (donor_bound and not gap_fill_driver),
    }
    passed = sum(1 for v in checks.values() if v)
    total = len(checks)
    score = round(100.0 * passed / total, 1)

    if score >= 85 and routed and mcu_ok and not dishonest:
        grade = "A"
    elif score >= 70:
        grade = "B"
    elif score >= 50:
        grade = "C"
    else:
        grade = "D"

    return {
        "product_id": product.get("id"),
        "family": product.get("family"),
        "build_id": build_id,
        "keyword_build_id": keyword,
        "preferred_build_ids": preferred,
        "family_match": family_hit,
        "grade": grade,
        "score": score,
        "checks": checks,
        "roles": sorted(roles),
        "module_ids": sorted(module_ids),
        "shopping": sorted(shop_ids),
        "still_missing": [str(s.get("module_id") or "") for s in still_missing],
        "dishonest_shopping": dishonest,
        "donor_bound": donor_bound,
        "gap_fill_driver": gap_fill_driver,
        "power_topology": package.get("power_topology"),
        "ready_to_compile": ready,
        "sources": sorted(sources),
    }


def _run_one(product: Mapping[str, Any], *, compile_it: bool, out_dir: Path) -> Dict[str, Any]:
    goal = str(product.get("goal") or "")
    parts = list(product.get("available_parts") or [])
    constraints = dict(product.get("constraints") or {})
    donor_context = None
    if product.get("circuit") or product.get("functional_salvage"):
        donor_context = {
            "circuit": product.get("circuit"),
            "functional_salvage": product.get("functional_salvage"),
        }

    t0 = time.time()
    if compile_it:
        intake = {
            "project_name": product.get("id"),
            "goal": goal,
            "salvage_mode": True,
            "available_parts": parts,
            "constraints": constraints,
        }
        if product.get("circuit"):
            intake["circuit"] = product["circuit"]
        result = splice_and_build_from_intake(
            intake,
            out_dir=out_dir / str(product["id"]),
            export_gerber=False,
            request_id=f"sweep_{product['id']}",
        )
        package = dict(result.get("salvage_package") or {})
        score = _score_package(product, package)
        score["compile_ok"] = bool(result.get("ok"))
        score["compile_build_ready"] = bool((result.get("design_quality_gate") or {}).get("build_ready"))
        score["elapsed_s"] = round(time.time() - t0, 3)
        if score["compile_ok"] and score["grade"] in {"A", "B"}:
            score["grade"] = score["grade"]  # keep
        elif not score["compile_ok"] and score["grade"] == "A":
            score["grade"] = "B"
        return score

    package = build_intake_salvage_package(
        goal=goal,
        parts=parts,
        constraints=constraints,
        project_name=str(product.get("id") or "product"),
        donor_context=donor_context,
    )
    score = _score_package(product, package)
    score["compile_ok"] = None
    score["elapsed_s"] = round(time.time() - t0, 3)
    return score


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--corpus",
        type=Path,
        default=ROOT / "examples" / "product_corpus" / "enabot_depth_corpus.json",
    )
    parser.add_argument("--out", type=Path, default=Path("/tmp/hs_product_corpus_sweep"))
    parser.add_argument("--family", action="append", default=[], help="Filter family (repeatable)")
    parser.add_argument("--limit", type=int, default=0, help="Limit products (debug)")
    parser.add_argument("--compile-candidates", action="store_true")
    parser.add_argument("--compile-all-flagged", action="store_true", help="same as --compile-candidates")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if not args.corpus.is_file():
        gen = ROOT / "scripts" / "generate_product_corpus.py"
        print(f"Corpus missing; run: python {gen}", file=sys.stderr)
        return 2

    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    products = list(corpus.get("products") or [])
    if args.family:
        want = set(args.family)
        products = [p for p in products if p.get("family") in want]
    if args.limit and args.limit > 0:
        products = products[: args.limit]

    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    do_compile = bool(args.compile_candidates or args.compile_all_flagged)

    rows: List[Dict[str, Any]] = []
    for i, product in enumerate(products, 1):
        compile_it = do_compile and bool(product.get("compile_candidate"))
        try:
            row = _run_one(product, compile_it=compile_it, out_dir=out / "builds")
        except Exception as exc:  # noqa: BLE001 — sweep must continue
            row = {
                "product_id": product.get("id"),
                "family": product.get("family"),
                "grade": "F",
                "score": 0,
                "error": str(exc),
                "checks": {},
            }
        rows.append(row)
        if i % 25 == 0 or i == len(products):
            print(f"… {i}/{len(products)}", flush=True)

    grades = Counter(r.get("grade") for r in rows)
    by_family: Dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        by_family[str(r.get("family") or "?")][str(r.get("grade") or "?")] += 1

    build_ids = Counter(r.get("build_id") or "none" for r in rows)
    weak = [r for r in rows if r.get("grade") in {"C", "D", "F"}]
    strong = [r for r in rows if r.get("grade") in {"A", "B"}]

    check_rates: Dict[str, float] = {}
    if rows:
        keys = set()
        for r in rows:
            keys |= set((r.get("checks") or {}).keys())
        for k in sorted(keys):
            vals = [(r.get("checks") or {}).get(k) for r in rows if r.get("checks")]
            vals = [v for v in vals if v is not None]
            check_rates[k] = round(100.0 * sum(1 for v in vals if v) / max(len(vals), 1), 1)

    report = {
        "schema_version": "hardware_splicer.product_corpus_sweep.v1",
        "corpus_path": str(args.corpus),
        "product_count": len(rows),
        "compile_mode": do_compile,
        "grades": dict(grades),
        "strong_count": len(strong),
        "weak_count": len(weak),
        "strong_pct": round(100.0 * len(strong) / max(len(rows), 1), 1),
        "check_pass_rates_pct": check_rates,
        "top_build_ids": build_ids.most_common(20),
        "grades_by_family": {fam: dict(c) for fam, c in sorted(by_family.items())},
        "weak_products": [
            {
                "id": r.get("product_id"),
                "family": r.get("family"),
                "grade": r.get("grade"),
                "build_id": r.get("build_id"),
                "preferred": r.get("preferred_build_ids"),
                "failed_checks": [k for k, v in (r.get("checks") or {}).items() if not v],
                "dishonest_shopping": r.get("dishonest_shopping"),
                "error": r.get("error"),
            }
            for r in sorted(weak, key=lambda x: (x.get("grade") or "", x.get("product_id") or ""))
        ],
        "rows": rows,
    }

    report_path = out / "PRODUCT_CORPUS_SWEEP.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    # Human summary markdown
    md = [
        "# Product corpus sweep",
        "",
        f"- Products: **{len(rows)}**",
        f"- Strong (A/B): **{len(strong)}** ({report['strong_pct']}%)",
        f"- Weak (C/D/F): **{len(weak)}**",
        f"- Grades: `{dict(grades)}`",
        "",
        "## Check pass rates",
        "",
    ]
    for k, v in check_rates.items():
        md.append(f"- `{k}`: {v}%")
    md.extend(["", "## Grades by family", ""])
    for fam, c in sorted(by_family.items()):
        md.append(f"- **{fam}**: {dict(c)}")
    md.extend(["", "## Weakest products (first 40)", ""])
    for r in report["weak_products"][:40]:
        md.append(
            f"- `{r['id']}` [{r['grade']}] → `{r.get('build_id')}` "
            f"failed={r.get('failed_checks')}"
        )
    summary_path = out / "PRODUCT_CORPUS_SWEEP.md"
    summary_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps({k: report[k] for k in report if k != "rows"}, indent=2))
    else:
        print(f"Sweep: {len(strong)}/{len(rows)} strong (A/B) = {report['strong_pct']}%")
        print(f"grades: {dict(grades)}")
        print(f"report: {report_path}")
        print(f"summary: {summary_path}")
        print("check pass %:", check_rates)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
