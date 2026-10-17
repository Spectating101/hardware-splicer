"""Evidence-aware tradeoff comparison for fabrication architecture options.

The service does not invent a universal weighted score. It estimates procurement
from retained quote snapshots, carries unresolved evidence and fabrication burden
as separate dimensions, and returns the non-dominated (Pareto-frontier) options.
When options reference the convergence resource graph, donor dependencies and
unresolved/unavailable resource burden are derived by HS rather than trusted from
agent-supplied counters.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Mapping, Sequence

from .fabrication_operator import FabricationValidationError
from .procurement_quotes import ProcurementQuoteBook
from .salvage_resource_graph import resource_index

_ALLOWED_KINDS = frozenset({"clean_sheet", "reclaim_heavy", "hybrid"})


class FabricationOptionTradeoff:
    def __init__(self, *, procurement: ProcurementQuoteBook):
        self.procurement = procurement

    def compare(
        self,
        *,
        options: Sequence[Mapping[str, Any]],
        currency: str,
        as_of: str | None = None,
        require_known_stock: bool = False,
        resource_graph: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if isinstance(options, (str, bytes, bytearray)) or not isinstance(options, Sequence):
            raise FabricationValidationError("fabrication options must be a list")
        if not 2 <= len(options) <= 64:
            raise FabricationValidationError("tradeoff comparison requires 2..64 options")
        resources = resource_index(resource_graph) if resource_graph is not None else None
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for index, option in enumerate(options):
            if not isinstance(option, Mapping):
                raise FabricationValidationError(f"option {index} must be an object")
            option_id = _id(option.get("option_id"), f"option {index} option_id")
            if option_id in seen:
                raise FabricationValidationError("fabrication option ids must be unique")
            seen.add(option_id)
            kind = option.get("kind")
            if kind not in _ALLOWED_KINDS:
                raise FabricationValidationError("option kind must be clean_sheet, reclaim_heavy or hybrid")
            bom = option.get("bom")
            if not isinstance(bom, list) or not bom:
                raise FabricationValidationError("each fabrication option requires a non-empty BOM")
            unresolved = _count(option.get("unresolved_evidence", 0), "unresolved_evidence")
            fabrication_ops = _count(option.get("fabrication_operations", 0), "fabrication_operations")
            manual_steps = _count(option.get("manual_steps", 0), "manual_steps")
            resource_summary = _resources_for_option(option, resources)
            if resource_summary is None:
                donor_dependencies = _count(option.get("donor_dependencies", 0), "donor_dependencies")
                unresolved_resource_facts = 0
                unavailable_resource_dependencies = 0
                resource_dependencies = 0
                referenced_resources: list[dict[str, Any]] = []
            else:
                donor_dependencies = resource_summary["donor_dependencies"]
                unresolved_resource_facts = resource_summary["unresolved_resource_facts"]
                unavailable_resource_dependencies = resource_summary["unavailable_resource_dependencies"]
                resource_dependencies = resource_summary["resource_dependencies"]
                referenced_resources = resource_summary["resources"]
                explicit_donors = option.get("donor_dependencies")
                if explicit_donors is not None:
                    claimed = _count(explicit_donors, "donor_dependencies")
                    if claimed != donor_dependencies:
                        raise FabricationValidationError(
                            f"option {option_id} donor_dependencies disagrees with referenced resource graph"
                        )
            estimate = self.procurement.cost_bom(
                lines=bom,
                currency=currency,
                as_of=as_of,
                require_known_stock=require_known_stock,
            )
            unpriced = sum(1 for line in estimate["lines"] if line["status"] == "UNPRICED")
            lead_times = [
                line.get("lead_time_days_snapshot")
                for line in estimate["lines"]
                if isinstance(line.get("lead_time_days_snapshot"), int)
            ]
            max_lead = max(lead_times) if lead_times else None
            rows.append({
                "option_id": option_id,
                "kind": kind,
                "procurement": estimate,
                "resource_refs": referenced_resources,
                "metrics": {
                    "unpriced_lines": unpriced,
                    "unresolved_evidence": unresolved,
                    "unresolved_resource_facts": unresolved_resource_facts,
                    "unavailable_resource_dependencies": unavailable_resource_dependencies,
                    "resource_dependencies": resource_dependencies,
                    "fabrication_operations": fabrication_ops,
                    "manual_steps": manual_steps,
                    "donor_dependencies": donor_dependencies,
                    "estimated_total": estimate["estimated_total"],
                    "max_quoted_lead_time_days": max_lead,
                },
            })

        frontier: list[str] = []
        dominated_by: dict[str, list[str]] = {}
        for candidate in rows:
            dominators = [
                other["option_id"]
                for other in rows
                if other["option_id"] != candidate["option_id"] and _dominates(other, candidate)
            ]
            dominated_by[candidate["option_id"]] = sorted(dominators)
            if not dominators:
                frontier.append(candidate["option_id"])
        return {
            "schema": "hardware_splicer.fabrication_option_tradeoff.v1",
            "currency": currency.upper(),
            "options": rows,
            "pareto_frontier": sorted(frontier),
            "dominated_by": dominated_by,
            "automatic_winner": None,
            "decision_requires_policy_or_human": True,
            "resource_graph_used": resource_graph is not None,
            "purchase_authorized": False,
            "physical_correctness": "UNPROVEN",
        }


def _resources_for_option(
    option: Mapping[str, Any],
    resources: Mapping[str, Mapping[str, Any]] | None,
) -> dict[str, Any] | None:
    refs = option.get("resource_refs")
    if refs is None:
        return None
    if resources is None:
        raise FabricationValidationError("resource_refs require resource_graph")
    if not isinstance(refs, list) or len(refs) > 256 or any(not isinstance(value, str) for value in refs):
        raise FabricationValidationError("resource_refs must be a bounded list of resource ids")
    if len(refs) != len(set(refs)):
        raise FabricationValidationError("resource_refs must be unique")
    selected: list[dict[str, Any]] = []
    unresolved = 0
    unavailable = 0
    donors = 0
    for raw in refs:
        ident = _id(raw, "resource_ref")
        if ident not in resources:
            raise FabricationValidationError(f"unknown resource_ref: {ident}")
        row = resources[ident]
        if row.get("kind") == "donor":
            donors += 1
        unresolved_facts = row.get("unresolved_facts") or []
        unresolved += len(unresolved_facts)
        if row.get("available") is not True:
            unavailable += 1
        support = row.get("support") if isinstance(row.get("support"), Mapping) else {}
        selected.append({
            "resource_id": ident,
            "kind": row.get("kind"),
            "available": row.get("available") is True,
            "unresolved_fact_count": len(unresolved_facts),
            "support": dict(support),
        })
    return {
        "resources": selected,
        "resource_dependencies": len(selected),
        "donor_dependencies": donors,
        "unresolved_resource_facts": unresolved,
        "unavailable_resource_dependencies": unavailable,
    }


def _dominates(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    lm = left["metrics"]
    rm = right["metrics"]
    dimensions: list[tuple[Decimal, Decimal]] = [
        (Decimal(lm["unpriced_lines"]), Decimal(rm["unpriced_lines"])),
        (Decimal(lm["unresolved_evidence"]), Decimal(rm["unresolved_evidence"])),
        (Decimal(lm.get("unresolved_resource_facts", 0)), Decimal(rm.get("unresolved_resource_facts", 0))),
        (Decimal(lm.get("unavailable_resource_dependencies", 0)), Decimal(rm.get("unavailable_resource_dependencies", 0))),
        (Decimal(lm["fabrication_operations"]), Decimal(rm["fabrication_operations"])),
        (Decimal(lm["manual_steps"]), Decimal(rm["manual_steps"])),
        (Decimal(lm["estimated_total"]), Decimal(rm["estimated_total"])),
    ]
    # Lead time only participates when both sides have a quoted value.
    if lm["max_quoted_lead_time_days"] is not None and rm["max_quoted_lead_time_days"] is not None:
        dimensions.append((Decimal(lm["max_quoted_lead_time_days"]), Decimal(rm["max_quoted_lead_time_days"])))
    no_worse = all(left_value <= right_value for left_value, right_value in dimensions)
    strictly_better = any(left_value < right_value for left_value, right_value in dimensions)
    return no_worse and strictly_better


def _count(value: Any, field: str) -> int:
    if type(value) is not int or not 0 <= value <= 10**9:
        raise FabricationValidationError(f"{field} must be a non-negative integer")
    return value


def _id(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise FabricationValidationError(f"{field} must be a string")
    cleaned = value.strip()
    if not cleaned or len(cleaned) > 128 or any(not (ch.isalnum() or ch in "._:-") for ch in cleaned):
        raise FabricationValidationError(f"{field} must be a bounded identifier")
    return cleaned
