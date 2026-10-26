"""Reproducible 31-record commercial replay from pinned HS branch snapshots.

Run: python scripts/replay_hs_commercial_portfolio.py --output-dir /tmp/hs-portfolio
No network, purchases, scraping, supplier communication, or fabrication.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


def dossier() -> dict:
    source = ROOT / "scripts" / "converge_commercial_sources.py"
    args = [
        sys.executable, str(source),
        "--donor-discovery", str(EXAMPLES / "commercial_tw_donor_discovery_snapshot_2026-10-19.json"),
        "--purchase-report", str(EXAMPLES / "commercial_tw_salvage_five_screen_snapshot.json"),
        "--regional-scan", str(EXAMPLES / "commercial_tw_cn_regional_scan_snapshot.json"),
        "--pf-run", str(EXAMPLES / "commercial_pf001_proofpod_snapshot.json"),
        "--pf-run", str(EXAMPLES / "commercial_pf002_benchhmi_snapshot.json"),
        "--pf-run", str(EXAMPLES / "commercial_pf003_fielddeck_snapshot.json"),
        "--case", str(EXAMPLES / "commercial_pf002_itemized_scenario_twd.json"),
        "--market-evidence", str(EXAMPLES / "commercial_market_evidence_tsc_historical.json"),
        "--external-observations", str(EXAMPLES / "commercial_external_market_observations_2026-10-26.json"),
        "--institutional-disposal", str(EXAMPLES / "commercial_taiwan_institutional_auctions_2026-10-26.json"),
        "--identity-claims", str(EXAMPLES / "commercial_t620_identity_conflict_2026-10-26.json"),
        "--repair-stress", str(EXAMPLES / "commercial_tsc_printhead_cost_stress_2026-10-26.json"),
        "--as-of", "2026-10-25",
    ]
    done = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=60)
    if done.returncode:
        raise RuntimeError(f"commercial convergence refused input: {done.stderr[-2000:]}")
    result = json.loads(done.stdout)
    cohort = result["cohort_review"]
    if (cohort["total_source_records"] != 31
            or cohort["distinct_named_concepts_after_known_lineage_aliases"] != 30
            or result.get("purchase_authorized") is not False):
        raise RuntimeError("unexpected cohort size, source alias or purchase authority")
    return result


def _fmt(value: object) -> str:
    if value is None:
        return "not priced"
    if isinstance(value, (int, float)):
        return f"{value:,.0f}" if float(value).is_integer() else f"{value:,.2f}"
    return str(value)


def markdown(report: dict) -> str:
    c = report["cohort_review"]
    sources = c["records"]
    salvage = [r for r in sources if r["source_class"] == "salvage_economics"]
    donors = [r for r in sources if r["source_class"] == "used_equipment_marketplace"]
    pf = [r for r in sources if r["source_class"] == "product_factory"]
    regional = [r for r in sources if r["source_class"] == "historical_regional_product_route"]
    lines = [
        "# HS commercial portfolio replay — source snapshot, not a market forecast",
        "",
        "**Authority:** DISCOVERY / RESEARCH ONLY. No supplier quote, sale, acquisition or physical manufacturing is proven.",
        "",
        "Input date(s): Sep 23–26 and Oct 19 2026. Historical asks may be stale or inaccessible. No live marketplace revalidation was performed.",
        "",
        "## Full-portfolio coverage",
        "",
        f"- Source records: **{c['total_source_records']}**; lineage-deduplicated named concepts: **{c['distinct_named_concepts_after_known_lineage_aliases']}**.",
        f"- Taiwan marketplace donor observations (unpriced): **{len(donors)}**.",
        f"- Taiwan modeled salvage acquisition cases: **{len(salvage)}**; **{c['positive_modeled_salvage_screens']}** show positive paper contribution, but only **{c['historical_models_meeting_original_profit_target']}** reaches the original NT$300 target, before real sold-price/yield verification.",
        f"- Product Factory experiments: **{len(pf)}**; regional Taiwan/China concepts: **{len(regional)}**.",
        "- The PF-002 itemized scenario is a separate **modeled route** for an already counted concept, not another independent business.",
        "",
        "## Five existing acquisition screens: modeled, not measured",
        "",
        "| Candidate | Proposed ask (NT$) | Expected net per acquisition (NT$) | Bid ceiling at target profit (NT$) | Positive sensitivities | Disposition |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in sorted(salvage, key=lambda x: x["modeled_net"], reverse=True):
        lines.append(
            f"| {row['candidate_id']} | {_fmt(row['source_ask'])} | "
            f"{_fmt(row['modeled_net'])} | {_fmt(row['modeled_bid_at_target_profit'])} | "
            f"{row['downside_wins_of_nine']}/9 | {row['decision']} |"
        )
    lines += [
        "",
        "**No salvage case has verified completed sales, a measured yield or a purchase authorization.**",
        "A positive expectation is not approval to buy. The TSC printer requires printhead verification; the QL-800's NT$24 margin is below the original NT$300 profit target.",
        "",
        "## Seventeen Taiwan donor observations: no plausible net computed",
        "",
        "| Device ID | Family | Historical advertised ask (NT$) | Evidence and action |",
        "| --- | --- | ---: | --- |",
    ]
    for row in donors:
        lo, hi = row.get("source_ask_range", (None, None)) if row.get("source_ask_range") else (None, None)
        # Cohort source retains prices as historical listing evidence; not sold comps.
        range_text = "unknown"
        if lo is not None:
            range_text = _fmt(lo) if lo == hi else f"{_fmt(lo)}–{_fmt(hi)}"
        link = row.get("source_url")
        label = row["candidate_id"]
        if link:
            label = f"[{label}]({link})"
        lines.append(f"| {label} | {row.get('family') or 'unknown'} | {range_text} | UNPRICED / verify donor and sold comparables |")
    lines += [
        "",
        "## Product Factory and wider Taiwan/China routes",
        "",
        "| Candidate | Market | Native currency | Price quality | Next evidence |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in pf + regional:
        next_gap = row["missing_evidence"][0]
        lines.append(
            f"| {row['candidate_id']} | {row['market']} | {row['currency']} | "
            f"{row['price_evidence']} | {next_gap} |"
        )
    lines += [
        "",
        "## Itemized PF-002 (BenchHMI) illustrative build route",
        "",
    ]
    for case in report["commercial_cases"]["cases"]:
        for route in case.get("routes") or []:
            lines.append(
                f"- {case['candidate_id']} / {route['route_id']}: "
                f"expected proceeds {_fmt(route['expected_proceeds'])} {case['currency']}; "
                f"total modeled costs {_fmt(route['total_cost'])}; "
                f"modeled net {_fmt(route['net_value'])}; status **{route['status']}**."
            )
            lines.append(
                f"- Missing: {', '.join((route.get('blockers') or [])[:10])}."
            )
    identity = report.get("identity_audits") or []
    repair = report.get("repair_cost_stress_tests") or []
    lines += [
        "",
        "## Explicit price and machine-identity disqualifiers",
        "",
    ]
    for item in identity:
        lines.append(
            f"- Device {item['candidate_id']}: **{item['status']}**; "
            f"{len(item['conflicts'])} source conflicts and no physical verification."
        )
        for conflict in item["conflicts"]:
            lines.append(
                f"  - {conflict['attribute']}: seller claims "
                f"{conflict['seller_claim']} vs technical reference "
                f"{conflict['manufacturer_claim']}. "
                f"[Seller]({conflict['seller_source']}) / "
                f"[Reference]({conflict['manufacturer_source']})."
            )
    for item in repair:
        lines.append(
            f"- {item['candidate_id']}: replacement part listing "
            f"NT$ {item['listing_replacement_range'][0]:,.0f}–"
            f"{item['listing_replacement_range'][1]:,.0f} would imply "
            f"NT$ {item['modeled_profit_if_head_required_on_each_success'][0]:,.0f} to "
            f"{item['modeled_profit_if_head_required_on_each_success'][1]:,.0f} "
            f"expected net under the stated conditional assumptions; **{item['status']}**. "
            f"[Parts listing]({item['source_url']})."
        )
    observations = report.get("external_market_observation_reports") or []
    lines += ["", "## Newly procured public market data — 2026-10-26", ""]
    for observed in observations:
        lines += [
            f"- **{observed['total_observations']}** distinct source-price observations "
            f"covering **{observed['distinct_candidates_with_observations']}** hardware concepts.",
            f"- Native markets: {observed['market_counts']}. "
            f"Seller-advertised prices and retailer catalog prices only; **0 verified sold transactions, 0 signed supplier quotes, 0 authenticated stock**.",
            "",
            "| Observation | Candidate | Market | Type | Indexed price | Source |",
            "| --- | --- | --- | --- | ---: | --- |",
        ]
        for item in observed["records"]:
            lo = item["price_min"]
            hi = item["price_max"]
            amt = (f"{_fmt(lo)}+" if hi is None else _fmt(lo) if lo == hi
                   else f"{_fmt(lo)}–{_fmt(hi)}")
            lines.append(
                f"| {item['evidence_id']} | {item['candidate_id']} | {item['currency']} | "
                f"{item['kind']} | {amt} | [Seller / catalog]({item['source_url']}) |"
            )
        lines += [
            "",
            "**None of these records is an accepted resale comparable or purchase quote.** "
            "Taobao aggregators and old listings cannot establish viable arbitrage without "
            "exact condition, unit option, shipping, landed costs and delivered-sale verification.",
        ]
    disposal = report.get("institutional_disposal_reports") or []
    lines += ["", "## Institutional surplus and regulated waste-auction sourcing", ""]
    for report_a in disposal:
        lines.append(
            f"Research records: **{report_a['count']}**, all source-evidence only; "
            "0 authorized auction bids or licensed handling permissions."
        )
        for item in report_a["auctions"]:
            lines.append(
                f"- {item['agency']}: **{item['status']}**, "
                f"{item['asset_class']} — [agency/notice]({item['source_url']})."
            )
    lines.append(
        "Some closed school scrap tenders require registered qualified recycling businesses "
        "and deposits; a public scrap lot is not automatically an accessible used-product purchase."
    )
    backlog = report["validation_backlog"]
    lines += [
        "",
        "## Diversified validation wave (research, not inventory acquisition)",
        "",
        f"After source-lineage consolidation: **{backlog['record_count']} named concepts**, "
        f"**{backlog['unpriced_concepts']} without an economic model**. "
        "All remain unverified business hypotheses.",
        "",
        "| Concept | Native currency | Review priority | Next evidence |",
        "| --- | --- | --- | --- |",
    ]
    indexed = {row["concept_id"]: row for row in backlog["entries"]}
    for cid in backlog["first_evidence_wave"]:
        row = indexed[cid]
        lines.append(
            f"| {cid} | {', '.join(row['native_currencies']) or 'unknown'} | "
            f"{row['priority_tier']} | {row['next_verification']} |"
        )
    lines += [
        "",
        "Price observations with unverified variants, marketplace sold markers "
        "without settlement evidence, or unrelated models are excluded from verified comparisons.",
    ]
    lines += [
        "",
        "## Near-term execution order",
        "",
        "1. Obtain **same-model completed sales** and a fault/printhead check for TSC TTP-244 Plus, before considering even a sample purchase.",
        "2. Qualify **one actual supplier-donor lot** for an industrial compute/POS/HMI concept; do not convert historical target prices to profits.",
        "3. Verify exact model, components, parts yield and transport costs for the lowest-acquisition-price Ruten listings, prioritizing inspectable low-voltage and nonregulated goods.",
        "4. Compare Taiwan and China sourcing only in native currencies until dated FX, customs, shipping and tax are added.",
        "5. For every candidate, calculate buy-and-sell, repair, disassemble, transform and own/operate value **only when required cost and output evidence exists**.",
        "6. Accept a paid customer requirement or measured productive use as validation; no automatic purchases or manufacturing.",
        "",
        "## Boundaries",
        "",
        "- Historical marketplace asking prices are not available stock, sold comparables or negotiated quotations.",
        "- Workstream count is not profit opportunity count; duplicate or related equipment concepts may share supply constraints.",
        "- A down-selected hypothesis remains only a research case until it has procurement, engineering, lawful ownership and actual demand/output evidence.",
        "- For regulated e-waste and risky mains/battery components, require appropriate professional/legal handling.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    report = dossier()
    outdir = args.output_dir
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "commercial_cohort_replay.json").write_text(
        json.dumps(report, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (outdir / "commercial_cohort_replay.md").write_text(markdown(report), encoding="utf-8")
    (outdir / "institutional_disposal_diligence.json").write_text(
        json.dumps(report.get("institutional_disposal_reports") or [], sort_keys=True,
                   indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (outdir / "commercial_external_market_diligence.json").write_text(
        json.dumps(report.get("external_market_observation_reports") or [], sort_keys=True,
                   indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (outdir / "commercial_validation_packets.json").write_text(
        json.dumps(report.get("validation_packets") or {}, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "source_records": report["cohort_review"]["total_source_records"],
        "unique_named_concepts": report["cohort_review"]["distinct_named_concepts_after_known_lineage_aliases"],
        "priced_salvage_models": report["cohort_review"]["historically_priced_salvage_screens"],
        "modeled_positive": report["cohort_review"]["positive_modeled_salvage_screens"],
        "modeled_at_target": report["cohort_review"]["historical_models_meeting_original_profit_target"],
        "deduplicated_validation_cases": report["validation_backlog"]["record_count"],
        "first_evidence_wave_count": len(report["validation_backlog"]["first_evidence_wave"]),
        "purchase_authorized": False,
        "output_dir": str(outdir),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
