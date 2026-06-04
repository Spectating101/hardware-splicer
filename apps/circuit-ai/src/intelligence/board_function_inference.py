"""
Board-level function inference from visual component detections.

This module intentionally stays conservative: a single image can often reveal
board role and reusable functional blocks, but it cannot prove exact circuit
intent without OCR, datasheets, measurements, or design files.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, Iterable, List, Sequence, Tuple


POWER_CLASSES = {
    "transformer",
    "inductor",
    "mosfet",
    "diode",
    "fuse",
    "varistor",
    "mov",
    "voltage_regulator",
    "regulator",
    "power_ic",
}
CONTROL_CLASSES = {
    "ic",
    "ic_chip",
    "microcontroller",
    "mcu",
    "cpu",
    "processor",
    "memory",
    "flash",
    "crystal",
    "oscillator",
}
INTERFACE_CLASSES = {
    "connector",
    "terminal",
    "header",
    "usb_connector",
    "usb",
    "jack",
    "switch",
    "button",
}
PASSIVE_CLASSES = {"resistor", "capacitor", "cap", "led", "test_point"}
WIRELESS_CLASSES = {"antenna", "wifi", "bluetooth", "rf_module", "esp32", "esp8266"}
ACTUATOR_CLASSES = {"relay", "mosfet", "motor_driver", "driver", "triac"}
SENSOR_CLASSES = {"sensor", "camera", "microphone", "imu", "pressure_sensor", "temperature_sensor"}
DISPLAY_CLASSES = {"display", "lcd", "oled", "seven_segment", "led"}


CLASS_ALIASES = {
    "cap1": "capacitor",
    "cap2": "capacitor",
    "cap3": "capacitor",
    "cap4": "capacitor",
    "capacitor": "capacitor",
    "res": "resistor",
    "resistor": "resistor",
    "ic": "ic_chip",
    "integrated_circuit": "ic_chip",
    "chip": "ic_chip",
    "ic_chip": "ic_chip",
    "mcu": "microcontroller",
    "microcontroller": "microcontroller",
    "mosfet": "mosfet",
    "transistor": "mosfet",
    "transformer": "transformer",
    "diode": "diode",
    "led": "led",
    "connector": "connector",
    "conn": "connector",
    "header": "connector",
    "terminal_block": "connector",
    "terminal": "connector",
    "usb": "usb_connector",
    "usb_connector": "usb_connector",
    "crystal": "crystal",
    "oscillator": "crystal",
    "inductor": "inductor",
    "coil": "inductor",
    "relay": "relay",
    "switch": "switch",
    "button": "switch",
    "fuse": "fuse",
    "mov": "varistor",
    "varistor": "varistor",
    "antenna": "antenna",
    "esp32": "esp32",
    "esp8266": "esp8266",
    "display": "display",
    "lcd": "display",
    "sensor": "sensor",
}


class BoardFunctionInferencer:
    """Infer board role, functional blocks, and reuse/splice candidates."""

    def analyze(
        self,
        detections: Sequence[Any],
        detection_summary: Dict[str, Any] | None = None,
        visual_topology: Dict[str, Any] | None = None,
        defect_inspection: Dict[str, Any] | None = None,
        marking_analysis: Dict[str, Any] | None = None,
        image_shape: Tuple[int, ...] | None = None,
    ) -> Dict[str, Any]:
        components = [self._component_record(det, idx) for idx, det in enumerate(detections or [])]
        counts = Counter(component["class_name"] for component in components)
        text = " ".join(component.get("text", "") for component in components).lower()
        text = f"{text} {self._marking_text(marking_analysis)}".strip()
        topology_conf = float((visual_topology or {}).get("confidence", 0.0) or 0.0)
        detector_quality = str((detection_summary or {}).get("detection_quality", "unknown"))
        learned_ratio = self._learned_detection_ratio(detection_summary or {})

        roles = self._score_roles(counts, text, marking_analysis=marking_analysis)
        primary_role = roles[0] if roles else self._unknown_role()
        blocks = self._infer_functional_blocks(components, counts, image_shape)
        machine_roles = self._infer_machine_roles(primary_role, roles, counts, blocks)
        splice_candidates = self._infer_splice_candidates(components, blocks, defect_inspection, image_shape)
        confidence = self._confidence(
            roles,
            blocks,
            topology_conf=topology_conf,
            learned_ratio=learned_ratio,
            detector_quality=detector_quality,
        )

        return {
            "mode": "image_only_board_function_inference",
            "board_identity": {
                "primary_type": primary_role["type"],
                "description": primary_role["description"],
                "confidence": round(min(confidence, primary_role["score"]), 3),
                "evidence": primary_role["evidence"][:8],
                "alternatives": [
                    {
                        "type": role["type"],
                        "description": role["description"],
                        "confidence": round(role["score"], 3),
                        "evidence": role["evidence"][:5],
                    }
                    for role in roles[1:4]
                ],
            },
            "functional_blocks": blocks,
            "machine_context": {
                "likely_roles": machine_roles,
                "integration_notes": self._integration_notes(primary_role["type"], counts),
                "pinout_evidence": self._pinout_evidence(marking_analysis),
                "connector_label_evidence": (marking_analysis or {}).get("connector_labels", []),
            },
            "reuse_and_splice": {
                "candidate_regions": splice_candidates,
                "board_spec_for_splicer": self._board_spec_for_splicer(
                    components,
                    splice_candidates,
                    image_shape=image_shape,
                    confidence=confidence,
                ),
                "warnings": self._splice_warnings(confidence, defect_inspection, visual_topology),
            },
            "observed_inventory": {
                "component_counts": dict(sorted(counts.items())),
                "recognized_component_count": len(components),
                "resolved_marking_count": len((marking_analysis or {}).get("components", []) or []),
            },
            "confidence": round(confidence, 3),
            "limitations": [
                "single-image inference estimates board role; it does not identify exact manufacturer model",
                "bottom-side parts, hidden traces, multilayer routing, and unlabeled ICs can change function",
                "use OCR markings, datasheets, electrical tests, Gerber/KiCad files, or a known golden board for high-confidence intent",
            ],
        }

    def _score_roles(
        self,
        counts: Counter,
        text: str,
        marking_analysis: Dict[str, Any] | None = None,
    ) -> List[Dict[str, Any]]:
        role_specs = [
            (
                "power_supply_or_regulator",
                "Power conversion, protection, or distribution board",
                {
                    "transformer": 0.34,
                    "inductor": 0.18,
                    "diode": 0.12,
                    "mosfet": 0.11,
                    "capacitor": 0.06,
                    "fuse": 0.14,
                    "varistor": 0.14,
                    "connector": 0.05,
                },
                ["vin", "vout", "ac", "dc", "12v", "24v", "5v", "3v3", "gnd"],
            ),
            (
                "controller_or_embedded_compute",
                "Controller, development, or embedded compute board",
                {
                    "microcontroller": 0.30,
                    "ic_chip": 0.20,
                    "crystal": 0.18,
                    "connector": 0.08,
                    "resistor": 0.04,
                    "capacitor": 0.04,
                    "usb_connector": 0.12,
                },
                ["stm32", "atmega", "esp32", "esp8266", "arduino", "mcu", "boot", "uart", "jtag"],
            ),
            (
                "io_interface_or_adapter",
                "Connector, adapter, breakout, or IO interface board",
                {"connector": 0.28, "usb_connector": 0.22, "resistor": 0.05, "led": 0.08, "switch": 0.10},
                ["usb", "rx", "tx", "sda", "scl", "gpio", "io", "in", "out"],
            ),
            (
                "motor_or_actuator_driver",
                "Motor, relay, solenoid, or high-current actuator driver board",
                {"mosfet": 0.18, "relay": 0.28, "diode": 0.10, "connector": 0.08, "ic_chip": 0.08, "inductor": 0.08},
                ["motor", "relay", "solenoid", "out", "phase", "pwm"],
            ),
            (
                "sensor_or_signal_conditioning",
                "Sensor front-end or signal conditioning board",
                {"sensor": 0.32, "ic_chip": 0.12, "resistor": 0.08, "capacitor": 0.08, "connector": 0.06},
                ["sensor", "temp", "pressure", "imu", "mic", "adc"],
            ),
            (
                "wireless_or_communications",
                "Wireless, RF, or communications module",
                {"antenna": 0.32, "esp32": 0.30, "esp8266": 0.30, "ic_chip": 0.08, "crystal": 0.08, "connector": 0.05},
                ["wifi", "bt", "ble", "rf", "zigbee", "lora", "antenna"],
            ),
            (
                "display_or_user_interface",
                "Display, indicator, button, or user-interface board",
                {"display": 0.34, "led": 0.14, "switch": 0.12, "connector": 0.08, "resistor": 0.05},
                ["lcd", "oled", "display", "key", "btn", "led"],
            ),
        ]

        roles = []
        for role_type, description, weights, keywords in role_specs:
            score = 0.0
            evidence = []
            for cls, weight in weights.items():
                count = counts.get(cls, 0)
                if count:
                    score += min(3, count) * weight
                    evidence.append(f"{count} {cls}")
            keyword_hits = [kw for kw in keywords if kw in text]
            if keyword_hits:
                score += min(0.25, 0.08 * len(keyword_hits))
                evidence.append(f"text hints: {', '.join(keyword_hits[:4])}")
            if score > 0:
                roles.append(
                    {
                        "type": role_type,
                        "description": description,
                        "score": min(0.95, round(score, 3)),
                        "evidence": evidence,
                    }
                )
        roles.sort(key=lambda item: item["score"], reverse=True)
        self._boost_roles_from_markings(roles, marking_analysis)
        roles.sort(key=lambda item: item["score"], reverse=True)
        return roles

    def _infer_functional_blocks(
        self,
        components: List[Dict[str, Any]],
        counts: Counter,
        image_shape: Tuple[int, ...] | None,
    ) -> List[Dict[str, Any]]:
        specs = [
            ("power_input_protection", "Input power/protection", POWER_CLASSES | {"connector"}),
            ("power_regulation", "Voltage regulation/filtering", {"voltage_regulator", "regulator", "inductor", "diode", "capacitor"}),
            ("compute_control", "Compute/control logic", CONTROL_CLASSES | WIRELESS_CLASSES),
            ("io_connectivity", "External IO/connectors", INTERFACE_CLASSES | WIRELESS_CLASSES),
            ("user_interface", "User interface/indication", DISPLAY_CLASSES | {"switch"}),
            ("actuator_drive", "Actuator or high-current output", ACTUATOR_CLASSES | {"diode", "connector"}),
            ("passive_conditioning", "Passive filtering/biasing", {"resistor", "capacitor", "inductor", "diode"}),
            ("sensor_frontend", "Sensor or analog front-end", SENSOR_CLASSES | {"ic_chip", "resistor", "capacitor"}),
        ]
        blocks = []
        for block_type, label, classes in specs:
            block_components = [comp for comp in components if comp["class_name"] in classes]
            if not block_components:
                continue
            if block_type == "sensor_frontend" and not any(comp["class_name"] in SENSOR_CLASSES for comp in block_components):
                continue
            if block_type == "actuator_drive" and not any(comp["class_name"] in ACTUATOR_CLASSES for comp in block_components):
                continue
            bbox = self._union_bbox([comp.get("bbox") for comp in block_components])
            confidence = min(0.9, 0.25 + 0.12 * min(len(block_components), 5))
            if block_type in {"compute_control", "power_input_protection"} and len(block_components) >= 3:
                confidence += 0.1
            blocks.append(
                {
                    "block_type": block_type,
                    "label": label,
                    "component_count": len(block_components),
                    "components": [comp["id"] for comp in block_components[:20]],
                    "bbox": bbox,
                    "confidence": round(min(confidence, 0.95), 3),
                    "function": self._block_function(block_type, counts),
                    "crop_hint": self._crop_hint(bbox, image_shape),
                }
            )
        blocks.sort(key=lambda block: (block["confidence"], block["component_count"]), reverse=True)
        return blocks

    def _infer_machine_roles(
        self,
        primary_role: Dict[str, Any],
        roles: List[Dict[str, Any]],
        counts: Counter,
        blocks: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        mapping = {
            "power_supply_or_regulator": ("power_node", "Supplies, converts, or protects machine power rails"),
            "controller_or_embedded_compute": ("machine_controller", "Runs firmware/control logic and coordinates IO"),
            "io_interface_or_adapter": ("io_breakout", "Connects sensors, actuators, host systems, or service ports"),
            "motor_or_actuator_driver": ("actuator_driver", "Switches current for motors, relays, solenoids, or loads"),
            "sensor_or_signal_conditioning": ("sensor_node", "Measures physical state or conditions analog signals"),
            "wireless_or_communications": ("communication_node", "Adds wireless or protocol connectivity"),
            "display_or_user_interface": ("operator_interface", "Provides machine display, indicators, or controls"),
        }
        result = []
        for role in roles[:4]:
            machine_role, description = mapping.get(role["type"], ("unknown_machine_role", role["description"]))
            result.append(
                {
                    "role": machine_role,
                    "confidence": round(role["score"], 3),
                    "description": description,
                    "evidence": role["evidence"][:5],
                }
            )
        if counts.get("connector", 0) >= 3 and any(block["block_type"] == "compute_control" for block in blocks):
            result.append(
                {
                    "role": "hub_or_backplane_candidate",
                    "confidence": 0.52,
                    "description": "Multiple connectors plus control logic suggest machine harness or module hub behavior",
                    "evidence": [f"{counts.get('connector', 0)} connector"],
                }
            )
        if not result:
            result.append(
                {
                    "role": "unknown_machine_module",
                    "confidence": 0.0,
                    "description": primary_role.get("description", "Unknown board role"),
                    "evidence": [],
                }
            )
        return result

    def _infer_splice_candidates(
        self,
        components: List[Dict[str, Any]],
        blocks: List[Dict[str, Any]],
        defect_inspection: Dict[str, Any] | None,
        image_shape: Tuple[int, ...] | None,
    ) -> List[Dict[str, Any]]:
        candidates = []
        for block in blocks:
            if block["block_type"] not in {
                "power_regulation",
                "compute_control",
                "io_connectivity",
                "actuator_drive",
                "sensor_frontend",
                "user_interface",
            }:
                continue
            bbox = block.get("bbox") or []
            risk = self._region_risk(bbox, defect_inspection)
            candidates.append(
                {
                    "region_id": f"crop_{len(candidates) + 1}_{block['block_type']}",
                    "source_block": block["block_type"],
                    "bbox": bbox,
                    "crop_bbox": self._expanded_bbox(bbox, image_shape, margin_ratio=0.18),
                    "confidence": round(max(0.0, block["confidence"] - risk["penalty"]), 3),
                    "reuse_mode": self._reuse_mode(block["block_type"]),
                    "splice_requirements": self._splice_requirements(block["block_type"]),
                    "risk": risk,
                }
            )
        candidates.sort(key=lambda item: item["confidence"], reverse=True)
        return candidates[:8]

    def _board_spec_for_splicer(
        self,
        components: List[Dict[str, Any]],
        candidates: List[Dict[str, Any]],
        image_shape: Tuple[int, ...] | None,
        confidence: float,
    ) -> Dict[str, Any]:
        height = int(image_shape[0]) if image_shape and len(image_shape) >= 2 else None
        width = int(image_shape[1]) if image_shape and len(image_shape) >= 2 else None
        ports = [
            {
                "id": comp["id"],
                "kind": comp["class_name"],
                "bbox_px": comp.get("bbox", []),
                "center_px": comp.get("center", []),
                "confidence": comp.get("confidence", 0.0),
            }
            for comp in components
            if comp["class_name"] in INTERFACE_CLASSES | WIRELESS_CLASSES
        ][:20]
        keepouts = [
            {"id": comp["id"], "kind": comp["class_name"], "bbox_px": comp.get("bbox", [])}
            for comp in components
            if comp["class_name"] in POWER_CLASSES | ACTUATOR_CLASSES
        ][:20]
        return {
            "coordinate_system": "image_pixels",
            "bbox_px": [0, 0, width, height] if width and height else [],
            "confidence": round(confidence, 3),
            "components": [
                {
                    "id": comp["id"],
                    "class_name": comp["class_name"],
                    "bbox_px": comp.get("bbox", []),
                    "confidence": comp.get("confidence", 0.0),
                }
                for comp in components[:80]
            ],
            "io_ports": ports,
            "keepouts": keepouts,
            "candidate_crops": [
                {
                    "id": candidate["region_id"],
                    "bbox_px": candidate["crop_bbox"],
                    "source_block": candidate["source_block"],
                    "confidence": candidate["confidence"],
                }
                for candidate in candidates
            ],
            "splicer_notes": [
                "pixel geometry must be calibrated to mm before mechanical placement",
                "mounting holes, board thickness, connector height, and cable clearance require measurement or CAD",
                "do electrical validation before powering any harvested/spliced module",
            ],
        }

    def _confidence(
        self,
        roles: List[Dict[str, Any]],
        blocks: List[Dict[str, Any]],
        topology_conf: float,
        learned_ratio: float,
        detector_quality: str,
    ) -> float:
        role_conf = roles[0]["score"] if roles else 0.0
        block_conf = min(0.8, 0.12 * len(blocks))
        quality_bonus = {"high": 0.12, "medium": 0.06}.get(detector_quality, 0.0)
        return max(
            0.0,
            min(
                0.92,
                0.45 * role_conf
                + 0.20 * block_conf
                + 0.15 * topology_conf
                + 0.15 * learned_ratio
                + quality_bonus,
            ),
        )

    def _marking_text(self, marking_analysis: Dict[str, Any] | None) -> str:
        if not marking_analysis:
            return ""
        chunks = list(marking_analysis.get("connector_labels", []) or [])
        for component in marking_analysis.get("components", []) or []:
            chunks.extend(component.get("part_tokens", []) or [])
            for candidate in component.get("candidates", []) or []:
                chunks.append(str(candidate.get("part_number", "")))
                datasheet = candidate.get("datasheet") if isinstance(candidate.get("datasheet"), dict) else {}
                chunks.extend(str(value) for value in (datasheet.get("key_specs") or {}).values())
                pinout = candidate.get("pinout") if isinstance(candidate.get("pinout"), dict) else {}
                chunks.append(str(pinout.get("description", "")))
        return " ".join(chunks).lower()

    def _boost_roles_from_markings(
        self,
        roles: List[Dict[str, Any]],
        marking_analysis: Dict[str, Any] | None,
    ) -> None:
        if not marking_analysis:
            return
        part_text = self._marking_text(marking_analysis)
        boosts = {
            "controller_or_embedded_compute": ["atmega", "stm32", "pic", "esp32", "esp8266", "mcu", "microcontroller"],
            "wireless_or_communications": ["esp32", "esp8266", "wifi", "bluetooth", "rf", "lora"],
            "power_supply_or_regulator": ["lm7805", "ams1117", "lm2596", "regulator", "voltage", "12v", "5v", "3.3v"],
            "io_interface_or_adapter": ["ch340", "cp2102", "ft232", "usb", "uart", "sda", "scl", "tx", "rx"],
            "sensor_or_signal_conditioning": ["bmp280", "ads1115", "sensor", "adc", "pressure", "temperature"],
            "motor_or_actuator_driver": ["uln2003", "motor", "relay", "driver", "mosfet"],
        }
        by_type = {role["type"]: role for role in roles}
        for role_type, keywords in boosts.items():
            hits = [keyword for keyword in keywords if keyword in part_text]
            if not hits:
                continue
            if role_type not in by_type:
                by_type[role_type] = {
                    "type": role_type,
                    "description": self._role_description(role_type),
                    "score": 0.0,
                    "evidence": [],
                }
                roles.append(by_type[role_type])
            role = by_type[role_type]
            role["score"] = min(0.95, float(role.get("score", 0.0)) + min(0.28, 0.10 * len(hits)))
            role.setdefault("evidence", []).append(f"marking evidence: {', '.join(hits[:4])}")

    def _role_description(self, role_type: str) -> str:
        return {
            "power_supply_or_regulator": "Power conversion, protection, or distribution board",
            "controller_or_embedded_compute": "Controller, development, or embedded compute board",
            "io_interface_or_adapter": "Connector, adapter, breakout, or IO interface board",
            "motor_or_actuator_driver": "Motor, relay, solenoid, or high-current actuator driver board",
            "sensor_or_signal_conditioning": "Sensor front-end or signal conditioning board",
            "wireless_or_communications": "Wireless, RF, or communications module",
            "display_or_user_interface": "Display, indicator, button, or user-interface board",
        }.get(role_type, "Unknown board role")

    def _pinout_evidence(self, marking_analysis: Dict[str, Any] | None) -> List[Dict[str, Any]]:
        evidence = []
        for component in (marking_analysis or {}).get("components", []) or []:
            for candidate in component.get("candidates", []) or []:
                pinout = candidate.get("pinout") if isinstance(candidate.get("pinout"), dict) else None
                if not pinout:
                    continue
                evidence.append(
                    {
                        "component_id": component.get("component_id"),
                        "part_number": candidate.get("part_number"),
                        "pin_count": pinout.get("pin_count"),
                        "package": pinout.get("package"),
                        "power_pins": pinout.get("power_pins", [])[:6],
                        "programming_or_clock_pins": pinout.get("programming_or_clock_pins", [])[:6],
                    }
                )
        return evidence[:12]

    def _component_record(self, detection: Any, index: int) -> Dict[str, Any]:
        if isinstance(detection, dict):
            raw_class = detection.get("class_name") or detection.get("label") or detection.get("type")
            bbox = detection.get("bbox") or []
            center = detection.get("center") or self._center_from_bbox(bbox)
            confidence = detection.get("confidence", detection.get("score", 0.0))
            text = detection.get("text_content") or detection.get("ocr_text") or detection.get("text") or ""
        else:
            raw_class = getattr(detection, "class_name", None) or getattr(detection, "label", None)
            bbox = getattr(detection, "bbox", []) or []
            center = getattr(detection, "center", None) or self._center_from_bbox(bbox)
            confidence = getattr(detection, "confidence", 0.0)
            text = getattr(detection, "text_content", "") or getattr(detection, "ocr_text", "")
        class_name = self._normalize_class(raw_class)
        return {
            "id": f"cmp_{index}_{class_name}",
            "class_name": class_name,
            "raw_class_name": str(raw_class or "unknown"),
            "bbox": self._clean_bbox(bbox),
            "center": self._clean_point(center),
            "confidence": round(float(confidence or 0.0), 3),
            "text": str(text or ""),
        }

    def _learned_detection_ratio(self, detection_summary: Dict[str, Any]) -> float:
        total = float(detection_summary.get("total_components", 0) or 0)
        if total <= 0:
            return 0.0
        breakdown = detection_summary.get("backend_breakdown") or {}
        learned = sum(count for backend, count in breakdown.items() if str(backend).startswith("yolo"))
        return min(1.0, float(learned) / total)

    def _region_risk(self, bbox: List[int], defect_inspection: Dict[str, Any] | None) -> Dict[str, Any]:
        defects = (defect_inspection or {}).get("defects") or []
        overlaps = []
        for defect in defects:
            defect_bbox = defect.get("bbox") if isinstance(defect, dict) else None
            if self._iou(bbox, defect_bbox) > 0.02:
                overlaps.append(defect)
        max_severity = max((float(defect.get("severity", 0.0) or 0.0) for defect in overlaps), default=0.0)
        return {
            "level": "high" if max_severity >= 0.7 else "medium" if overlaps else "low",
            "overlapping_defects": len(overlaps),
            "penalty": round(0.25 * max_severity + 0.05 * min(len(overlaps), 3), 3),
        }

    def _splice_warnings(
        self,
        confidence: float,
        defect_inspection: Dict[str, Any] | None,
        visual_topology: Dict[str, Any] | None,
    ) -> List[str]:
        warnings = [
            "crop/splice output is planning metadata only; it is not a validated mechanical or electrical design",
        ]
        if confidence < 0.55:
            warnings.append("board role confidence is low; collect OCR, reverse-side image, or design files before reuse")
        if (visual_topology or {}).get("confidence", 0.0) < 0.45:
            warnings.append("visual topology confidence is low; hidden nets may make extracted modules unusable")
        if int((defect_inspection or {}).get("defect_count", 0) or 0) > 0:
            warnings.append("defect candidates overlap may make harvested regions risky")
        return warnings

    def _block_function(self, block_type: str, counts: Counter) -> str:
        functions = {
            "power_input_protection": "Accepts incoming power and protects downstream circuitry",
            "power_regulation": "Converts, filters, or stabilizes board power rails",
            "compute_control": "Runs logic, timing, firmware, or protocol control",
            "io_connectivity": "Provides external electrical connections to a machine or host",
            "user_interface": "Displays status or accepts operator input",
            "actuator_drive": "Switches higher current loads from low-power control signals",
            "passive_conditioning": "Filters, biases, divides, limits current, or shapes signals",
            "sensor_frontend": "Measures physical signals or conditions sensor output",
        }
        return functions.get(block_type, "Unknown functional block")

    def _reuse_mode(self, block_type: str) -> str:
        return {
            "power_regulation": "harvest_as_power_submodule",
            "compute_control": "reuse_or_reprogram_controller_region",
            "io_connectivity": "reuse_as_connector_adapter_or_harness_anchor",
            "actuator_drive": "harvest_as_load_driver_after_current_validation",
            "sensor_frontend": "reuse_as_sensor_or_measurement_frontend",
            "user_interface": "reuse_as_indicator_or_control_panel",
        }.get(block_type, "inspect_before_reuse")

    def _splice_requirements(self, block_type: str) -> List[str]:
        base = ["confirm pinout", "measure supply rails", "inspect both sides", "verify isolation/clearance"]
        extras = {
            "compute_control": ["identify MCU/IC markings", "confirm programming/debug interface"],
            "power_regulation": ["load-test output", "verify input voltage range", "thermal check"],
            "io_connectivity": ["map connector pins", "confirm mating connector and cable clearance"],
            "actuator_drive": ["measure load current", "add flyback/ESD protection as needed"],
            "sensor_frontend": ["calibrate sensor", "identify analog/digital interface"],
            "user_interface": ["map buttons/LEDs/display interface"],
        }
        return base + extras.get(block_type, [])

    def _integration_notes(self, primary_type: str, counts: Counter) -> List[str]:
        notes = []
        if primary_type == "power_supply_or_regulator":
            notes.append("Treat as an energy source or power rail module; validate voltage, current, isolation, and heat before connecting machinery.")
        elif primary_type == "controller_or_embedded_compute":
            notes.append("Treat as a control node; OCR chip markings and locate programming/debug headers before trying firmware reuse.")
        elif primary_type == "motor_or_actuator_driver":
            notes.append("Treat outputs as high-current paths; confirm load rating and protection before driving actuators.")
        elif primary_type == "io_interface_or_adapter":
            notes.append("Treat connectors as machine interface points; build a pin map before splicing harnesses.")
        else:
            notes.append("Use this as a triage result; add OCR, reverse-side scan, and electrical probes for confident integration.")
        if counts.get("connector", 0) or counts.get("usb_connector", 0):
            notes.append("Connector regions are the best starting point for pinout tracing and machine-level integration.")
        return notes

    def _crop_hint(self, bbox: List[int], image_shape: Tuple[int, ...] | None) -> Dict[str, Any]:
        return {
            "suggested_crop_bbox": self._expanded_bbox(bbox, image_shape, margin_ratio=0.15),
            "include_margin": "15% around block bbox",
        }

    def _unknown_role(self) -> Dict[str, Any]:
        return {
            "type": "unknown_board",
            "description": "Board role could not be inferred from visible components",
            "score": 0.0,
            "evidence": [],
        }

    def _normalize_class(self, value: Any) -> str:
        name = str(value or "unknown").strip().lower().replace(" ", "_").replace("-", "_")
        return CLASS_ALIASES.get(name, name)

    def _union_bbox(self, boxes: Iterable[Any]) -> List[int]:
        clean = [self._clean_bbox(box) for box in boxes]
        clean = [box for box in clean if len(box) == 4]
        if not clean:
            return []
        return [
            min(box[0] for box in clean),
            min(box[1] for box in clean),
            max(box[2] for box in clean),
            max(box[3] for box in clean),
        ]

    def _expanded_bbox(
        self,
        bbox: List[int],
        image_shape: Tuple[int, ...] | None,
        margin_ratio: float,
    ) -> List[int]:
        if len(bbox) != 4:
            return []
        x1, y1, x2, y2 = bbox
        margin = int(round(max(x2 - x1, y2 - y1) * margin_ratio))
        width = int(image_shape[1]) if image_shape and len(image_shape) >= 2 else None
        height = int(image_shape[0]) if image_shape and len(image_shape) >= 2 else None
        return [
            max(0, x1 - margin),
            max(0, y1 - margin),
            min(width if width is not None else x2 + margin, x2 + margin),
            min(height if height is not None else y2 + margin, y2 + margin),
        ]

    def _clean_bbox(self, bbox: Any) -> List[int]:
        if not isinstance(bbox, (list, tuple)) or len(bbox) < 4:
            return []
        return [int(round(float(v))) for v in bbox[:4]]

    def _clean_point(self, point: Any) -> List[int]:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            return []
        return [int(round(float(v))) for v in point[:2]]

    def _center_from_bbox(self, bbox: Any) -> List[int]:
        clean = self._clean_bbox(bbox)
        if len(clean) != 4:
            return []
        return [int(round((clean[0] + clean[2]) / 2)), int(round((clean[1] + clean[3]) / 2))]

    def _iou(self, bbox_a: Any, bbox_b: Any) -> float:
        a = self._clean_bbox(bbox_a)
        b = self._clean_bbox(bbox_b)
        if len(a) != 4 or len(b) != 4:
            return 0.0
        x1 = max(a[0], b[0])
        y1 = max(a[1], b[1])
        x2 = min(a[2], b[2])
        y2 = min(a[3], b[3])
        inter = max(0, x2 - x1) * max(0, y2 - y1)
        area_a = max(0, a[2] - a[0]) * max(0, a[3] - a[1])
        area_b = max(0, b[2] - b[0]) * max(0, b[3] - b[1])
        union = area_a + area_b - inter
        return float(inter) / float(union) if union > 0 else 0.0
