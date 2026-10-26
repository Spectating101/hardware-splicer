"""Evidence-gated qualification of *direct* seller quotations for HS hardware.

Marketplace asks, search snippets and catalogs never become an actionable
purchase solely by appearing in an RFQ intake file. Quote qualification and
purchase authorization are distinct decisions.
"""
from __future__ import annotations

from datetime import date
from math import isfinite
from typing import Any, Mapping

SCHEMA = "hardware_splicer.procurement_quote.v1"
CURRENCY = {"Taiwan": "TWD", "China": "CNY", "Indonesia": "IDR"}
COST_KEYS = (
    "device_and_options", "shipping", "tax_and_duties", "test_labor",
    "repair_and_parts", "data_sanitization", "return_and_warranty",
    "environmental_handling",
)


def _monetary(value: Any, key: str, errors: list[str]) -> float | None:
    if isinstance(value, bool):
        errors.append(f"invalid_cost:{key}")
        return None
    if not isinstance(value, (int, float)) or not isfinite(value) or value < 0:
        errors.append(f"invalid_cost:{key}")
        return None
    return float(value)


def qualify_procurement_quote(
    evidence: Mapping[str, Any], *, as_of: str, max_age_days: int = 30,
) -> dict[str, Any]:
    """Return a reviewed screening record. Never authorize spending."""
    errors: list[str] = []
    blockers: list[str] = []
    if not isinstance(evidence, Mapping) or evidence.get("schema_version") != SCHEMA:
        return {
            "status": "INVALID", "errors": ["unsupported_quote_schema"],
            "purchase_authorized": False,
        }
    candidate_id = str(evidence.get("candidate_id") or "")
    if not candidate_id:
        errors.append("missing_candidate_id")
    market = evidence.get("market")
    currency = evidence.get("currency")
    if CURRENCY.get(market) != currency:
        errors.append("market_currency_mismatch")
    quantity = evidence.get("quantity")
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
        errors.append("invalid_quantity")
    if (isinstance(max_age_days, bool) or not isinstance(max_age_days, int)
            or max_age_days < 1):
        errors.append("invalid_max_age_days")
    try:
        today = date.fromisoformat(as_of)
        quoted_at = date.fromisoformat(str(evidence.get("quote_date") or ""))
    except (TypeError, ValueError):
        errors.append("invalid_quote_date")
        quoted_at = None
        today = None
    if today and quoted_at:
        age = (today - quoted_at).days
        if age < 0:
            errors.append("future_dated_quote")
        elif age > max_age_days:
            blockers.append("stale_quote")

    quote_kind = evidence.get("quote_kind")
    if quote_kind != "direct_written_seller_quote":
        blockers.append("not_a_direct_seller_quote")
    if not str(evidence.get("seller_id") or "").strip():
        blockers.append("seller_unidentified")
    if not str(evidence.get("written_quote_reference") or "").strip():
        blockers.append("missing_written_quote")
    if not str(evidence.get("exact_sku") or "").strip():
        blockers.append("exact_sku_unconfirmed")
    if not str(evidence.get("variant_photo_or_serial_reference") or "").strip():
        blockers.append("variant_not_evidenced")
    if not str(evidence.get("condition_or_test_reference") or "").strip():
        blockers.append("working_condition_unproven")
    if evidence.get("stock_confirmed_for_quantity") is not True:
        blockers.append("stock_quantity_unconfirmed")
    if not str(evidence.get("stock_evidence_reference") or "").strip():
        blockers.append("missing_stock_evidence")
    if not str(evidence.get("warranty_and_return_terms_reference") or "").strip():
        blockers.append("missing_warranty_terms")
    if not str(evidence.get("delivery_commitment_reference") or "").strip():
        blockers.append("missing_delivery_commitment")
    if evidence.get("lawful_ownership_review") is not True:
        blockers.append("ownership_unreviewed")
    if evidence.get("regulated_waste_review") is not True:
        blockers.append("waste_or_recycling_rules_unreviewed")

    costs = evidence.get("per_unit_costs")
    if not isinstance(costs, Mapping):
        costs = {}
        errors.append("missing_per_unit_costs")
    values = {}
    for key in COST_KEYS:
        if key not in costs:
            errors.append(f"missing_cost:{key}")
            continue
        value = _monetary(costs[key], key, errors)
        if value is not None:
            values[key] = value
    if (isinstance(costs, Mapping) and evidence.get("line_item_currency") != currency):
        errors.append("item_currency_mismatch")
    total = sum(values.values()) if len(values) == len(COST_KEYS) else None
    if total is not None and not isfinite(total):
        errors.append("nonfinite_landed_cost")
        total = None
    if len(values) == len(COST_KEYS) and total is not None and evidence.get("total_includes_per_unit_fees") is not True:
        blockers.append("fee_completeness_unconfirmed")

    status = "INVALID" if errors else "QUOTE_REVIEW_READY" if not blockers else "RESEARCH_ONLY"
    return {
        "schema_version": "hardware_splicer.procurement_quote_screen.v1",
        "candidate_id": candidate_id,
        "market": market,
        "currency": currency,
        "quote_kind": quote_kind,
        "quantity": quantity,
        "landed_cost_per_unit": round(total, 2) if total is not None else None,
        "estimated_landed_total": round(total * quantity, 2) if total is not None and isinstance(quantity, int) and quantity > 0 else None,
        "status": status,
        "errors": sorted(set(errors)),
        "blockers": sorted(set(blockers)),
        "needs_human_review": True,
        "physical_test_passed_by_this_screen": False,
        "buyer_committed": False,
        "purchase_authorized": False,
        "value_claim": "NO_VALIDATED_ARBITRAGE_MARGIN",
        "limitations": [
            "even a written quote requires independent source and physical acceptance review",
            "this is procurement landed-cost screening, not profit or purchase approval",
            "marketplace asking prices and cross-listed advertisements are not seller quotations",
        ],
    }


def qualify_observation_not_quote(observation: Mapping[str, Any]) -> dict[str, Any]:
    """Strictly classify already-imported asking prices without elevating them."""
    if observation.get("transaction_status") != "NOT_TRANSACTION_READY":
        raise ValueError("market observation missing explicit discovery-only status")
    return {
        "candidate_id": observation.get("candidate_id"),
        "evidence_id": observation.get("evidence_id"),
        "observed_offer_group": observation.get("observed_offer_group"),
        "currency": observation.get("currency"),
        "source_url": observation.get("source_url"),
        "status": "RFQ_REQUIRED",
        "quote_ready": False,
        "source_price_min": observation.get("price_min"),
        "source_price_max": observation.get("price_max"),
        "landed_cost_per_unit": None,
        "validated_margin": None,
        "purchase_authorized": False,
        "next_evidence": [
            "direct dated seller written quote with exact option and quantities",
            "serial/model photos and recorded tests",
            "landed shipping, tax, repair and warranty terms in native currency",
            "supplier stock, eligibility, data wiping and legal ownership",
        ],
    }
