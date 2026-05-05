from __future__ import annotations

from collections import Counter, deque
from typing import Any, Dict, List, Sequence, Tuple


class TopologyDiff:
    """Compare detected visual topology to a reference netlist connectivity model."""

    def __init__(self) -> None:
        self._ref_prefix_category: Dict[str, str] = {
            "R": "resistor",
            "C": "capacitor",
            "L": "inductor",
            "D": "diode",
            "Q": "transistor",
            "U": "ic",
            "J": "connector",
            "P": "connector",
            "X": "connector",
            "SW": "switch",
            "K": "relay",
            "F": "fuse",
            "Y": "crystal",
            "B": "battery",
            "A": "connector",
            "T": "transformer",
        }

    @staticmethod
    def _normalize_value(value: Any) -> str:
        return str(value or "").strip().lower().replace(" ", "_").replace("-", "_")

    @staticmethod
    def _as_text(value: Any) -> str:
        return str(value or "").strip()

    @staticmethod
    def _endpoint_key(value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        return text.split(":", 1)[0]

    @staticmethod
    def _endpoint_label(value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            return "unknown"
        if ":" in text:
            tail = text.split(":", 1)[1].strip()
            if tail:
                return tail
        return text

    def _classify_reference_component(self, ref: str, meta: Dict[str, Any]) -> str:
        ref_key = (ref or "").strip().upper()
        for prefix, category in self._ref_prefix_category.items():
            if ref_key.startswith(prefix):
                return category

        # Metadata-based fallbacks.
        haystack = f"{meta.get('value','')} {meta.get('footprint','')}".upper()
        for token in ("CONN", "HEADER", "TERMINAL"):
            if token in haystack:
                return "connector"
        if "RES" in haystack or "RESISTOR" in haystack:
            return "resistor"
        if "CAP" in haystack or "CAPACITOR" in haystack:
            return "capacitor"
        if "LED" in haystack:
            return "led"
        if "STM" in haystack or "ESP" in haystack or "MCU" in haystack:
            return "ic"
        return "other"

    @staticmethod
    def _signature_from_types(types: Sequence[str]) -> str:
        if not types:
            return ""
        counts = Counter(types)
        return "|".join(f"{name}:{counts[name]}" for name in sorted(counts.keys()))

    def _extract_reference_component_classes(self, reference_data: Dict[str, Any]) -> Dict[str, str]:
        components = reference_data.get("components") or {}
        if not isinstance(components, dict):
            return {}
        return {
            str(ref): self._normalize_value(
                self._classify_reference_component(str(ref), meta if isinstance(meta, dict) else {})
            )
            for ref, meta in components.items()
            if isinstance(ref, str) and ref.strip()
        }

    @staticmethod
    def _safe_nodes(node_list: Any) -> List[Tuple[str, str]]:
        if not isinstance(node_list, list):
            return []
        nodes: List[Tuple[str, str]] = []
        for node in node_list:
            if not isinstance(node, dict):
                continue
            ref = str(node.get("ref") or "").strip()
            pin = str(node.get("pin") or "").strip()
            if ref and pin:
                nodes.append((ref, pin))
        return nodes

    def extract_reference_signatures(self, reference_data: Dict[str, Any]) -> Tuple[Counter[str], Dict[str, int]]:
        if not isinstance(reference_data, dict):
            return Counter(), {"net_count": 0, "component_count": 0, "isolated_count": 0}

        nets = reference_data.get("nets") or {}
        if not isinstance(nets, dict):
            return Counter(), {"net_count": 0, "component_count": 0, "isolated_count": 0}

        ref_classes = self._extract_reference_component_classes(reference_data)
        signatures: Counter[str] = Counter()
        component_counts: Counter[str] = Counter()
        isolated = 0

        for net_data in nets.values():
            if not isinstance(net_data, dict):
                continue
            nodes = self._safe_nodes(net_data.get("nodes"))
            types: List[str] = []
            for ref, _pin in nodes:
                category = ref_classes.get(ref, "other")
                if not category:
                    category = "other"
                types.append(category)
                component_counts[category] += 1

            if len(types) == 1:
                isolated += 1
            if len(types) < 2:
                continue
            sig = self._signature_from_types(types)
            if sig:
                signatures[sig] += 1

        return signatures, {
            "net_count": len(signatures),
            "component_count": sum(component_counts.values()),
            "isolated_count": isolated,
            "total_nets": len(nets),
        }

    @staticmethod
    def _value_for_key(payload: Any, key: str) -> Any:
        if isinstance(payload, dict):
            return payload.get(key)
        return getattr(payload, key, None)

    def _extract_visual_graph(self, visual_topology: Dict[str, Any]) -> Tuple[Dict[str, set[str]], Dict[str, str]]:
        graph: Dict[str, set[str]] = {}
        node_class: Dict[str, str] = {}

        for row in (visual_topology.get("component_instances") or []):
            if not isinstance(row, dict):
                continue
            node_id = self._as_text(row.get("instance_id") or row.get("node_id"))
            if not node_id:
                continue
            label = self._normalize_value(
                row.get("class_name")
                or row.get("component_type")
                or row.get("name")
                or row.get("label")
                or "unknown"
            )
            node_class[node_id] = label

        for row in (visual_topology.get("connections") or []):
            c1 = self._value_for_key(row, "component1")
            c2 = self._value_for_key(row, "component2")
            id1 = self._endpoint_key(c1)
            id2 = self._endpoint_key(c2)
            if not id1 or not id2 or id1 == id2:
                continue

            node_class.setdefault(id1, self._normalize_value(self._endpoint_label(c1)))
            node_class.setdefault(id2, self._normalize_value(self._endpoint_label(c2)))
            graph.setdefault(id1, set()).add(id2)
            graph.setdefault(id2, set()).add(id1)

        return graph, node_class

    def _extract_visual_signatures(self, visual_topology: Dict[str, Any]) -> Tuple[Counter[str], Dict[str, int]]:
        if not isinstance(visual_topology, dict):
            return Counter(), {"net_count": 0, "component_count": 0, "isolated_count": 0}

        graph, node_class = self._extract_visual_graph(visual_topology)
        if not graph:
            return Counter(), {"net_count": 0, "component_count": 0, "isolated_count": 0}

        signatures: Counter[str] = Counter()
        component_counts: Counter[str] = Counter()
        visited: set[str] = set()
        isolated = 0

        for node in graph.keys():
            if node in visited:
                continue
            queue = deque([node])
            visited.add(node)
            component_nodes: List[str] = []
            while queue:
                curr = queue.popleft()
                component_nodes.append(curr)
                for nxt in graph.get(curr, set()):
                    if nxt in visited:
                        continue
                    visited.add(nxt)
                    queue.append(nxt)

            types = [node_class.get(n, "unknown") for n in component_nodes]
            if len(types) == 1:
                isolated += 1
            if len(types) < 2:
                component_counts.update(types)
                continue
            sig = self._signature_from_types(types)
            if sig:
                signatures[sig] += 1
            component_counts.update(types)

        return signatures, {
            "net_count": len(signatures),
            "component_count": sum(component_counts.values()),
            "isolated_count": isolated,
        }

    def _diff_rows(self, reference_signatures: Counter[str], visual_signatures: Counter[str]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], int]:
        missing: List[Dict[str, Any]] = []
        extra: List[Dict[str, Any]] = []
        mismatches = 0
        keys = set(reference_signatures.keys()) | set(visual_signatures.keys())
        for key in sorted(keys):
            reference_count = int(reference_signatures.get(key, 0))
            visual_count = int(visual_signatures.get(key, 0))
            if visual_count < reference_count:
                delta = reference_count - visual_count
                missing.append(
                    {
                        "signature": key,
                        "reference": reference_count,
                        "observed": visual_count,
                        "delta": delta,
                    }
                )
                mismatches += delta
            elif visual_count > reference_count:
                delta = visual_count - reference_count
                extra.append(
                    {
                        "signature": key,
                        "reference": reference_count,
                        "observed": visual_count,
                        "delta": delta,
                    }
                )
                mismatches += delta
        return missing, extra, mismatches

    def compare(self, reference_data: Dict[str, Any], visual_topology: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(reference_data, dict):
            raise ValueError("reference_data must be a dictionary")
        if not isinstance(visual_topology, dict):
            raise ValueError("visual_topology must be a dictionary")

        ref_signatures, ref_stats = self.extract_reference_signatures(reference_data)
        vis_signatures, vis_stats = self._extract_visual_signatures(visual_topology)
        matched = sum(
            min(ref_signatures.get(sig, 0), vis_signatures.get(sig, 0))
            for sig in set(ref_signatures.keys()) & set(vis_signatures.keys())
        )
        missing, extra, mismatches = self._diff_rows(ref_signatures, vis_signatures)

        status = "PASS" if not missing and not extra else "FAIL"
        summary = (
            f"Topology AOI: {status}. "
            f"Reference net clusters {ref_stats['net_count']}, observed clusters {vis_stats['net_count']}, "
            f"mismatch {mismatches}."
        )

        return {
            "status": status,
            "reference_signature_count": len(ref_signatures),
            "observed_signature_count": len(vis_signatures),
            "matched_clusters": int(matched),
            "topology_delta": int(mismatches),
            "reference_signatures": [
                {"signature": sig, "count": int(count)}
                for sig, count in sorted(ref_signatures.items(), key=lambda item: (item[0], item[1]))
            ],
            "observed_signatures": [
                {"signature": sig, "count": int(count)}
                for sig, count in sorted(vis_signatures.items(), key=lambda item: (item[0], item[1]))
            ],
            "missing": missing,
            "extra": extra,
            "reference_stats": ref_stats,
            "observed_stats": vis_stats,
            "summary": summary,
            "notes": [
                "Topology AOI compares net-level class signatures extracted from the reference netlist vs visual trace graph."
            ],
        }
