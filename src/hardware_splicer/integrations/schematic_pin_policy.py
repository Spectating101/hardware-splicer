"""Pin-level decisions for the generated KiCad schematic.

The exporter draws one symbol per catalog module. KiCad ERC then asks three questions that the
netlist alone cannot answer:

* Which pins the design leaves open on purpose (no-connect flag)?
* Which power nets are fed from off-board through a connector or module (PWR_FLAG)?
* What electrical direction does a pin really have (catalog roles describe the MCU side)?

The answers come from ``data/schematic_pin_policy.json``, the module registry and the recipe notes
it cites. Nothing here relaxes ERC: a pin the netlist connects never receives a no-connect, a
PWR_FLAG is only planned for a net that has a power input, no power output and a documented
off-board feed, and anything else is left for KiCad to report.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from ..netlist.ir import CircuitNetlist
from ..pcb.module_registry import find_module

_POLICY_PATH = Path(__file__).resolve().parent.parent / "data" / "schematic_pin_policy.json"

ROLE_TO_KICAD_PIN_TYPE: Dict[str, str] = {
    "power_in": "power_in",
    "power_out": "power_out",
    "power_3v3": "power_out",
    "gnd": "power_in",
    "digital_in": "input",
    "analog_in": "input",
    "uart_rx": "input",
    "digital_out": "output",
    "analog_out": "output",
    "pwm": "output",
    "uart_tx": "output",
    "digital_io": "bidirectional",
    "i2c_sda": "bidirectional",
    "i2c_scl": "bidirectional",
}


@lru_cache(maxsize=1)
def load_policy() -> Mapping[str, Any]:
    return json.loads(_POLICY_PATH.read_text(encoding="utf-8"))


def catalog_pins(module_id: Optional[str]) -> List[Dict[str, Any]]:
    spec = find_module(str(module_id or "")) if module_id else None
    pins = list((spec or {}).get("pins") or [])
    return [dict(row) for row in pins if isinstance(row, Mapping) and str(row.get("id") or "").strip()]


def pin_electrical_type(
    module_id: Optional[str], pin: Mapping[str, Any], policy: Optional[Mapping[str, Any]] = None
) -> str:
    """KiCad electrical type for a catalog pin, honouring explicit direction overrides."""

    rules = policy if policy is not None else load_policy()
    override = (
        (rules.get("direction_overrides") or {}).get(str(module_id or ""), {}).get(str(pin.get("id")))
    )
    if isinstance(override, Mapping):
        direction = str(override.get("direction") or "").strip().lower()
        if direction in {"input", "output", "bidirectional"}:
            return direction
    return ROLE_TO_KICAD_PIN_TYPE.get(str(pin.get("role") or "").strip().lower(), "passive")


@dataclass(frozen=True)
class NoConnectPlan:
    ref: str
    pin: str
    disposition: str
    reason: str


@dataclass(frozen=True)
class PowerFlagPlan:
    """A PWR_FLAG attached to ``net`` at ``ref.pin`` (``stub`` when the net is synthetic)."""

    net: str
    ref: str
    pin: str
    source: str
    stub: bool = False


def _canonical(netlist: CircuitNetlist) -> tuple:
    components = tuple(sorted((c.ref, str(c.module_id or "")) for c in netlist.components))
    nets = frozenset(frozenset((p.component_ref, p.pin) for p in net.pins) for net in netlist.nets)
    return components, nets


@lru_cache(maxsize=None)
def _recipe_canonical(recipe_key: str) -> Optional[tuple]:
    """Canonical form of the netlist the catalog recipe ``recipe_key`` lowers to, or None."""

    from ..netlist.lower import build_graph_to_netlist
    from ..plan_to_graph import load_catalog_data, splice_plan_to_build_graph

    if recipe_key not in (load_catalog_data().get("recipes") or {}):
        return None
    graph, _id, _notes, _warnings = splice_plan_to_build_graph(
        {"target": {"recommended_build_id": recipe_key}}
    )
    return _canonical(build_graph_to_netlist(graph))


def catalog_recipe_for(netlist: CircuitNetlist, build_id: Optional[str]) -> Optional[str]:
    """The catalog recipe key this netlist actually is, or None.

    A caller-supplied build name is a claim, not evidence. Recipe-specific policy applies only
    when the netlist's components and connectivity equal what the recipe lowers to (the USB
    variant of a build counts as that build's recipe).
    """

    if not build_id:
        return None
    mine = _canonical(netlist)
    for key in (build_id, f"{build_id}_usb"):
        expected = _recipe_canonical(key)
        if expected is not None and expected == mine:
            return key
    return None


def _recipe_notes(recipe_key: str) -> str:
    from ..plan_to_graph import load_catalog_data

    recipe = (load_catalog_data().get("recipes") or {}).get(recipe_key) or {}
    return " ".join(str(n) for n in recipe.get("notes") or [])


def _pin_policy_entry(
    policy: Mapping[str, Any], recipe_key: Optional[str], module_id: str, pin_id: str
) -> Optional[Mapping[str, Any]]:
    if recipe_key:
        entry = ((policy.get("build_pins") or {}).get(recipe_key) or {}).get(module_id, {}).get(pin_id)
        if isinstance(entry, Mapping):
            return entry
    entry = (policy.get("module_pins") or {}).get(module_id, {}).get(pin_id)
    return entry if isinstance(entry, Mapping) else None


def plan_no_connects(
    netlist: CircuitNetlist,
    *,
    build_id: Optional[str] = None,
    policy: Optional[Mapping[str, Any]] = None,
) -> List[NoConnectPlan]:
    """Pins that may carry a no-connect flag.

    A pin qualifies only when no net references it and one of these documented reasons applies:
    the module's own pin note says it is optional, the module is a microcontroller board and the
    pin is general-purpose I/O, or ``schematic_pin_policy.json`` lists the pin (per module or per
    build, citing the recipe note or datasheet). Per-build entries apply only when the netlist is
    provably that catalog recipe (``catalog_recipe_for``). Unlisted pins stay open for KiCad.
    """

    rules = policy if policy is not None else load_policy()
    # Recipe-specific entries need proof the netlist is that recipe, not just its name.
    recipe_key = catalog_recipe_for(netlist, build_id)
    referenced = {pin.key() for net in netlist.nets for pin in net.pins}
    mcu = rules.get("mcu_general_io") or {}
    mcu_roles = {str(r) for r in mcu.get("roles") or []}
    note_re = re.compile(str(rules.get("optional_note_pattern") or r"\boptional\b"), re.IGNORECASE)
    plans: List[NoConnectPlan] = []
    for comp in netlist.components:
        module_id = str(comp.module_id or "")
        spec = find_module(module_id) if module_id else None
        if not spec:
            continue
        pins = catalog_pins(module_id)
        connected_here = {
            str(p.get("id")) for p in pins if f"{comp.ref}.{p.get('id')}" in referenced
        }
        for pin in pins:
            pin_id = str(pin.get("id"))
            if f"{comp.ref}.{pin_id}" in referenced:
                continue
            entry = _pin_policy_entry(rules, recipe_key, module_id, pin_id)
            if entry is not None:
                needs = {str(x) for x in entry.get("requires_connected") or []}
                if needs and not needs <= connected_here:
                    continue
                note_needed = str(entry.get("requires_recipe_note") or "")
                if note_needed and (
                    recipe_key is None or note_needed.lower() not in _recipe_notes(recipe_key).lower()
                ):
                    continue
                plans.append(
                    NoConnectPlan(comp.ref, pin_id, str(entry.get("disposition") or "listed"), str(entry.get("reason") or ""))
                )
            elif note_re.search(str(pin.get("notes") or "")):
                plans.append(NoConnectPlan(comp.ref, pin_id, "optional_per_module_note", str(pin.get("notes"))))
            elif (
                str(spec.get("category") or "") == str(mcu.get("category") or "mcu")
                and str(pin.get("role") or "").lower() in mcu_roles
            ):
                plans.append(NoConnectPlan(comp.ref, pin_id, "unused_mcu_io", str(mcu.get("reason") or "")))
    return plans


def _is_source_connector(spec: Mapping[str, Any]) -> bool:
    """Off-board supply entry: a power module that only emits power (barrel jack, USB power)."""

    if str(spec.get("category") or "") != "power":
        return False
    roles = [str(p.get("role") or "") for p in spec.get("pins") or []]
    return "power_out" in roles and "power_in" not in roles


def _ext_net_name(ref: str, pin: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", f"{ref}_{pin}_EXT")


def plan_power_flags(
    netlist: CircuitNetlist,
    *,
    policy: Optional[Mapping[str, Any]] = None,
) -> List[PowerFlagPlan]:
    """PWR_FLAGs for nets with a power input, no power output and a documented off-board feed.

    A net is fed when it holds a pin of an off-board supply connector (a power module that only
    emits power, such as the USB or barrel-jack inputs), a pin the policy names as externally
    supplied (``external_supply``) or as a module output terminal (``module_output_terminals``,
    e.g. a MOSFET module's switched return), or a ground pin that the policy declares common with another
    pin of the same non-isolated module whose net is itself fed. Nets with no such source get no
    flag, so KiCad keeps reporting them.
    """

    rules = policy if policy is not None else load_policy()
    comp_by_ref = {c.ref: c for c in netlist.components}
    external = rules.get("external_supply") or {}
    common = rules.get("common_ground") or {}
    outputs = rules.get("module_output_terminals") or {}

    def ptype(ref: str, pin_id: str) -> Optional[str]:
        comp = comp_by_ref.get(ref)
        for pin in catalog_pins(comp.module_id if comp else None):
            if str(pin.get("id")) == pin_id:
                return pin_electrical_type(comp.module_id if comp else None, pin, rules)
        return None

    net_pins: Dict[str, List[tuple[str, str]]] = {
        net.name: [(p.component_ref, p.pin) for p in net.pins] for net in netlist.nets
    }
    net_of: Dict[tuple[str, str], str] = {
        pin: name for name, pins in net_pins.items() for pin in pins
    }

    fed: Dict[str, tuple[str, str, str]] = {}

    def mark(net: str, ref: str, pin: str, source: str) -> None:
        fed.setdefault(net, (ref, pin, source))

    for net, pins in net_pins.items():
        for ref, pin_id in pins:
            comp = comp_by_ref.get(ref)
            module_id = str(comp.module_id or "") if comp else ""
            spec = find_module(module_id) if module_id else None
            if spec and _is_source_connector(spec):
                mark(net, ref, pin_id, f"{ref} ({module_id}) off-board supply connector")
            ext = external.get(module_id)
            if isinstance(ext, Mapping) and pin_id in (
                set(ext.get("ground_pins") or []) | set(ext.get("supply_pins") or [])
            ):
                mark(net, ref, pin_id, f"{ref} ({module_id}): {ext.get('reason')}")
            out = outputs.get(module_id)
            if isinstance(out, Mapping) and pin_id in set(out.get("pins") or []):
                mark(net, ref, pin_id, f"{ref} ({module_id}) output terminal {pin_id}: {out.get('reason')}")

    changed = True
    while changed:
        changed = False
        for comp in netlist.components:
            groups = common.get(str(comp.module_id or "")) or []
            for group in groups:
                live = [(p, net_of.get((comp.ref, p))) for p in group]
                feeders = [(p, n) for p, n in live if n is not None and n in fed]
                if not feeders:
                    continue
                src_pin, src_net = feeders[0]
                for pin_id, net in live:
                    if net is not None and net not in fed:
                        mark(
                            net,
                            comp.ref,
                            pin_id,
                            f"{comp.ref} ({comp.module_id}) ground {pin_id}, common with {src_pin} on fed net {src_net}",
                        )
                        changed = True

    plans: List[PowerFlagPlan] = []
    for net, pins in net_pins.items():
        types = [ptype(ref, pin_id) for ref, pin_id in pins]
        if "power_in" not in types or "power_out" in types:
            continue
        if net not in fed:
            continue
        ref, pin_id, source = fed[net]
        plans.append(PowerFlagPlan(net=net, ref=ref, pin=pin_id, source=source))

    connected = {p for pins in net_pins.values() for p in pins}
    for comp in netlist.components:
        ext = external.get(str(comp.module_id or ""))
        if not isinstance(ext, Mapping):
            continue
        for pin_id in ext.get("supply_pins") or []:
            if (comp.ref, pin_id) in connected:
                continue
            plans.append(
                PowerFlagPlan(
                    net=_ext_net_name(comp.ref, pin_id),
                    ref=comp.ref,
                    pin=str(pin_id),
                    source=f"{comp.ref} ({comp.module_id}) {pin_id}: {ext.get('reason')}",
                    stub=True,
                )
            )
    return plans
