"""Measured commercial outcomes: append-only evidence, separate from screening estimates."""
from __future__ import annotations

import math
from typing import Any, Mapping

SCHEMA = "hardware_splicer.commercial_outcome_ledger.v1"
CURRENCIES = frozenset({"TWD", "CNY", "IDR", "USD"})


def _measured_value(item: Any, label: str, errors: list[str]) -> float | None:
    if not isinstance(item, Mapping):
        errors.append(f"missing:{label}")
        return None
    if item.get("evidence_class") != "MEASURED":
        errors.append(f"not_measured:{label}")
    if not str(item.get("reference") or "").strip():
        errors.append(f"missing_receipt:{label}")
    amount = item.get("amount")
    if isinstance(amount, bool):
        errors.append(f"invalid_amount:{label}")
        return None
    try:
        value = float(amount)
    except (TypeError, ValueError):
        errors.append(f"invalid_amount:{label}")
        return None
    if not math.isfinite(value) or value < 0:
        errors.append(f"invalid_amount:{label}")
        return None
    return value


def append_outcome(ledger: Mapping[str, Any], transaction: Mapping[str, Any]) -> dict[str, Any]:
    """Create a new ledger snapshot, never rewrite or silently upgrade old estimates.

    A measured transaction must have its own source-backed receipts and settled
    payment evidence. An invoice, deposit or unaccepted offer is not collected
    revenue. Later warranty spending remains unresolved, so this is provisional
    collected contribution rather than final lifetime profit.
    """
    errors: list[str] = []
    if ledger.get("schema_version") != SCHEMA:
        errors.append("unsupported_ledger_schema")
    original = ledger.get("transactions")
    if not isinstance(original, list):
        errors.append("missing_transactions")
        original = []
    if not isinstance(transaction, Mapping):
        return {"status": "INVALID", "errors": ["invalid_transaction"], "ledger": dict(ledger)}
    uid = str(transaction.get("transaction_id") or "")
    candidate = str(transaction.get("candidate_id") or "")
    route = str(transaction.get("route_id") or "")
    currency = transaction.get("currency")
    if not uid:
        errors.append("missing_transaction_id")
    if not candidate:
        errors.append("missing_candidate_id")
    if not route:
        errors.append("missing_route_id")
    if currency not in CURRENCIES:
        errors.append("unsupported_currency")
    if any(str(t.get("transaction_id")) == uid for t in original if isinstance(t, Mapping)):
        errors.append("duplicate_transaction_id")
    if transaction.get("acceptance_status") != "ACCEPTED":
        errors.append("unaccepted_transaction")
    if not str(transaction.get("acceptance_reference") or "").strip():
        errors.append("missing_acceptance_reference")
    if transaction.get("payment_status") != "SETTLED":
        errors.append("unsettled_revenue")
    if not str(transaction.get("payment_reference") or "").strip():
        errors.append("missing_payment_reference")
    revenue = _measured_value(transaction.get("revenue"), "revenue", errors)
    costs = transaction.get("costs")
    if not isinstance(costs, Mapping) or not costs:
        errors.append("missing_actual_costs")
        costs = {}
    values = {
        str(name): _measured_value(item, f"costs.{name}", errors)
        for name, item in costs.items()
    }
    # Financial receipt set must account for all expected cost categories explicitly;
    # the transaction supplies which categories apply, with zero-cost items recorded.
    required = {"acquisition", "materials", "engineering", "labor", "quality",
                "logistics_and_tax", "fees", "warranty_cash_spent"}
    if not required.issubset(costs.keys()):
        errors.append("incomplete_cost_coverage")
    if errors:
        return {"status": "INVALID", "errors": sorted(set(errors)),
                "ledger": dict(ledger), "transaction": None}
    assert revenue is not None and all(x is not None for x in values.values())
    spent = sum(values.values())
    contribution = revenue - spent
    entry = {
        "transaction_id": uid,
        "candidate_id": candidate,
        "route_id": route,
        "currency": currency,
        "acceptance_status": "ACCEPTED",
        "acceptance_reference": transaction["acceptance_reference"],
        "payment_status": "SETTLED",
        "payment_reference": transaction["payment_reference"],
        "revenue": dict(transaction["revenue"]),
        "costs": {name: dict(item) for name, item in costs.items()},
        "total_actual_cost": round(spent, 2),
        "collected_contribution_to_date": round(contribution, 2),
        "observed_cash_margin_to_date": round(contribution / revenue, 6) if revenue > 0 else None,
        "warranty_liability_finalized": False,
        "measurement_scope": "accepted_and_collected_transaction_only_future_claims_open",
    }
    result = dict(ledger)
    result["transactions"] = [*original, entry]
    return {"status": "RECORDED", "errors": [], "ledger": result, "transaction": entry}
