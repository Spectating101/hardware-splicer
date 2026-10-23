"""Manufacturing consistency checks for Hardware Splicer project packages.

The authority model prevents unsupported certainty claims, but it cannot detect a
self-consistent quantitative error such as a BOM listing one servo when the compiled
build graph contains two servo instances. This module closes that separate class of
failure with deterministic package-level reconciliation.
"""

from __future__ import annotations

import copy
from collections import Counter
from typing import Any, Dict, Mapping, Sequence

SCHEMA_VERSION = "hardware_splicer.manufacturing_reconciliation.v1"


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _quantity(value: Any) -> tuple[int | None, str | None]:
    if value in (None, ""):
        return 1, None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None, "not_numeric"
    if not numeric.is_integer():
        return None, "not_integer"
    quantity = int(numeric)
    if quantity <= 0:
        return None, "not_positive"
    return quantity, None


def reconcile_bom_to_build_graph(
    build_graph: Mapping[str, Any] | None,
    bom_lines: Sequence[Mapping[str, Any]] | None,
) -> Dict[str, Any]:
    """Compare compiled module instances with BOM quantities.

    Graph nodes are instance truth: each node contributes exactly one required
    module. BOM lines may be instance-shaped or aggregate repeated modules through
    ``qty``. BOM-only rows are warnings because off-board parts, harness material,
    fasteners, and other assembly items may legitimately sit outside the electrical
    graph. Missing or under/over-counted graph modules are blockers.
    """

    graph = dict(build_graph or {})
    nodes = [row for row in (graph.get("nodes") or []) if isinstance(row, Mapping)]
    lines = [row for row in (bom_lines or []) if isinstance(row, Mapping)]
    blockers: list[Dict[str, Any]] = []
    warnings: list[Dict[str, Any]] = []

    if not nodes:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "not_evaluable",
            "package_ready": None,
            "graph_instance_count": 0,
            "bom_quantity_count": sum(
                quantity or 0 for quantity, _ in (_quantity(row.get("qty")) for row in lines)
            ),
            "graph_counts": {},
            "bom_counts": {},
            "blockers": [],
            "warnings": [
                {
                    "code": "build_graph_missing",
                    "message": "No compiled build-graph nodes are available for BOM reconciliation.",
                }
            ],
        }

    node_ids: set[str] = set()
    graph_by_node_id: Dict[str, str] = {}
    graph_counts: Counter[str] = Counter()
    unidentified_nodes: list[str] = []
    for index, node in enumerate(nodes, start=1):
        node_id = _text(node.get("id")) or f"index:{index}"
        if node_id in node_ids:
            blockers.append(
                {
                    "code": "duplicate_graph_node_id",
                    "node_id": node_id,
                    "message": f"Build graph contains duplicate node ID {node_id!r}.",
                }
            )
        node_ids.add(node_id)
        module_id = _text(node.get("moduleId") or node.get("module_id"))
        if not module_id:
            unidentified_nodes.append(node_id)
            continue
        graph_by_node_id[node_id] = module_id
        graph_counts[module_id] += 1

    if unidentified_nodes:
        blockers.append(
            {
                "code": "graph_node_missing_module_id",
                "node_ids": unidentified_nodes,
                "message": (
                    f"{len(unidentified_nodes)} build-graph node(s) lack module identity and "
                    "cannot be reconciled to the BOM."
                ),
            }
        )

    bom_counts: Counter[str] = Counter()
    bom_node_ids: set[str] = set()
    bom_refs: set[str] = set()
    unidentified_bom_rows: list[int] = []
    for index, row in enumerate(lines, start=1):
        module_id = _text(row.get("module_id") or row.get("moduleId"))
        quantity, error = _quantity(row.get("qty"))
        if error:
            blockers.append(
                {
                    "code": "invalid_bom_quantity",
                    "line_index": index,
                    "module_id": module_id or None,
                    "value": row.get("qty"),
                    "reason": error,
                    "message": f"BOM line {index} has invalid quantity {row.get('qty')!r}.",
                }
            )
            continue
        if not module_id:
            unidentified_bom_rows.append(index)
            continue
        bom_counts[module_id] += quantity or 0

        node_id = _text(row.get("node_id") or row.get("nodeId"))
        if node_id:
            if node_id in bom_node_ids:
                blockers.append(
                    {
                        "code": "duplicate_bom_node_id",
                        "node_id": node_id,
                        "message": f"More than one BOM line claims build-graph node {node_id!r}.",
                    }
                )
            bom_node_ids.add(node_id)
            expected_module = graph_by_node_id.get(node_id)
            if expected_module is None:
                blockers.append(
                    {
                        "code": "unknown_bom_node_id",
                        "node_id": node_id,
                        "module_id": module_id,
                        "message": f"BOM line references unknown build-graph node {node_id!r}.",
                    }
                )
            elif expected_module != module_id:
                blockers.append(
                    {
                        "code": "bom_node_module_mismatch",
                        "node_id": node_id,
                        "expected_module_id": expected_module,
                        "actual_module_id": module_id,
                        "message": (
                            f"BOM node {node_id!r} names {module_id!r}; build graph requires "
                            f"{expected_module!r}."
                        ),
                    }
                )

        reference = _text(row.get("ref") or row.get("designator"))
        if reference:
            if reference in bom_refs:
                blockers.append(
                    {
                        "code": "duplicate_bom_reference",
                        "reference": reference,
                        "message": f"BOM reference {reference!r} appears more than once.",
                    }
                )
            bom_refs.add(reference)

    if unidentified_bom_rows:
        warnings.append(
            {
                "code": "bom_rows_missing_module_id",
                "line_indices": unidentified_bom_rows,
                "message": (
                    f"{len(unidentified_bom_rows)} BOM line(s) lack module identity and were "
                    "excluded from graph quantity comparison."
                ),
            }
        )

    for module_id, expected in sorted(graph_counts.items()):
        actual = int(bom_counts.get(module_id, 0))
        if actual != expected:
            blockers.append(
                {
                    "code": "bom_graph_quantity_mismatch",
                    "module_id": module_id,
                    "expected_graph_instances": expected,
                    "actual_bom_quantity": actual,
                    "delta": actual - expected,
                    "message": (
                        f"BOM quantity for {module_id!r} is {actual}; compiled build graph "
                        f"contains {expected} instance(s)."
                    ),
                }
            )

    for module_id, quantity in sorted(bom_counts.items()):
        if module_id not in graph_counts:
            warnings.append(
                {
                    "code": "bom_only_module",
                    "module_id": module_id,
                    "quantity": int(quantity),
                    "message": (
                        f"BOM contains {quantity} × {module_id!r} outside the compiled graph; "
                        "confirm it is an intentional off-board or assembly item."
                    ),
                }
            )

    status = "blocked" if blockers else "clear"
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "package_ready": not blockers,
        "graph_instance_count": int(sum(graph_counts.values())),
        "bom_quantity_count": int(sum(bom_counts.values())),
        "graph_counts": dict(sorted(graph_counts.items())),
        "bom_counts": dict(sorted(bom_counts.items())),
        "blockers": blockers,
        "warnings": warnings,
    }



# Explicit multi-instance source inventory is not interchangeable with a single
# graph node: two donor motors and one generated motor is an engineering loss.
# Extra unused inventory is *not* an error; only under-counted modules actually
# selected into the compiled graph are guarded.
_MULTI_INSTANCE_INTAKE_ROLES = frozenset({"mot", "act", "svo", "load", "sns"})


def reconcile_intake_quantities_to_build_graph(
    intake: Mapping[str, Any] | None,
    build_graph: Mapping[str, Any] | None,
    bom_lines: Sequence[Mapping[str, Any]] | None = None,
) -> Dict[str, Any]:
    """Detect known selected multi-instance inventory lost in project synthesis.

    Optional available parts not selected into the graph are intentionally not
    blockers. Only a selected module ID with fewer instances than the intake
    demands is blocked pending reconciliation or an operator disposition.
    This checks *representation*, not circuit compatibility or part verification.
    """
    from .module_resolver import resolve_parts_to_modules

    source = dict(intake or {})
    parts = source.get("normalized_parts") or source.get("available_parts") or []
    if not isinstance(parts, list):
        parts = []
    nodes = [
        row for row in ((build_graph or {}).get("nodes") or [])
        if isinstance(row, Mapping)
    ]
    graph_counts: Counter[str] = Counter(
        _text(row.get("moduleId") or row.get("module_id"))
        for row in nodes
        if _text(row.get("moduleId") or row.get("module_id"))
    )
    bom_counts: Counter[str] = Counter()
    for row in (bom_lines or []):
        if not isinstance(row, Mapping):
            continue
        module = _text(row.get("module_id") or row.get("moduleId"))
        qty, error = _quantity(row.get("qty"))
        if module and not error:
            bom_counts[module] += qty or 0
    if not parts or (not nodes and not bom_counts):
        return {
            "status": "not_evaluable",
            "source_counts": {},
            "graph_counts": dict(sorted(graph_counts.items())),
            "bom_counts": dict(sorted(bom_counts.items())),
            "blockers": [],
            "warnings": [],
        }

    source_counts: Counter[str] = Counter()
    for part in parts:
        if not isinstance(part, Mapping):
            continue
        candidates = resolve_parts_to_modules([part])
        if not candidates:
            continue
        candidate = next(
            (row for row in candidates if row.get("module_id")), {}
        )
        module_id = _text(candidate.get("module_id"))
        role = _text(candidate.get("role"))
        if not module_id or role not in _MULTI_INSTANCE_INTAKE_ROLES:
            continue
        quantity, error = _quantity(part.get("quantity", part.get("qty", 1)))
        # Invalid quantities cannot become asserted inventory facts.
        if error:
            continue
        source_counts[module_id] += quantity or 0

    blockers = []
    warnings = []
    for module_id, expected in sorted(source_counts.items()):
        actual_graph = int(graph_counts.get(module_id, 0))
        actual_bom = int(bom_counts.get(module_id, 0))
        # A BOM-selected motor absent from the graph is still selected hardware,
        # not an optional spare. A missing graph and an under-counted BOM are both
        # review blockers: the system must not claim the requested unit count.
        if actual_graph == 0 and actual_bom == 0:
            warnings.append({
                "code": "inventory_module_not_selected",
                "module_id": module_id,
                "inventory_quantity": int(expected),
                "message": (
                    f"Inventory contains {expected} × {module_id!r}, but no "
                    "matching module appears in the graph or BOM; confirm intentional omission."
                ),
            })
        elif actual_graph < expected or (actual_bom and actual_bom < expected):
            blockers.append({
                "code": "intake_selected_quantity_underrepresented",
                "module_id": module_id,
                "intake_quantity": int(expected),
                "actual_graph_instances": actual_graph,
                "actual_bom_quantity": actual_bom,
                "missing_graph_instances": int(max(0, expected - actual_graph)),
                "missing_bom_units": int(max(0, expected - actual_bom)),
                "message": (
                    f"Source inventory contains {expected} × {module_id!r}; "
                    f"generated graph has {actual_graph} and BOM has {actual_bom}. "
                    "Confirm any intentionally unused units before release."
                ),
            })

    return {
        "status": "blocked" if blockers else "clear",
        "source_counts": dict(sorted(source_counts.items())),
        "graph_counts": dict(sorted(graph_counts.items())),
        "bom_counts": dict(sorted(bom_counts.items())),
        "blockers": blockers,
        "warnings": warnings,
    }

def apply_manufacturing_reconciliation(
    package: Mapping[str, Any],
    *,
    build_graph: Mapping[str, Any] | None,
    intake: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Attach reconciliation and make contradictions package-blocking.

    Existing evidence such as ``power_on_authorized`` is not rewritten: a BOM
    contradiction blocks this package/release, but it does not falsify a historical
    physical measurement. The package verdict and build/fabrication readiness are
    downgraded until the contradiction is resolved.
    """

    result = copy.deepcopy(dict(package))
    bom = dict(result.get("bom") or {})
    reconciliation = reconcile_bom_to_build_graph(
        build_graph,
        [row for row in (bom.get("lines") or []) if isinstance(row, Mapping)],
    )
    result["manufacturing_reconciliation"] = reconciliation
    intake_reconciliation = reconcile_intake_quantities_to_build_graph(intake, build_graph, bom.get("lines"))
    result["intake_quantity_reconciliation"] = intake_reconciliation

    gates = dict(result.get("gates") or {})
    gates["manufacturing_reconciliation_status"] = reconciliation["status"]
    gates["intake_quantity_reconciliation_status"] = intake_reconciliation["status"]
    gates["package_ready"] = (
        False if intake_reconciliation["status"] == "blocked" else (
            reconciliation.get("package_ready")
            if reconciliation["status"] != "not_evaluable" else None
        )
    )
    if reconciliation["status"] == "blocked" or intake_reconciliation["status"] == "blocked":
        gates["verdict"] = "BLOCKED"
        gates["build_ready"] = False
        gates["fabrication_ready"] = False
        existing = [str(value) for value in (gates.get("blockers") or [])]
        for blocker in reconciliation["blockers"] + intake_reconciliation["blockers"]:
            message = str(blocker.get("message") or blocker.get("code"))
            if message not in existing:
                existing.append(message)
        gates["blockers"] = existing[:40]
    result["gates"] = gates
    return result
