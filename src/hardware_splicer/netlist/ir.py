"""Circuit netlist intermediate representation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional


@dataclass
class PinRef:
    component_ref: str
    pin: str

    def to_dict(self) -> Dict[str, str]:
        return {"component_ref": self.component_ref, "pin": self.pin}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> PinRef:
        return cls(component_ref=str(data.get("component_ref") or ""), pin=str(data.get("pin") or ""))

    def key(self) -> str:
        return f"{self.component_ref}.{self.pin}"


@dataclass
class ComponentInstance:
    ref: str
    value: str = ""
    footprint: str = ""
    module_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ref": self.ref,
            "value": self.value,
            "footprint": self.footprint,
            "module_id": self.module_id,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ComponentInstance:
        return cls(
            ref=str(data.get("ref") or ""),
            value=str(data.get("value") or ""),
            footprint=str(data.get("footprint") or ""),
            module_id=data.get("module_id"),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass
class Net:
    name: str
    pins: List[PinRef] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "pins": [p.to_dict() for p in self.pins]}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Net:
        return Net(
            name=str(data.get("name") or ""),
            pins=[PinRef.from_dict(p) for p in data.get("pins") or []],
        )


@dataclass
class CircuitNetlist:
    schema_version: str = "hardware_splicer.netlist.v1"
    source: str = "unknown"
    components: List[ComponentInstance] = field(default_factory=list)
    nets: List[Net] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "source": self.source,
            "components": [c.to_dict() for c in self.components],
            "nets": [n.to_dict() for n in self.nets],
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> CircuitNetlist:
        return cls(
            schema_version=str(data.get("schema_version") or "hardware_splicer.netlist.v1"),
            source=str(data.get("source") or "unknown"),
            components=[ComponentInstance.from_dict(c) for c in data.get("components") or []],
            nets=[Net.from_dict(n) for n in data.get("nets") or []],
            metadata=dict(data.get("metadata") or {}),
        )

    def component_map(self) -> Dict[str, ComponentInstance]:
        return {c.ref: c for c in self.components}
