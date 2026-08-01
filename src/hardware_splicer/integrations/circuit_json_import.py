"""Import upstream tscircuit Circuit JSON into Hardware Splicer netlist IR.

The importer accepts the real source graph used by Circuit JSON:

- ``source_component`` defines component identity and source properties;
- ``source_port`` maps stable port IDs to component pins;
- ``source_net`` names shared electrical nets;
- ``source_trace`` connects ports to named nets or directly to other ports.

Legacy Hardware-Splicer ``schematic_trace`` documents and ``REF.PIN`` port
references remain supported for backwards compatibility.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Mapping, Sequence

from ..netlist.ir import CircuitNetlist, ComponentInstance, Net, PinRef

_WARNING_SUFFIXES = ("_warning", "_error")
_VALUE_FIELDS = (
    "display_value",
    "display_resistance",
    "display_capacitance",
    "display_inductance",
    "display_voltage",
    "value",
    "resistance",
    "capacitance",
    "inductance",
    "manufacturer_part_number",
)


def _string(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _unique_ref(preferred: str, source_id: str, used: Counter[str]) -> str:
    base = preferred or source_id or "U"
    used[base] += 1
    return base if used[base] == 1 else f"{base}_{used[base]}"


def _component_value(doc: Mapping[str, Any], ref: str) -> str:
    for field in _VALUE_FIELDS:
        value = doc.get(field)
        if value not in {None, ""}:
            return str(value)
    return ref


def _component_footprint(
    doc: Mapping[str, Any],
    pcb_component: Mapping[str, Any] | None,
    ref: str,
) -> str:
    direct = doc.get("footprint") or doc.get("kicad_footprint")
    if direct:
        return str(direct)
    metadata = dict((pcb_component or {}).get("metadata") or {})
    kicad = metadata.get("kicad_footprint")
    if isinstance(kicad, Mapping):
        for key in ("footprint", "name", "library_link", "path"):
            if kicad.get(key):
                return str(kicad[key])
    if kicad:
        return str(kicad)
    return ref


def _legacy_pin_ref(value: Any) -> PinRef | None:
    text = _string(value)
    if "." not in text:
        return None
    ref, pin = text.split(".", 1)
    if not ref or not pin:
        return None
    return PinRef(component_ref=ref, pin=pin)


def _dedupe_pins(pins: Sequence[PinRef]) -> List[PinRef]:
    seen: set[str] = set()
    result: List[PinRef] = []
    for pin in pins:
        key = pin.key()
        if key in seen:
            continue
        seen.add(key)
        result.append(pin)
    return result


def _diagnostic_document(doc: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        key: doc.get(key)
        for key in (
            "type",
            "error_id",
            "warning_id",
            "message",
            "source_component_id",
            "source_port_id",
            "source_trace_id",
            "source_net_id",
        )
        if doc.get(key) not in {None, ""}
    }


def circuit_json_to_netlist(
    docs: Sequence[Mapping[str, Any]],
    *,
    source: str = "circuit_json",
) -> CircuitNetlist:
    """Convert Circuit JSON source documents into :class:`CircuitNetlist`.

    The conversion intentionally consumes the source-level graph rather than
    inferring connectivity from rendered schematic or PCB coordinates. Import
    diagnostics are retained in ``CircuitNetlist.metadata['circuit_json']``.
    """

    source_components = [doc for doc in docs if doc.get("type") == "source_component"]
    source_ports = [doc for doc in docs if doc.get("type") == "source_port"]
    source_nets = [doc for doc in docs if doc.get("type") == "source_net"]
    source_traces = [doc for doc in docs if doc.get("type") == "source_trace"]
    legacy_traces = [doc for doc in docs if doc.get("type") == "schematic_trace"]
    pcb_components = {
        _string(doc.get("source_component_id")): doc
        for doc in docs
        if doc.get("type") == "pcb_component" and doc.get("source_component_id")
    }

    used_refs: Counter[str] = Counter()
    component_id_to_ref: Dict[str, str] = {}
    components: List[ComponentInstance] = []

    for doc in source_components:
        source_id = _string(doc.get("source_component_id"))
        ref = _unique_ref(_string(doc.get("name")), source_id, used_refs)
        if source_id:
            component_id_to_ref[source_id] = ref
        pcb_component = pcb_components.get(source_id)
        ftype = _string(doc.get("ftype"))
        metadata = {
            "interchange": "circuit-json",
            "source_component_id": source_id or None,
            "ftype": ftype or None,
            "manufacturer_part_number": doc.get("manufacturer_part_number"),
            "supplier_part_numbers": doc.get("supplier_part_numbers"),
            "subcircuit_id": doc.get("subcircuit_id"),
            "pcb_component_id": (pcb_component or {}).get("pcb_component_id"),
        }
        components.append(
            ComponentInstance(
                ref=ref,
                value=_component_value(doc, ref),
                footprint=_component_footprint(doc, pcb_component, ref),
                module_id=_string(doc.get("module_id")) or ftype or ref,
                metadata={key: value for key, value in metadata.items() if value is not None},
            )
        )

    port_id_to_pin: Dict[str, PinRef] = {}
    unresolved_ports: List[Dict[str, Any]] = []

    for doc in source_ports:
        port_id = _string(doc.get("source_port_id"))
        component_id = _string(doc.get("source_component_id"))
        ref = component_id_to_ref.get(component_id)
        if not port_id or not ref:
            unresolved_ports.append(
                {
                    "source_port_id": port_id or None,
                    "source_component_id": component_id or None,
                    "reason": "missing_component_mapping",
                }
            )
            continue
        pin_value = doc.get("pin_number")
        if pin_value is None:
            pin_value = (
                doc.get("most_frequently_referenced_by_name")
                or doc.get("name")
                or next(iter(doc.get("port_hints") or []), None)
                or port_id
            )
        port_id_to_pin[port_id] = PinRef(component_ref=ref, pin=str(pin_value))

    source_net_index = {
        _string(doc.get("source_net_id")): doc
        for doc in source_nets
        if doc.get("source_net_id")
    }
    net_buckets: Dict[str, List[PinRef]] = {}
    net_sources: Dict[str, Dict[str, Any]] = {}
    unresolved_trace_ports: List[Dict[str, Any]] = []
    ambiguous_traces: List[Dict[str, Any]] = []

    def add_trace(doc: Mapping[str, Any], *, legacy: bool = False) -> None:
        trace_id = _string(doc.get("source_trace_id")) or _string(doc.get("schematic_trace_id"))
        raw_port_ids = list(doc.get("connected_source_port_ids") or [])
        pins: List[PinRef] = []
        missing: List[str] = []
        for raw_port in raw_port_ids:
            port_id = _string(raw_port)
            pin = port_id_to_pin.get(port_id) or _legacy_pin_ref(port_id)
            if pin:
                pins.append(pin)
            elif port_id:
                missing.append(port_id)
        if missing:
            unresolved_trace_ports.append(
                {
                    "trace_id": trace_id or None,
                    "source_port_ids": missing,
                }
            )

        source_net_ids = [
            _string(value)
            for value in (doc.get("connected_source_net_ids") or [])
            if _string(value)
        ]
        if not source_net_ids and legacy and doc.get("source_net_id"):
            source_net_ids = [_string(doc.get("source_net_id"))]

        if source_net_ids:
            resolved_names = [
                _string(source_net_index.get(net_id, {}).get("name")) or net_id
                for net_id in source_net_ids
            ]
            net_name = resolved_names[0]
            if len(source_net_ids) > 1:
                ambiguous_traces.append(
                    {
                        "trace_id": trace_id or None,
                        "source_net_ids": source_net_ids,
                        "resolved_names": resolved_names,
                        "reason": "multiple_source_nets_on_trace",
                    }
                )
            net_sources.setdefault(
                net_name,
                {
                    "source_net_ids": [],
                    "source_trace_ids": [],
                    "source_net": dict(source_net_index.get(source_net_ids[0]) or {}),
                },
            )
            for net_id in source_net_ids:
                if net_id not in net_sources[net_name]["source_net_ids"]:
                    net_sources[net_name]["source_net_ids"].append(net_id)
        else:
            net_name = (
                _string(doc.get("name"))
                or _string(doc.get("display_name"))
                or trace_id
                or f"NET_{len(net_buckets) + 1}"
            )
            net_sources.setdefault(
                net_name,
                {
                    "source_net_ids": [],
                    "source_trace_ids": [],
                    "source_net": {},
                },
            )

        if trace_id and trace_id not in net_sources[net_name]["source_trace_ids"]:
            net_sources[net_name]["source_trace_ids"].append(trace_id)
        net_buckets.setdefault(net_name, []).extend(pins)

    for doc in source_traces:
        add_trace(doc)
    for doc in legacy_traces:
        add_trace(doc, legacy=True)

    if not source_traces:
        for doc in legacy_traces:
            if doc.get("source_net_id") and not doc.get("connected_source_net_ids"):
                old_name = _string(doc.get("source_net_id")) or "NET"
                generated_name = (
                    _string(doc.get("name"))
                    or _string(doc.get("display_name"))
                    or _string(doc.get("schematic_trace_id"))
                )
                if generated_name and generated_name in net_buckets and old_name not in net_buckets:
                    net_buckets[old_name] = net_buckets.pop(generated_name)
                    net_sources[old_name] = net_sources.pop(generated_name)

    nets: List[Net] = []
    single_pin_nets: List[Dict[str, Any]] = []
    for name, raw_pins in net_buckets.items():
        pins = _dedupe_pins(raw_pins)
        if len(pins) < 2:
            single_pin_nets.append(
                {
                    "name": name,
                    "pins": [pin.to_dict() for pin in pins],
                    **net_sources.get(name, {}),
                }
            )
            continue
        nets.append(Net(name=name, pins=pins))

    diagnostic_docs = [
        _diagnostic_document(doc)
        for doc in docs
        if _string(doc.get("type")).endswith(_WARNING_SUFFIXES)
    ]
    metadata = {
        "interchange": "circuit-json",
        "circuit_json": {
            "document_count": len(docs),
            "source_component_count": len(source_components),
            "source_port_count": len(source_ports),
            "source_net_count": len(source_nets),
            "source_trace_count": len(source_traces),
            "legacy_schematic_trace_count": len(legacy_traces),
            "imported_component_count": len(components),
            "imported_net_count": len(nets),
            "unresolved_ports": unresolved_ports,
            "unresolved_trace_ports": unresolved_trace_ports,
            "ambiguous_traces": ambiguous_traces,
            "single_pin_nets": single_pin_nets,
            "source_nets": net_sources,
            "upstream_diagnostics": diagnostic_docs,
        },
    }
    return CircuitNetlist(
        source=source,
        components=components,
        nets=nets,
        metadata=metadata,
    )
