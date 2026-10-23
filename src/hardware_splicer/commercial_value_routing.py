"""Evidence-gated commercial routing over existing HS engineering and salvage outputs.

This does NOT authorize acquisition, fabrication, power-on, sales or investment.
Production unit economics are distinct from derivative DEVELOPMENT economics.
Native currencies remain segregated; no implicit foreign-exchange conversions.
"""
from __future__ import annotations

import math
from typing import Any, Mapping

SCHEMA = "hardware_splicer.commercial_value_case.v1"
CURRENCIES = frozenset({"TWD", "CNY", "IDR", "USD"})
ACTIONS = frozenset({
    "resell", "refurbish", "recover_parts", "build_product",
    "operate", "replicate", "recycle",
})
COSTS = (
    "acquisition", "material_and_fab", "engineering", "labor",
    "quality", "freight_and_tax", "sales_and_payment", "warranty_and_returns",
)
EVIDENCE = frozenset({"UNKNOWN", "HYPOTHESIS", "ESTIMATED", "QUOTED", "MEASURED", "INVALID"})
STRONG_EVIDENCE = frozenset({"QUOTED", "MEASURED"})
RELEASE_GATES = (
    "physical_test_passed", "rights_cleared", "compliance_cleared",
    "procurement_verified",
)
SALES_GATES = ("buyer_committed",)
OPERATE_GATES = ("site_or_use_rights_cleared", "operational_benefit_verified")


def _amount(item: Any, field: str, errors: list[str], *, signed: bool = False) -> float | None:
    if not isinstance(item, Mapping):
        errors.append(f"missing_money:{field}")
        return None
    status = item.get("evidence_class")
    if status not in EVIDENCE or status in {"UNKNOWN", "INVALID"}:
        errors.append(f"unsupported_evidence:{field}")
    if status in STRONG_EVIDENCE and not str(item.get("reference") or "").strip():
        errors.append(f"missing_reference:{field}")
    raw = item.get("amount")
    if isinstance(raw, bool):
        errors.append(f"invalid_amount:{field}")
        return None
    try:
        num = float(raw)
    except (ValueError, TypeError):
        errors.append(f"invalid_amount:{field}")
        return None
    if not math.isfinite(num) or (not signed and num < 0):
        errors.append(f"invalid_amount:{field}")
        return None
    return num


def _fraction(item: Any, field: str, errors: list[str], default: float | None = None) -> float | None:
    if item is None:
        if default is None:
            errors.append(f"missing_fraction:{field}")
        return default
    if isinstance(item, bool):
        errors.append(f"invalid_fraction:{field}")
        return None
    try:
        num = float(item)
    except (ValueError, TypeError):
        errors.append(f"invalid_fraction:{field}")
        return None
    if not math.isfinite(num) or num < 0 or num > 1:
        errors.append(f"invalid_fraction:{field}")
        return None
    return num


def _gate_blockers(route: Mapping[str, Any], *, action: str) -> list[str]:
    gates = route.get("gates") if isinstance(route.get("gates"), Mapping) else {}
    refs = route.get("gate_references") if isinstance(route.get("gate_references"), Mapping) else {}
    missing = []
    required = RELEASE_GATES + (OPERATE_GATES if action == "operate" else SALES_GATES)
    for gate in required:
        if gates.get(gate) is not True or not str(refs.get(gate) or "").strip():
            missing.append(f"unproven_gate:{gate}")
    return missing


def evaluate_route(route: Mapping[str, Any], *, currency: str, min_margin: float = 0.30) -> dict[str, Any]:
    """Price one route per acquired asset. Never convert currency or grant purchase authority."""
    errors: list[str] = []
    route_id = str(route.get("route_id") or "")
    action = str(route.get("action") or "")
    if not route_id:
        errors.append("missing_route_id")
    if action not in ACTIONS:
        errors.append("unsupported_action")
    if route.get("currency") != currency:
        errors.append("currency_mismatch")
    min_margin = _fraction(min_margin, "min_margin", errors)
    expenses = route.get("expenses") if isinstance(route.get("expenses"), Mapping) else {}
    amounts: dict[str, float] = {}
    for key in COSTS:
        value = _amount(expenses.get(key), f"expenses.{key}", errors)
        if value is not None:
            amounts[key] = value
    # Prevent a missing line-item from silently becoming zero.
    cost = sum(amounts.values()) if len(amounts) == len(COSTS) else None

    p = _fraction(route.get("success_probability"), "success_probability", errors)
    probability_evidence = route.get("probability_evidence")
    if probability_evidence not in EVIDENCE or probability_evidence in {"UNKNOWN", "INVALID"}:
        errors.append("missing_probability_evidence")
    sale_value: float | None = None
    failure_value: float | None = None
    discounted_proceeds: float | None = None

    if action == "operate":
        flows = route.get("monthly_net_cashflows")
        rate = _fraction(route.get("monthly_discount_rate"), "monthly_discount_rate", errors)
        terminal = _amount(route.get("terminal_value"), "terminal_value", errors)
        if not isinstance(flows, list) or not flows:
            errors.append("missing_monthly_net_cashflows")
        else:
            parsed_flows = [
                _amount(item, f"monthly_net_cashflows.{i}", errors, signed=True)
                for i, item in enumerate(flows, 1)
            ]
            if rate is not None and terminal is not None and all(v is not None for v in parsed_flows):
                discounted_proceeds = sum(
                    v / (1 + rate) ** i for i, v in enumerate(parsed_flows, 1)
                ) + terminal / (1 + rate) ** len(parsed_flows)
        if p is not None and p != 1:
            errors.append("operating_risk_requires_explicit_scenarios")
    else:
        sale_value = _amount(route.get("sale_proceeds"), "sale_proceeds", errors)
        if p is not None and p < 1:
            failure_value = _amount(route.get("failure_proceeds"), "failure_proceeds", errors)
        elif p == 1:
            failure_value = 0.0
        if p is not None and sale_value is not None and failure_value is not None:
            discounted_proceeds = p * sale_value + (1 - p) * failure_value

    blockers = _gate_blockers(route, action=action)
    if action == "operate":
        # Operating output is not a confirmed sale and cannot use sale-margin terminology.
        metric_name = "net_present_value"
    else:
        metric_name = "expected_contribution"
    if cost is not None and not math.isfinite(cost):
        errors.append("nonfinite_aggregated_cost")
    if discounted_proceeds is not None and not math.isfinite(discounted_proceeds):
        errors.append("nonfinite_aggregated_proceeds")
    result: dict[str, Any] = {
        "route_id": route_id,
        "action": action,
        "currency": currency,
        "metric": metric_name,
        "status": "INVALID" if errors else "UNPRICED",
        "errors": sorted(set(errors)),
        "blockers": blockers,
        "purchase_authorized": False,
        "ready_for_human_commercial_review": False,
        "expected_proceeds": round(discounted_proceeds, 2) if discounted_proceeds is not None and math.isfinite(discounted_proceeds) else None,
        "total_cost": round(cost, 2) if cost is not None and math.isfinite(cost) else None,
        "net_value": None,
        "margin": None,
        "break_even_bid": None,
        "bid_ceiling_at_target_margin": None,
        "sale_price_minus_20pct": None,
        "sale_price_plus_20pct": None,
        "success_net_if_acquired": None,
        "failure_net_if_acquired": None,
        "evpi_upper_bound": None,
    }
    if errors or cost is None or discounted_proceeds is None or min_margin is None:
        return result

    net = discounted_proceeds - cost
    result["net_value"] = round(net, 2)
    result["break_even_bid"] = round(max(0, discounted_proceeds - (cost - amounts["acquisition"])), 2)
    if action != "operate" and p is not None and sale_value is not None and failure_value is not None:
        success_net = sale_value - cost
        failure_net = failure_value - cost
        # Decision-theoretic value of PERFECT pre-purchase knowledge, when a
        # no-buy outcome costs exactly zero. This is a theoretical upper bound
        # on information spending, not a forecast of AI recognition value.
        perfect_info = p * max(0.0, success_net) + (1 - p) * max(0.0, failure_net)
        evpi = max(0.0, perfect_info - max(0.0, net))
        result["success_net_if_acquired"] = round(success_net, 2)
        result["failure_net_if_acquired"] = round(failure_net, 2)
        result["evpi_upper_bound"] = round(evpi, 2)
    if action != "operate" and discounted_proceeds > 0 and p is not None and sale_value is not None:
        result["margin"] = round(net / discounted_proceeds, 6)
        result["bid_ceiling_at_target_margin"] = round(
            max(0, discounted_proceeds * (1 - min_margin) - (cost - amounts["acquisition"])), 2
        )
        result["sale_price_minus_20pct"] = round(
            p * (sale_value * 0.8) + (1 - p) * failure_value - cost, 2
        )
        result["sale_price_plus_20pct"] = round(
            p * (sale_value * 1.2) + (1 - p) * failure_value - cost, 2
        )
    # Lack of credible quotation/buyer evidence can never be papered over by margin.
    strong_cost = all(
        isinstance(expenses.get(key), Mapping)
        and expenses[key].get("evidence_class") in STRONG_EVIDENCE
        and str(expenses[key].get("reference") or "").strip()
        for key in ("acquisition", "material_and_fab")
    )
    buyer = route.get("sale_proceeds") if isinstance(route.get("sale_proceeds"), Mapping) else {}
    if action == "operate":
        flows = route.get("monthly_net_cashflows") or []
        terminal = route.get("terminal_value") or {}
        strong_proceeds = (
            bool(flows) and all(
                isinstance(x, Mapping) and x.get("evidence_class") == "MEASURED"
                and str(x.get("reference") or "").strip()
                for x in flows
            )
            and isinstance(terminal, Mapping)
            and terminal.get("evidence_class") in STRONG_EVIDENCE
            and bool(str(terminal.get("reference") or "").strip())
        )
    else:
        strong_proceeds = (
            buyer.get("evidence_class") in STRONG_EVIDENCE
            and bool(str(buyer.get("reference") or "").strip())
        )
    result["blockers"] = blockers + (
        ([] if strong_cost else ["unquoted_core_cost"])
        + ([] if strong_proceeds else [
            "unverified_operating_output" if action == "operate" else "unverified_buyer_price"
        ])
        + ([] if probability_evidence in STRONG_EVIDENCE else ["unverified_yield"])
        + ([] if (net > 0 and (action == "operate" or result["margin"] >= min_margin))
         else ["economics_below_gate"])
    )
    result["status"] = "REVIEW_READY" if not result["blockers"] else "SCREENING_ONLY"
    result["ready_for_human_commercial_review"] = not bool(result["blockers"])
    return result


def evaluate_commercial_case(case: Mapping[str, Any]) -> dict[str, Any]:
    """Screen routes for one candidate; DO NOT rank different currencies together."""
    errors: list[str] = []
    if case.get("schema_version") != SCHEMA:
        errors.append("unsupported_schema")
    currency = case.get("currency")
    if currency not in CURRENCIES:
        errors.append("unsupported_currency")
    candidate_id = str(case.get("candidate_id") or "")
    if not candidate_id:
        errors.append("missing_candidate_id")
    routes = case.get("routes")
    if not isinstance(routes, list) or not routes:
        errors.append("missing_routes")
    if errors:
        return {"candidate_id": candidate_id, "currency": currency, "status": "INVALID",
                "errors": errors, "routes": [], "purchase_authorized": False}
    margin_errors: list[str] = []
    margin = _fraction(case.get("target_contribution_margin", 0.30), "target_margin", margin_errors)
    if margin_errors or margin is None:
        return {"candidate_id": candidate_id, "currency": currency, "status": "INVALID",
                "errors": margin_errors, "routes": [], "purchase_authorized": False}
    evaluations = [evaluate_route(r, currency=currency, min_margin=margin) for r in routes]
    ids = [r["route_id"] for r in evaluations]
    if len(ids) != len(set(ids)):
        errors.append("duplicate_route_id")
    ranked = sorted(
        [r for r in evaluations if r["net_value"] is not None],
        key=lambda r: r["net_value"], reverse=True,
    )
    metric_families = {r["metric"] for r in ranked}
    # A discounted stream of productive use is not directly ranked against a
    # one-off completed sale, even if the reported units are both NT dollars.
    mutually_comparable = len(metric_families) <= 1
    return {
        "candidate_id": candidate_id,
        "currency": currency,
        "market": case.get("market"),
        "status": "INVALID" if errors else (
            "REVIEW_READY" if any(r["status"] == "REVIEW_READY" for r in ranked)
            else "SCREENING_ONLY"
        ),
        "errors": errors,
        "routes": evaluations,
        "screening_rank": [r["route_id"] for r in ranked] if mutually_comparable else [],
        "best_screening_route": ranked[0]["route_id"] if ranked and mutually_comparable else None,
        "comparability_blockers": [] if mutually_comparable else ["mixed_operating_npv_and_sales_contribution"],
        "purchase_authorized": False,
        "limitations": [
            "screening ranks are not purchase, sale, or physical authorization",
            "operating NPV is comparable only at the same horizon and discount assumptions",
            "realized performance requires separate measured outcome records",
            "production economics do not establish development cost savings",
        ],
    }


def normalize_product_factory_run(run: Mapping[str, Any], *, source_ref: str) -> dict[str, Any]:
    """Read PF-001/002/003 without treating target MSRP or COGS as transactions."""
    metrics = run.get("metrics") or {}
    stages = {str(x.get("id")): str(x.get("state")) for x in run.get("stages", [])}
    return {
        "candidate_id": run.get("product_id"),
        "origin": "product_factory",
        "run_id": run.get("run_id"),
        "source_ref": source_ref,
        "stage_states": stages,
        "price_hypotheses": {
            k: {"amount": v, "evidence_class": "HYPOTHESIS", "reference": source_ref}
            for k, v in metrics.items()
            if ("msrp" in k or "cogs" in k or "donor" in k)
            and isinstance(v, (int, float)) and not isinstance(v, bool)
        },
        "physical_status": (run.get("authority") or {}).get("physical_correctness", "UNPROVEN"),
        "commercial_status": "DISCOVERY_ONLY",
        "purchase_authorized": False,
    }


def normalize_salvage_opportunities(report: Mapping[str, Any], *, source_ref: str) -> list[dict[str, Any]]:
    """Bridge Circuit-AI proposals; its estimated USD values are not market evidence."""
    source: Mapping[str, Any] = report
    if isinstance(report.get("final_report"), Mapping):
        source = report["final_report"]
    elif isinstance(report.get("report"), Mapping):
        source = report["report"]
    if isinstance(source.get("opportunity_report"), Mapping):
        source = source["opportunity_report"]
    out = []
    for item in source.get("opportunities") or []:
        if not isinstance(item, Mapping):
            continue
        out.append({
            "candidate_id": str(item.get("id") or ""),
            "origin": "circuit_ai_salvage",
            "source_ref": source_ref,
            "suggested_action": item.get("type"),
            "technical_score": item.get("score"),
            "value_hypothesis_usd": {
                "amount": item.get("estimated_output_value_usd"),
                "evidence_class": "HYPOTHESIS",
                "reference": source_ref,
            },
            "commercial_status": "UNPRICED",
            "purchase_authorized": False,
        })
    return out


def evaluate_portfolio(cases: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Group screenings by native currency, never aggregate incompatible FX units.

    A per-unit screening rank is not a return-on-capital, procurement approval,
    supply-volume forecast, or comparable operating annuity.
    """
    results = [evaluate_commercial_case(case) for case in cases]
    by_currency: dict[str, list[dict[str, Any]]] = {}
    for item in results:
        currency = item.get("currency")
        if currency not in CURRENCIES or item.get("status") == "INVALID":
            continue
        best_id = item.get("best_screening_route")
        matching = [route for route in item["routes"] if route["route_id"] == best_id]
        if not matching:
            continue
        best = matching[0]
        by_currency.setdefault(currency, []).append({
            "candidate_id": item["candidate_id"],
            "route_id": best_id,
            "expected_net_per_asset": best["net_value"],
            "metric": best["metric"],
            "evidence_status": best["status"],
            "purchase_authorized": False,
        })
    for rows in by_currency.values():
        rows.sort(key=lambda x: x["expected_net_per_asset"], reverse=True)
    return {
        "status": "SCREENING_ONLY",
        "cases": results,
        "native_currency_rankings": by_currency,
        "purchase_authorized": False,
        "limitations": [
            "no FX comparison or conversion performed",
            "per-asset expected net is not volume-adjusted profit or return on capital",
            "operating NPV and sales contribution require matched horizon assumptions",
            "rankings cannot grant purchasing or manufacturing authority",
        ],
    }


def normalize_donor_discovery(catalog: Mapping[str, Any], *, source_ref: str) -> list[dict[str, Any]]:
    """Import PR #148 discovery records without pretending to own the donor."""
    if catalog.get("schema_version") != "hardware_splicer.commerce_donor_discovery.v1":
        raise ValueError("requires the exact donor discovery schema")
    rows = catalog.get("records")
    if not isinstance(rows, list):
        raise ValueError("missing donor discovery records")
    out = []
    known: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping) or row.get("status") != "DISCOVERY_ONLY":
            raise ValueError("cannot promote donor discovery to tested inventory")
        uid = str(row.get("listing_id") or "")
        if not uid or uid in known:
            raise ValueError("missing or duplicate listing id")
        known.add(uid)
        low = row.get("advertised_ask_twd_min")
        high = row.get("advertised_ask_twd_max")
        if (isinstance(low, bool) or isinstance(high, bool)
                or not isinstance(low, (int, float))
                or not isinstance(high, (int, float))
                or not math.isfinite(low) or not math.isfinite(high)
                or low < 0 or high < low):
            raise ValueError("invalid advertised ask range")
        out.append({
            "candidate_id": uid,
            "origin": "taiwan_marketplace_donor_discovery",
            "family": row.get("family"),
            "source_ref": source_ref,
            "listing_url": row.get("source_url"),
            "currency": "TWD",
            "advertised_ask_range": [low, high],
            "ask_evidence_class": "HYPOTHESIS",
            "potential_parts_unverified": row.get("parts_hypotheses_unverified") or [],
            "commercial_status": "DISCOVERY_ONLY",
            "purchase_authorized": False,
        })
    return out


def normalize_salvage_purchase_screen(screen: Mapping[str, Any], *, source_ref: str) -> dict[str, Any]:
    """Preserve PR #147's granular bid math; do not rerun or reinterpret it."""
    if screen.get("schema_version") != "hardware_splicer.salvage_purchase_screen.v1":
        raise ValueError("requires the exact salvage purchase screen schema")
    if screen.get("purchase_authorized") is not False:
        raise ValueError("purchase screen cannot provide purchase authority")
    return {
        "candidate_id": screen.get("id"),
        "origin": "taiwan_salvage_purchase_screen",
        "source_ref": source_ref,
        "currency": "TWD",
        "priced_outcome": {
            "expected_net_per_acquired_unit": screen.get("expected_net_per_acquired_unit_twd"),
            "break_even_max_bid": screen.get("break_even_max_purchase_twd"),
            "target_profit_max_bid": screen.get("max_purchase_for_target_profit_twd"),
            "evidence_class": "ESTIMATED",
            "reference": source_ref,
        },
        "price_basis": screen.get("acquisition_price_basis"),
        "limitations": screen.get("required_evidence") or [],
        "commercial_status": "SCREENING_ONLY",
        "purchase_authorized": False,
    }
