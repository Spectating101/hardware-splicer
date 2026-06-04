"""Machine-level connector and pinout planning from board evidence."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Sequence


POWER_LABELS = {"VIN", "VCC", "VDD", "3V3", "5V", "12V", "24V", "GND"}
SERIAL_LABELS = {"TX", "RX", "UART"}
I2C_LABELS = {"SDA", "SCL"}
SPI_LABELS = {"MISO", "MOSI", "SCK", "CS"}
CONTROL_LABELS = {"RST", "RESET", "EN"}
OUTPUT_LABELS = {"MOTOR", "OUT", "OUT1", "OUT2", "IN", "IN1", "IN2"}


class ConnectionMapper:
    """Build a practical connector/pinout map for machine integration."""

    def map_connections(
        self,
        detections: Sequence[Any],
        marking_analysis: Dict[str, Any] | None = None,
        board_understanding: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        connectors = self._connector_records(detections)
        labels = [str(label).upper() for label in (marking_analysis or {}).get("connector_labels", []) or []]
        pinout_evidence = ((board_understanding or {}).get("machine_context") or {}).get("pinout_evidence", []) or []
        interfaces = self._interfaces_from_labels(labels, pinout_evidence)
        connector_maps = [
            self._map_connector(connector, labels, interfaces, index)
            for index, connector in enumerate(connectors)
        ]
        splice_plan = self._splice_plan(connector_maps, interfaces, board_understanding)
        confidence = self._confidence(connector_maps, labels, pinout_evidence)

        return {
            "mode": "machine_connection_map",
            "connector_count": len(connectors),
            "connector_maps": connector_maps,
            "interfaces": interfaces,
            "pinout_evidence": pinout_evidence[:20],
            "splice_plan": splice_plan,
            "confidence": round(confidence, 3),
            "limitations": [
                "pin assignments are inferred from labels and known pinouts; verify with continuity and voltage measurements",
                "image-only connector geometry cannot determine exact pin order without calibration or close-up photos",
                "do not power harvested modules until polarity, rails, and isolation are confirmed",
            ],
        }

    def _connector_records(self, detections: Sequence[Any]) -> List[Dict[str, Any]]:
        records = []
        for idx, detection in enumerate(detections or []):
            if isinstance(detection, dict):
                class_name = str(detection.get("class_name") or detection.get("label") or "")
                bbox = detection.get("bbox") or []
                center = detection.get("center") or self._center(bbox)
                confidence = detection.get("confidence", 0.0)
                text = detection.get("ocr_text") or detection.get("text_content") or detection.get("text") or ""
            else:
                class_name = str(getattr(detection, "class_name", ""))
                bbox = getattr(detection, "bbox", []) or []
                center = getattr(detection, "center", None) or self._center(bbox)
                confidence = getattr(detection, "confidence", 0.0)
                text = getattr(detection, "ocr_text", "") or getattr(detection, "text_content", "")
            normalized = class_name.strip().lower().replace("-", "_").replace(" ", "_")
            if normalized not in {"connector", "usb_connector", "terminal", "header", "jack", "switch"}:
                continue
            records.append(
                {
                    "id": f"conn_{idx}_{normalized}",
                    "class_name": normalized,
                    "bbox": self._bbox(bbox),
                    "center": self._point(center),
                    "confidence": round(float(confidence or 0.0), 3),
                    "text": str(text or ""),
                    "estimated_pin_count": self._estimate_pin_count(bbox, normalized),
                }
            )
        return records

    def _interfaces_from_labels(
        self,
        labels: List[str],
        pinout_evidence: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        label_set = set(labels)
        interfaces = []
        if label_set & POWER_LABELS:
            interfaces.append(
                {
                    "type": "power",
                    "labels": sorted(label_set & POWER_LABELS),
                    "confidence": 0.72 if {"GND"} & label_set else 0.55,
                    "validation": ["measure voltage before connection", "confirm polarity", "check current limit"],
                }
            )
        if SERIAL_LABELS.issubset(label_set) or {"TX", "RX"} & label_set:
            interfaces.append(
                {
                    "type": "uart_serial",
                    "labels": sorted(label_set & SERIAL_LABELS),
                    "confidence": 0.68,
                    "validation": ["confirm logic level", "cross TX/RX correctly", "share ground"],
                }
            )
        if I2C_LABELS.issubset(label_set):
            interfaces.append(
                {
                    "type": "i2c",
                    "labels": ["SCL", "SDA"],
                    "confidence": 0.7,
                    "validation": ["verify pullups", "confirm voltage domain", "scan bus address"],
                }
            )
        if SPI_LABELS & label_set:
            interfaces.append(
                {
                    "type": "spi",
                    "labels": sorted(label_set & SPI_LABELS),
                    "confidence": 0.58,
                    "validation": ["identify chip select", "confirm mode/clock", "share ground"],
                }
            )
        if CONTROL_LABELS & label_set:
            interfaces.append(
                {
                    "type": "reset_enable",
                    "labels": sorted(label_set & CONTROL_LABELS),
                    "confidence": 0.52,
                    "validation": ["confirm active polarity", "use high impedance probe first"],
                }
            )
        if OUTPUT_LABELS & label_set:
            interfaces.append(
                {
                    "type": "actuator_or_load_output",
                    "labels": sorted(label_set & OUTPUT_LABELS),
                    "confidence": 0.5,
                    "validation": ["load-test output", "confirm flyback protection", "measure max current"],
                }
            )
        for evidence in pinout_evidence:
            part = evidence.get("part_number")
            if not part:
                continue
            interfaces.append(
                {
                    "type": "known_ic_pinout",
                    "part_number": part,
                    "pin_count": evidence.get("pin_count"),
                    "confidence": 0.74,
                    "validation": ["verify package orientation", "match pin 1 marker", "confirm continuity to connector"],
                }
            )
        return interfaces

    def _map_connector(
        self,
        connector: Dict[str, Any],
        labels: List[str],
        interfaces: List[Dict[str, Any]],
        index: int,
    ) -> Dict[str, Any]:
        nearby_labels = labels if len(labels) <= 12 else labels[:12]
        likely_roles = []
        if set(nearby_labels) & POWER_LABELS:
            likely_roles.append("power_or_ground")
        if set(nearby_labels) & (SERIAL_LABELS | I2C_LABELS | SPI_LABELS):
            likely_roles.append("data_or_programming")
        if set(nearby_labels) & OUTPUT_LABELS:
            likely_roles.append("load_output")
        if not likely_roles:
            likely_roles.append("unlabeled_external_interface")

        return {
            "connector_id": connector["id"],
            "bbox": connector.get("bbox", []),
            "center": connector.get("center", []),
            "class_name": connector.get("class_name", "connector"),
            "estimated_pin_count": connector.get("estimated_pin_count"),
            "labels": nearby_labels,
            "likely_roles": likely_roles,
            "candidate_pin_groups": self._candidate_pin_groups(nearby_labels),
            "confidence": round(min(0.85, 0.35 + 0.08 * len(nearby_labels) + 0.05 * len(interfaces)), 3),
            "recommended_next_photo": "close_up_connector_side" if index == 0 else "close_up_connector_label",
        }

    def _candidate_pin_groups(self, labels: Iterable[str]) -> List[Dict[str, Any]]:
        label_set = set(labels)
        groups = []
        for group_type, group_labels in [
            ("power", POWER_LABELS),
            ("uart", SERIAL_LABELS),
            ("i2c", I2C_LABELS),
            ("spi", SPI_LABELS),
            ("control", CONTROL_LABELS),
            ("load", OUTPUT_LABELS),
        ]:
            matches = sorted(label_set & group_labels)
            if matches:
                groups.append({"type": group_type, "labels": matches})
        return groups

    def _splice_plan(
        self,
        connector_maps: List[Dict[str, Any]],
        interfaces: List[Dict[str, Any]],
        board_understanding: Dict[str, Any] | None,
    ) -> Dict[str, Any]:
        role = ((board_understanding or {}).get("board_identity") or {}).get("primary_type", "unknown_board")
        return {
            "safest_entry_points": [
                item["connector_id"]
                for item in connector_maps
                if "power_or_ground" in item.get("likely_roles", []) or "data_or_programming" in item.get("likely_roles", [])
            ][:6],
            "required_measurements": self._required_measurements(role, interfaces),
            "do_not_assume": [
                "pin order",
                "voltage level",
                "shared ground",
                "connector current rating",
                "firmware protocol",
            ],
        }

    def _required_measurements(self, role: str, interfaces: List[Dict[str, Any]]) -> List[str]:
        measurements = ["continuity from connector to ground", "unpowered resistance between power and ground"]
        if any(interface.get("type") == "power" for interface in interfaces) or "power" in role:
            measurements.extend(["powered voltage at each rail", "current draw under current-limited supply"])
        if any(interface.get("type") in {"uart_serial", "i2c", "spi"} for interface in interfaces):
            measurements.extend(["logic high voltage", "signal idle state", "protocol capture if powered safely"])
        if "actuator" in role or any(interface.get("type") == "actuator_or_load_output" for interface in interfaces):
            measurements.extend(["load output voltage", "max load current", "flyback/protection diode continuity"])
        return measurements

    def _confidence(
        self,
        connector_maps: List[Dict[str, Any]],
        labels: List[str],
        pinout_evidence: List[Dict[str, Any]],
    ) -> float:
        if not connector_maps:
            return 0.0
        return min(
            0.9,
            0.25
            + 0.08 * min(len(connector_maps), 4)
            + 0.04 * min(len(set(labels)), 8)
            + 0.12 * min(len(pinout_evidence), 3),
        )

    def _estimate_pin_count(self, bbox: Any, class_name: str) -> int | None:
        box = self._bbox(bbox)
        if len(box) != 4:
            return None
        width = max(1, box[2] - box[0])
        height = max(1, box[3] - box[1])
        long_side = max(width, height)
        if class_name == "usb_connector":
            return 4
        if long_side < 40:
            return None
        return max(2, min(40, round(long_side / 18)))

    def _bbox(self, bbox: Any) -> List[int]:
        if not isinstance(bbox, (list, tuple)) or len(bbox) < 4:
            return []
        return [int(round(float(value))) for value in bbox[:4]]

    def _point(self, point: Any) -> List[int]:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            return []
        return [int(round(float(value))) for value in point[:2]]

    def _center(self, bbox: Any) -> List[int]:
        box = self._bbox(bbox)
        if len(box) != 4:
            return []
        return [int(round((box[0] + box[2]) / 2)), int(round((box[1] + box[3]) / 2))]
