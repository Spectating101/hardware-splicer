"""Plan safe reuse, rewiring, and splicing from salvaged electronics."""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, Iterable, List, Sequence

from src.intelligence.circuit_ai_reasoner import CircuitAIReasoner


class SalvageSplicePlanner:
    """Turn junk-device evidence into reusable blocks and build/splice plans."""

    BUILD_CATALOG = [
        {
            "id": "usb_fume_extractor",
            "name": "USB fume extractor or bench cooling fan",
            "requires_any": [{"motor_or_load", "fan_or_pump"}, {"actuator_driver"}, {"power"}],
            "nice_to_have": {"switch_or_button", "connector", "enclosure_candidate", "filter_frame"},
            "value_usd": 18.0,
            "difficulty": "easy",
            "output_function": "moves air for cooling, drying, or solder-fume capture",
        },
        {
            "id": "inspection_motion_fixture",
            "name": "Inspection light and motion fixture",
            "requires_any": [{"mechanical_motion"}, {"led_or_light", "camera_or_vision"}, {"power"}],
            "nice_to_have": {"sensor_or_adc", "switch_or_button", "connector", "enclosure_candidate", "display_or_ui"},
            "value_usd": 28.0,
            "difficulty": "medium",
            "output_function": "moves a light/camera/sensor along a rail for inspection, scanning, cleaning checks, or repeatable documentation",
        },
        {
            "id": "low_voltage_motor_test_jig",
            "name": "Low-voltage motor/load test jig",
            "requires_any": [{"motor_or_load", "fan_or_pump", "mechanical_motion"}, {"power"}, {"connector", "switch_or_button"}],
            "nice_to_have": {"switch_or_button", "display_or_ui", "actuator_driver", "wheel_or_drive"},
            "value_usd": 16.0,
            "difficulty": "easy",
            "output_function": "bench fixture for testing small motors, pumps, LEDs, and harnesses",
        },
        {
            "id": "robot_drive_base",
            "name": "Small robot drive base",
            "requires_any": [{"motor_or_load", "wheel_or_drive"}, {"actuator_driver", "controller"}, {"power"}],
            "nice_to_have": {"wireless", "connector", "switch_or_button", "sensor_or_adc", "enclosure_candidate"},
            "value_usd": 26.0,
            "difficulty": "medium",
            "output_function": "mobile base for toy robotics, camera sliders, or small automation experiments",
        },
        {
            "id": "plotter_motion_stage",
            "name": "Printer/scanner motion stage",
            "requires_any": [{"mechanical_motion"}, {"switch_or_button", "sensor_or_adc"}, {"power"}],
            "nice_to_have": {"connector", "wheel_or_drive", "enclosure_candidate"},
            "value_usd": 20.0,
            "difficulty": "medium",
            "output_function": "salvaged motion axis for plotters, camera sliders, test fixtures, or tiny CNC experiments",
        },
        {
            "id": "smart_relay_box",
            "name": "Smart relay or low-voltage load controller",
            "requires_any": [{"controller"}, {"actuator_driver"}, {"power"}],
            "nice_to_have": {"wireless", "connector", "enclosure_candidate", "switch_or_button"},
            "value_usd": 24.0,
            "difficulty": "medium",
            "output_function": "controlled switching for LEDs, small pumps, fans, and fixtures",
        },
        {
            "id": "sensor_logger",
            "name": "Sensor logger or alert module",
            "requires_any": [{"controller"}, {"sensor_or_adc"}, {"power"}],
            "nice_to_have": {"wireless", "display_or_ui", "connector"},
            "value_usd": 22.0,
            "difficulty": "medium",
            "output_function": "logs temperature, humidity, current, voltage, or switch state",
        },
        {
            "id": "network_status_indicator",
            "name": "Network status light or WiFi indicator",
            "requires_any": [{"wireless", "network_interface"}, {"display_or_ui", "led_or_light"}, {"power"}],
            "nice_to_have": {"connector", "enclosure_candidate", "switch_or_button", "controller"},
            "value_usd": 15.0,
            "difficulty": "medium",
            "output_function": "network/link/status indicator using router LEDs, antenna, or WiFi modules",
        },
        {
            "id": "small_audio_amp_box",
            "name": "Small powered speaker or alert box",
            "requires_any": [{"speaker_or_audio"}, {"power"}, {"switch_or_button", "connector"}],
            "nice_to_have": {"battery", "enclosure_candidate", "display_or_ui", "controller"},
            "value_usd": 18.0,
            "difficulty": "easy",
            "output_function": "bench audio monitor, alert speaker, or tiny powered speaker enclosure",
        },
        {
            "id": "salvaged_input_panel",
            "name": "Input panel, macro pad, mouse, or controller tester",
            "requires_any": [{"switch_or_button"}, {"connector"}, {"power", "controller"}],
            "nice_to_have": {"display_or_ui", "enclosure_candidate", "usb_serial", "led_or_light"},
            "value_usd": 13.0,
            "difficulty": "easy",
            "output_function": "reuses buttons, joysticks, mouse switches, keyboards, and shells as a control panel or test fixture",
        },
        {
            "id": "camera_ir_light_or_sensor_mount",
            "name": "Camera/IR light or sensor mount",
            "requires_any": [{"camera_or_vision", "sensor_or_adc"}, {"power"}, {"enclosure_candidate", "connector"}],
            "nice_to_have": {"led_or_light", "wireless", "switch_or_button"},
            "value_usd": 17.0,
            "difficulty": "medium",
            "output_function": "inspection light, camera mount, IR illuminator, or sensor fixture",
        },
        {
            "id": "bench_power_adapter",
            "name": "Bench power adapter or breakout",
            "requires_any": [{"power"}, {"connector"}],
            "nice_to_have": {"display_or_ui", "switch_or_button", "enclosure_candidate"},
            "value_usd": 14.0,
            "difficulty": "easy",
            "output_function": "known-voltage breakout with safer connectors and fusing",
        },
        {
            "id": "usb_uart_debug_adapter",
            "name": "USB/UART debug adapter",
            "requires_any": [{"usb_serial"}, {"connector"}],
            "nice_to_have": {"controller", "enclosure_candidate"},
            "value_usd": 9.0,
            "difficulty": "easy",
            "output_function": "serial console, firmware logs, and board bring-up",
        },
        {
            "id": "indicator_or_task_light",
            "name": "Indicator light or small task lamp",
            "requires_any": [{"display_or_ui", "led_or_light"}, {"power"}],
            "nice_to_have": {"switch_or_button", "connector", "enclosure_candidate"},
            "value_usd": 12.0,
            "difficulty": "easy",
            "output_function": "status indicator, cabinet light, or bench lamp",
        },
    ]

    HARD_HAZARD_TERMS = {
        "mains",
        "ac line",
        "120v",
        "240v",
        "crt",
        "microwave",
        "neon",
        "inverter",
        "high voltage",
        "laser diode",
        "exposed laser",
        "swollen",
        "punctured",
        "leaking lithium",
    }

    def plan(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        text = self._case_text(payload)
        analysis = payload.get("analysis") if isinstance(payload.get("analysis"), dict) else {}
        functional_reports = self._functional_salvage_reports(payload, analysis)
        functional_blocks = self._blocks_from_functional_salvage(functional_reports)
        inventory_blocks = self._blocks_from_inventory(payload.get("inventory") or payload.get("modules") or payload.get("available_parts"))
        text_blocks = self._text_blocks_for_case(payload, inventory_blocks)
        blocks = self._dedupe_blocks(
            functional_blocks
            + self._blocks_from_analysis(analysis)
            + inventory_blocks
            + text_blocks
        )
        capability_counts = Counter(cap for block in blocks for cap in block.get("capabilities", []))
        hazards = self._hazards(text, blocks)
        candidates = self._build_candidates(capability_counts, blocks, hazards, text)
        splice_plan = self._splice_plan(payload, analysis, blocks, candidates, hazards, functional_reports=functional_reports)
        evidence_plan = self._evidence_plan(blocks, splice_plan, hazards)
        verdict = self._verdict(blocks, candidates, hazards, evidence_plan)
        confidence = self._confidence(blocks, candidates, hazards, analysis)
        functional_reuse_plan = self._functional_reuse_plan(functional_reports, blocks, splice_plan, verdict)
        circuit_reasoning = CircuitAIReasoner(
            enable_llm=bool(payload.get("use_llm_reasoner") or payload.get("use_llm")),
        ).assess(
            {
                "goal": payload.get("goal"),
                "analysis": analysis,
                "salvage_plan": {
                    "verdict": verdict,
                    "splice_plan": splice_plan,
                    "evidence_plan": evidence_plan,
                    "functional_reuse_plan": functional_reuse_plan,
                },
                "functional_reuse_plan": functional_reuse_plan,
            }
        )
        if verdict == "unsafe_hold":
            top = {
                "id": "safety_hold",
                "name": "Safety hold before salvage",
                "output_function": "recover only clearly isolated low-voltage parts after a separate safety review",
            }
        else:
            top = candidates[0] if candidates else {}
        return {
            "mode": "salvage_splice_reuse_plan",
            "verdict": verdict,
            "confidence": confidence,
            "target": {
                "requested_goal": str(payload.get("goal") or "reuse useful functions from junk electronics"),
                "recommended_build_id": top.get("id"),
                "recommended_build": top.get("name"),
                "output_function": top.get("output_function"),
            },
            "reusable_blocks": blocks,
            "capability_summary": dict(sorted(capability_counts.items())),
            "build_candidates": candidates,
            "splice_plan": splice_plan,
            "functional_reuse_plan": functional_reuse_plan,
            "circuit_reasoning": circuit_reasoning,
            "integration_contract": self._integration_contract(blocks, top, splice_plan, hazards),
            "evidence_plan": evidence_plan,
            "stop_conditions": self._stop_conditions(hazards, blocks),
            "value_tracking": {
                "goal": "salvage_to_build",
                "outcome_decisions": ["reused", "built", "salvaged", "sold", "unsafe_hold", "not_worth_it"],
                "proof_fields": [
                    "before item/source",
                    "blocks recovered",
                    "measurements recorded",
                    "new output function",
                    "time saved",
                    "value recovered or replacement cost avoided",
                    "operator corrections",
                    "training export",
                ],
            },
            "honesty": [
                "image or text can propose reuse, but power and pin certainty comes from measurements",
                "prefer low-voltage modules, connectors, motors, sensors, UI parts, and enclosures",
                "do not reuse unknown battery packs, mains sections, or high-voltage modules without a separate safety procedure",
            ],
            "session_payload": self._session_payload(
                payload,
                blocks,
                candidates,
                splice_plan,
                evidence_plan,
                hazards,
                verdict,
                confidence,
                functional_reports=functional_reports,
                functional_reuse_plan=functional_reuse_plan,
                circuit_reasoning=circuit_reasoning,
            ),
        }

    def _functional_salvage_reports(self, payload: Dict[str, Any], analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        roots = [
            analysis,
            payload.get("circuit") if isinstance(payload.get("circuit"), dict) else {},
            payload.get("functional_salvage") if isinstance(payload.get("functional_salvage"), dict) else {},
        ]
        reports: List[Dict[str, Any]] = []
        seen = set()

        def add_report(report: Any) -> None:
            if not isinstance(report, dict) or report.get("mode") != "functional_salvage_assessment":
                return
            key = (report.get("schema_version"), report.get("board_id"), len(report.get("reusable_blocks") or []))
            if key in seen:
                return
            seen.add(key)
            reports.append(report)

        for root in roots:
            if not isinstance(root, dict):
                continue
            add_report(root)
            fs = root.get("functional_salvage")
            add_report(fs)
            if isinstance(fs, dict) and fs.get("mode") == "functional_salvage_portfolio" and not root.get("boards"):
                blocks = [row for row in fs.get("top_reusable_blocks") or [] if isinstance(row, dict)]
                if blocks:
                    add_report(
                        {
                            "mode": "functional_salvage_assessment",
                            "schema_version": fs.get("schema_version"),
                            "board_id": "circuit_portfolio",
                            "verdict": fs.get("verdict"),
                            "reusable_blocks": blocks,
                            "evidence_gates": [],
                        }
                    )
            for board in root.get("boards") or []:
                if isinstance(board, dict):
                    add_report(board.get("functional_salvage"))
        return reports

    def _blocks_from_functional_salvage(self, reports: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        blocks: List[Dict[str, Any]] = []
        for report in reports:
            board_id = str(report.get("board_id") or "board")
            for row in report.get("reusable_blocks") or []:
                if not isinstance(row, dict):
                    continue
                caps = [str(cap).lower() for cap in row.get("capabilities") or []]
                if not caps:
                    continue
                source_refs = row.get("source_refs") or []
                connector_refs = row.get("connector_refs") or []
                block = self._block(
                    str(row.get("block_id") or row.get("function_type") or row.get("name") or "functional_block"),
                    str(row.get("name") or row.get("function_type") or "reusable function"),
                    caps,
                    "circuit_functional_salvage",
                    confidence=row.get("confidence", 0.68),
                )
                block.update(
                    {
                        "board_id": board_id,
                        "function_type": row.get("function_type"),
                        "circuit_block_id": row.get("block_id"),
                        "source_refs": source_refs,
                        "connector_refs": connector_refs,
                        "nets": row.get("nets") or [],
                        "extractability": row.get("extractability") or {},
                        "status": row.get("status"),
                        "reuse_value_score": row.get("reuse_value_score"),
                        "evidence_gates": row.get("evidence_gates") or [],
                    }
                )
                prompts = [
                    str(gate.get("prompt"))
                    for gate in row.get("evidence_gates") or []
                    if isinstance(gate, dict) and gate.get("prompt")
                ]
                block["required_tests"] = self._dedupe([*(block.get("required_tests") or []), *prompts])[:10]
                if row.get("suggested_uses"):
                    block["suggested_uses"] = self._dedupe(row.get("suggested_uses") or [])[:8]
                if connector_refs:
                    block["extraction_action"] = f"reuse through connector(s): {', '.join(str(ref) for ref in connector_refs[:4])}"
                elif isinstance(row.get("extractability"), dict) and row["extractability"].get("action"):
                    block["extraction_action"] = row["extractability"]["action"]
                blocks.append(block)
        return blocks

    def _blocks_from_analysis(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        blocks: List[Dict[str, Any]] = []
        salvage = analysis.get("salvage_opportunities") if isinstance(analysis.get("salvage_opportunities"), dict) else {}
        asset_summary = salvage.get("asset_summary") if isinstance(salvage.get("asset_summary"), dict) else {}
        for cap, count in (asset_summary.get("capabilities") or {}).items():
            blocks.append(self._block(str(cap), str(cap).replace("_", " "), [str(cap)], "analysis", count=count))
        for part, count in (asset_summary.get("parts") or {}).items():
            blocks.append(self._block(str(part), str(part).upper(), self._capabilities_for_token(str(part)), "part_marking", count=count))

        board = analysis.get("board_understanding") or analysis.get("fused_board_understanding") or {}
        if isinstance(board, dict):
            role = ((board.get("board_identity") or {}).get("primary_type") or "")
            if role:
                caps = self._capabilities_for_role(role)
                blocks.append(self._block(role, role.replace("_", " "), caps, "board_role", confidence=(board.get("board_identity") or {}).get("confidence", board.get("confidence", 0.45))))
            for block in board.get("functional_blocks", []) or []:
                if isinstance(block, dict):
                    block_type = str(block.get("block_type") or "functional_block")
                    blocks.append(self._block(block_type, block_type.replace("_", " "), self._capabilities_for_role(block_type), "functional_block", confidence=block.get("confidence", 0.55)))

        connection = analysis.get("machine_connection_map") if isinstance(analysis.get("machine_connection_map"), dict) else {}
        connector_count = int(connection.get("connector_count", 0) or asset_summary.get("connector_count", 0) or 0)
        if connector_count:
            blocks.append(self._block("connector", f"{connector_count} reusable connector(s)", ["connector"], "connector_map", count=connector_count))
        for interface in connection.get("interfaces", []) or []:
            if isinstance(interface, dict):
                interface_type = str(interface.get("type") or "")
                if interface_type:
                    blocks.append(self._block(interface_type, interface_type.replace("_", " "), self._capabilities_for_role(interface_type), "interface", confidence=interface.get("confidence", 0.55)))

        marking = analysis.get("marking_analysis") if isinstance(analysis.get("marking_analysis"), dict) else {}
        for component in marking.get("components", []) or []:
            if not isinstance(component, dict):
                continue
            for candidate in component.get("candidates", []) or []:
                if isinstance(candidate, dict) and candidate.get("part_number"):
                    part = str(candidate.get("part_number"))
                    blocks.append(self._block(part.lower(), part.upper(), self._capabilities_for_token(part), "marking_candidate", confidence=candidate.get("confidence", 0.55)))
        return blocks

    def _blocks_from_inventory(self, value: Any) -> List[Dict[str, Any]]:
        rows: List[Any]
        if value is None:
            return []
        if isinstance(value, str):
            rows = [item.strip() for item in value.replace(";", "\n").replace(",", "\n").splitlines() if item.strip()]
        elif isinstance(value, list):
            rows = value
        elif isinstance(value, dict):
            rows = [value]
        else:
            rows = [value]

        blocks = []
        for index, row in enumerate(rows):
            if isinstance(row, dict):
                name = str(row.get("name") or row.get("label") or row.get("title") or row.get("part") or f"module {index + 1}")
                caps = [str(cap).lower() for cap in row.get("capabilities", []) or []] or self._capabilities_for_token(name)
                blocks.append(self._block(name.lower(), name, caps, "operator_inventory", count=row.get("quantity", row.get("qty", 1)), confidence=row.get("confidence", 0.6)))
            else:
                name = str(row)
                blocks.append(self._block(name.lower(), name, self._capabilities_for_token(name), "operator_inventory"))
        return blocks

    def _blocks_from_text(self, text: str) -> List[Dict[str, Any]]:
        tokens = {
            "usb": ("usb power/cable", ["power", "connector"]),
            "5v": ("5V low-voltage supply", ["power"]),
            "12v": ("12V low-voltage supply", ["power"]),
            "motor": ("small motor/load", ["motor_or_load", "fan_or_pump"]),
            "vibration": ("small vibration motor", ["motor_or_load", "fan_or_pump"]),
            "fan": ("fan blade and motor", ["motor_or_load", "fan_or_pump", "enclosure_candidate"]),
            "pump": ("small pump/load", ["motor_or_load", "fan_or_pump"]),
            "relay": ("relay/load switch", ["actuator_driver"]),
            "mosfet": ("MOSFET driver", ["actuator_driver"]),
            "transistor": ("transistor driver", ["actuator_driver"]),
            "switch": ("switch/button", ["switch_or_button"]),
            "button": ("switch/button", ["switch_or_button"]),
            "keyboard": ("keyboard/input matrix", ["switch_or_button", "connector"]),
            "mouse": ("mouse input board", ["switch_or_button", "sensor_or_adc", "connector"]),
            "gamepad": ("gamepad/controller input board", ["switch_or_button", "connector"]),
            "controller": ("controller input board", ["switch_or_button", "connector"]),
            "led": ("LED/light", ["led_or_light", "display_or_ui"]),
            "light bar": ("inspection light bar", ["led_or_light", "display_or_ui"]),
            "display": ("display/UI", ["display_or_ui"]),
            "optical": ("optical sensor", ["sensor_or_adc"]),
            "sensor": ("sensor module", ["sensor_or_adc"]),
            "camera": ("camera module", ["camera_or_vision", "sensor_or_adc"]),
            "speaker": ("speaker/audio driver", ["speaker_or_audio"]),
            "amplifier": ("audio amplifier board", ["speaker_or_audio", "actuator_driver"]),
            "audio": ("audio board", ["speaker_or_audio"]),
            "wifi": ("WiFi/radio module", ["wireless", "network_interface"]),
            "router": ("router/network board", ["wireless", "network_interface"]),
            "ethernet": ("Ethernet connector/interface", ["network_interface", "connector"]),
            "antenna": ("antenna/radio part", ["wireless"]),
            "remote": ("remote/button input", ["switch_or_button", "controller"]),
            "stepper": ("stepper motor", ["motor_or_load", "mechanical_motion"]),
            "servo": ("servo/motor actuator", ["motor_or_load", "mechanical_motion"]),
            "gear": ("gears/mechanical drive", ["mechanical_motion", "wheel_or_drive"]),
            "gearbox": ("gearbox/mechanical drive", ["mechanical_motion", "wheel_or_drive"]),
            "wheel": ("wheel/drive part", ["wheel_or_drive", "mechanical_motion"]),
            "belt": ("belt/rail mechanism", ["mechanical_motion"]),
            "rail": ("linear rail/mechanism", ["mechanical_motion"]),
            "esp32": ("ESP32 controller", ["controller", "wireless"]),
            "esp8266": ("ESP8266 controller", ["controller", "wireless"]),
            "arduino": ("Arduino-compatible controller", ["controller"]),
            "battery": ("battery or pack", ["power", "battery"]),
            "connector": ("connector/harness", ["connector"]),
            "wire": ("wire harness", ["connector"]),
            "harness": ("wire harness", ["connector"]),
            "enclosure": ("enclosure/mechanical frame", ["enclosure_candidate"]),
            "case": ("enclosure/mechanical frame", ["enclosure_candidate"]),
        }
        blocks = []
        lower = text.lower()
        for needle, (name, caps) in tokens.items():
            if needle in lower:
                blocks.append(self._block(needle, name, caps, "text_signal", confidence=0.48))
        return blocks

    def _text_blocks_for_case(self, payload: Dict[str, Any], inventory_blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if inventory_blocks and any(
            cap != "unknown_reusable_part"
            for block in inventory_blocks
            for cap in block.get("capabilities", [])
        ):
            return []
        return self._blocks_from_text(self._case_text(payload))

    def _build_candidates(
        self,
        capability_counts: Counter,
        blocks: List[Dict[str, Any]],
        hazards: List[Dict[str, Any]],
        case_text: str,
    ) -> List[Dict[str, Any]]:
        caps = set(capability_counts)
        candidates = []
        hard_hazard = any(item.get("severity") == "hard_stop" for item in hazards)
        for build in self.BUILD_CATALOG:
            groups = [set(group) for group in build["requires_any"]]
            matched_groups = [sorted(group & caps) for group in groups]
            present = [match for match in matched_groups if match]
            missing = [sorted(group) for group, match in zip(groups, matched_groups) if not match]
            if not present:
                continue
            nice = sorted(set(build["nice_to_have"]) & caps)
            match_score = len(present) / max(len(groups), 1)
            score = 0.35 + 0.42 * match_score + 0.04 * len(nice)
            score += self._goal_bias(build, case_text)
            if hard_hazard:
                score *= 0.45
            candidates.append(
                {
                    "id": build["id"],
                    "name": build["name"],
                    "score": round(min(score, 0.96), 3),
                    "difficulty": build["difficulty"],
                    "estimated_output_value_usd": build["value_usd"],
                    "output_function": build["output_function"],
                    "matched_capabilities": sorted({cap for match in present for cap in match}),
                    "missing_capability_groups": missing,
                    "nice_to_have_matched": nice,
                    "reuse_blocks": [block["block_id"] for block in blocks if set(block.get("capabilities", [])) & caps][:8],
                    "first_build_step": self._first_build_step(build["id"], bool(missing)),
                }
            )
        return sorted(candidates, key=lambda item: item["score"], reverse=True)[:8]

    def _goal_bias(self, build: Dict[str, Any], case_text: str) -> float:
        text = case_text.lower()
        haystack = " ".join([build["id"], build["name"], build["output_function"]]).lower()
        bias = 0.0
        for token in ["fan", "fume", "extractor", "cooling", "air", "motor", "vibration", "toothbrush", "pump", "relay", "sensor", "logger", "uart", "power", "light", "led", "strip", "controller", "robot", "drive", "wheel", "speaker", "audio", "wifi", "network", "camera", "ir", "inspection", "fixture", "scan", "scanner", "plotter", "printer", "stepper", "motion", "input", "button", "keyboard", "mouse", "gamepad"]:
            if token in text and token in haystack:
                bias += 0.055
        return min(bias, 0.18)

    def _splice_plan(
        self,
        payload: Dict[str, Any],
        analysis: Dict[str, Any],
        blocks: List[Dict[str, Any]],
        candidates: List[Dict[str, Any]],
        hazards: List[Dict[str, Any]],
        *,
        functional_reports: List[Dict[str, Any]] | None = None,
    ) -> Dict[str, Any]:
        connection = analysis.get("machine_connection_map") if isinstance(analysis.get("machine_connection_map"), dict) else {}
        raw_splice = connection.get("splice_plan") if isinstance(connection.get("splice_plan"), dict) else {}
        topology_authority = raw_splice.get("topology_authority") if isinstance(raw_splice.get("topology_authority"), dict) else {}
        raw_entry_points = raw_splice.get("safest_entry_points") or []
        inferred_entry_points = [
            block["block_id"] for block in blocks if "connector" in block.get("capabilities", [])
        ][:6]
        functional_entry_points = self._functional_entry_points(functional_reports or [])
        entry_points = self._dedupe(
            [*raw_entry_points, *functional_entry_points, *inferred_entry_points]
            if raw_entry_points
            else [*functional_entry_points, *inferred_entry_points]
        )[:10]
        target = (candidates[0] if candidates else {}).get("id", "generic_reuse")
        measurements = self._dedupe(
            [
                *self._required_measurements(blocks, connection),
                *self._functional_gate_prompts(functional_reports or []),
            ]
        )[:16]
        return {
            "target_build_id": target,
            "safest_entry_points": entry_points,
            "required_measurements": measurements,
            "adapter_circuits": self._adapter_circuits(blocks, target),
            "wiring_steps": self._wiring_steps(blocks, target, hazards),
            "mechanical_steps": self._mechanical_steps(blocks, target),
            "topology_authority": topology_authority,
            "pin_level_splice_contracts": raw_splice.get("pin_level_splice_contracts") if isinstance(raw_splice.get("pin_level_splice_contracts"), list) else [],
            "do_not_connect_until": [
                "input polarity is known",
                "rail voltage is measured under current limit",
                "ground reference is confirmed",
                "load resistance/current is checked",
                "battery or mains hazards are cleared",
            ],
        }

    def _functional_entry_points(self, reports: List[Dict[str, Any]]) -> List[str]:
        entries = []
        for report in reports:
            board_id = str(report.get("board_id") or "board")
            for block in report.get("reusable_blocks") or []:
                if not isinstance(block, dict):
                    continue
                for ref in block.get("connector_refs") or []:
                    entries.append(f"{board_id}:{ref}")
        return self._dedupe(entries)[:10]

    def _functional_gate_prompts(self, reports: List[Dict[str, Any]]) -> List[str]:
        prompts = []
        for report in reports:
            for gate in report.get("evidence_gates") or []:
                if isinstance(gate, dict) and gate.get("prompt"):
                    prompts.append(str(gate["prompt"]))
            for block in report.get("reusable_blocks") or []:
                if not isinstance(block, dict):
                    continue
                prompts.extend(str(item) for item in block.get("missing_evidence") or [])
        return self._dedupe(prompts)[:16]

    def _functional_reuse_plan(
        self,
        reports: List[Dict[str, Any]],
        blocks: List[Dict[str, Any]],
        splice_plan: Dict[str, Any],
        verdict: str,
    ) -> Dict[str, Any]:
        circuit_blocks = [block for block in blocks if block.get("source") == "circuit_functional_salvage"]
        ready_blocks = [block for block in circuit_blocks if block.get("status") == "reuse_ready"]
        blocked_blocks = [block for block in circuit_blocks if str(block.get("status") or "").startswith("blocked")]
        statuses = Counter(str(block.get("status") or "unknown") for block in circuit_blocks)
        extractability = Counter(
            str((block.get("extractability") or {}).get("class") or "unknown")
            for block in circuit_blocks
        )
        gates = [
            gate
            for report in reports
            for gate in report.get("evidence_gates") or []
            if isinstance(gate, dict)
        ]
        return {
            "mode": "functional_reuse_plan",
            "schema_version": "salvage_functional_reuse_plan.v1",
            "verdict": verdict,
            "circuit_backed": bool(circuit_blocks),
            "report_count": len(reports),
            "reusable_block_count": len(circuit_blocks),
            "ready_block_count": len(ready_blocks),
            "blocked_block_count": len(blocked_blocks),
            "splice_readiness": "ready_for_first_splice"
            if ready_blocks
            else "blocked_until_evidence"
            if circuit_blocks
            else "inventory_only",
            "status_summary": dict(sorted(statuses.items())),
            "extractability_summary": dict(sorted(extractability.items())),
            "open_evidence_gate_count": len([gate for gate in gates if str(gate.get("status", "open")) != "closed"]),
            "safest_entry_points": splice_plan.get("safest_entry_points") or [],
            "recommended_first_splice": self._recommended_first_splice(circuit_blocks),
            "ready_blocks": [self._reuse_plan_block_summary(block) for block in ready_blocks[:8]],
            "top_blocks": [
                self._reuse_plan_block_summary(block)
                for block in sorted(circuit_blocks, key=lambda row: float(row.get("reuse_value_score") or row.get("confidence") or 0.0), reverse=True)[:8]
            ],
        }

    def _reuse_plan_block_summary(self, block: Dict[str, Any]) -> Dict[str, Any]:
        board_id = str(block.get("board_id") or "board")
        connector_refs = [str(ref) for ref in block.get("connector_refs") or []]
        return {
            "block_id": block.get("block_id"),
            "circuit_block_id": block.get("circuit_block_id"),
            "name": block.get("name"),
            "board_id": board_id,
            "capabilities": block.get("capabilities") or [],
            "status": block.get("status"),
            "extractability": block.get("extractability") or {},
            "entry_points": [f"{board_id}:{ref}" for ref in connector_refs],
            "missing_evidence": self._dedupe(
                str(gate.get("prompt"))
                for gate in block.get("evidence_gates") or []
                if isinstance(gate, dict) and str(gate.get("status", "open")) != "closed" and gate.get("prompt")
            )[:8],
        }

    def _recommended_first_splice(self, circuit_blocks: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not circuit_blocks:
            return {
                "status": "inventory_only",
                "reason": "No circuit-backed reusable function blocks were supplied.",
            }

        def rank(block: Dict[str, Any]) -> tuple:
            status_rank = 0 if block.get("status") == "reuse_ready" else 1
            extractability = (block.get("extractability") or {}).get("class")
            extraction_rank = 0 if extractability == "connector_reuse" else 1 if extractability == "whole_board_reuse" else 2
            missing = len(
                [
                    gate
                    for gate in block.get("evidence_gates") or []
                    if isinstance(gate, dict) and str(gate.get("status", "open")) != "closed"
                ]
            )
            return (
                status_rank,
                extraction_rank,
                missing,
                -float(block.get("reuse_value_score") or block.get("confidence") or 0.0),
                str(block.get("block_id") or ""),
            )

        selected = sorted(circuit_blocks, key=rank)[0]
        summary = self._reuse_plan_block_summary(selected)
        summary["status"] = selected.get("status") or "unknown"
        summary["next_action"] = (
            "Build the labeled splice through this entry point and run first-power under current limit."
            if selected.get("status") == "reuse_ready"
            else "Close the listed evidence gates before using this function in a splice."
        )
        return summary

    def _evidence_plan(
        self,
        blocks: List[Dict[str, Any]],
        splice_plan: Dict[str, Any],
        hazards: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        capture_prompts = [
            "whole device before disassembly",
            "PCB top and bottom",
            "connector/wire-color closeups",
            "part markings on drivers, regulators, controllers, and sensors",
            "new build wiring before first power-up",
        ]
        if any("motor_or_load" in block.get("capabilities", []) for block in blocks):
            capture_prompts.append("motor/load label, wire colors, and shaft/mechanical mount")
        if any(hazard.get("severity") == "hard_stop" for hazard in hazards):
            capture_prompts.insert(0, "safety label, battery pack, mains input, or high-voltage section")
        return {
            "capture_prompts": capture_prompts[:8],
            "measurement_prompts": splice_plan.get("required_measurements", [])[:10],
            "review_prompts": [
                "operator confirms reused block function",
                "operator confirms voltage/current rating before power",
                "operator records final build outcome and value",
            ],
            "training_labels": [
                "reusable block type",
                "pin/connector role",
                "adapter circuit used",
                "successful output function",
                "unsafe or not-worth-it stop reason",
            ],
        }

    def _required_measurements(self, blocks: List[Dict[str, Any]], connection: Dict[str, Any]) -> List[str]:
        measurements = list((connection.get("splice_plan") or {}).get("required_measurements") or [])
        caps = {cap for block in blocks for cap in block.get("capabilities", [])}
        measurements.extend(["unpowered resistance between power and ground", "continuity from connector ground to exposed ground"])
        if "power" in caps or "battery" in caps:
            measurements.extend(["input voltage and polarity", "current draw under current-limited supply"])
        if "motor_or_load" in caps or "fan_or_pump" in caps:
            measurements.extend(["motor/load resistance", "startup current estimate", "driver output voltage with dummy load"])
        if "actuator_driver" in caps:
            measurements.extend(["MOSFET/transistor short check", "flyback/protection diode continuity", "load current limit"])
        if "controller" in caps or "usb_serial" in caps:
            measurements.extend(["logic high voltage", "shared ground continuity", "serial/I2C/SPI idle state if reused"])
        return self._dedupe(measurements)[:12]

    def _adapter_circuits(self, blocks: List[Dict[str, Any]], target: str) -> List[Dict[str, Any]]:
        caps = {cap for block in blocks for cap in block.get("capabilities", [])}
        adapters = []
        if "motor_or_load" in caps or "fan_or_pump" in caps:
            adapters.append(
                {
                    "name": "fused low-side MOSFET switch",
                    "use_when": "controlling a DC motor, fan, pump, relay, or LED strip from a switch or controller",
                    "must_include": ["fuse or current limit", "flyback diode for inductive loads", "common ground", "gate/base resistor if driven by controller"],
                }
            )
        if "power" in caps:
            adapters.append(
                {
                    "name": "buck/boost regulator or protected power breakout",
                    "use_when": "source voltage does not exactly match the salvaged load/module rating",
                    "must_include": ["polarity marking", "current rating margin", "input fuse", "strain relief"],
                }
            )
        if "controller" in caps and ("actuator_driver" in caps or "motor_or_load" in caps):
            adapters.append(
                {
                    "name": "logic-to-load interface",
                    "use_when": "a microcontroller pin needs to control a higher-current salvaged load",
                    "must_include": ["level compatibility", "driver transistor/MOSFET", "separate load supply if needed", "shared ground only when safe"],
                }
            )
        if "speaker_or_audio" in caps:
            adapters.append(
                {
                    "name": "audio amp power and speaker harness",
                    "use_when": "reusing speakers, amplifier boards, buzzers, or alert modules",
                    "must_include": ["speaker impedance check", "amp supply voltage check", "input isolation if source is unknown"],
                }
            )
        if "camera_or_vision" in caps:
            adapters.append(
                {
                    "name": "camera/IR protected power harness",
                    "use_when": "reusing camera boards, IR LEDs, or inspection-light assemblies",
                    "must_include": ["voltage/current check", "thermal check for LEDs", "do not assume video/data protocol"],
                }
            )
        if target == "inspection_motion_fixture":
            adapters.append(
                {
                    "name": "motion-and-light fixture harness",
                    "use_when": "a scanner, printer, or camera assembly provides a rail, light bar, limit switch, or optical sensor",
                    "must_include": ["current-limited LED driver", "stepper/DC motor driver sized for load", "limit switch input", "hard stop or travel limit"],
                }
            )
        if "sensor_or_adc" in caps:
            adapters.append(
                {
                    "name": "sensor breakout harness",
                    "use_when": "reusing a sensor board with unknown pin order",
                    "must_include": ["pin labels", "voltage-domain check", "pull-up verification for I2C/open-drain lines"],
                }
            )
        return adapters or [
            {
                "name": "labeled connector breakout",
                "use_when": "the useful function is not known yet",
                "must_include": ["GND continuity", "voltage-domain notes", "do-not-power label until verified"],
            }
        ]

    def _wiring_steps(self, blocks: List[Dict[str, Any]], target: str, hazards: List[Dict[str, Any]]) -> List[str]:
        if any(item.get("severity") == "hard_stop" for item in hazards):
            return [
                "isolate the hazardous section and do not power it",
                "recover only clearly low-voltage, disconnected modules after safety review",
                "document why the hazardous section was excluded",
            ]
        steps = [
            "identify reusable block pins or wires from labels, continuity, and close-up photos",
            "power the reused block from a current-limited supply at the lowest plausible rated voltage",
            "verify the block output function before connecting it to any other module",
        ]
        caps = {cap for block in blocks for cap in block.get("capabilities", [])}
        if "motor_or_load" in caps or "fan_or_pump" in caps:
            steps.extend(
                [
                    "wire the motor/load through a fuse or current limit first",
                    "add a MOSFET/transistor driver if a controller or switch cannot handle load current",
                    "add flyback protection for inductive motors, pumps, relays, or coils",
                ]
            )
        if "controller" in caps:
            steps.append("connect controller logic only after voltage domains and common-ground requirements are verified")
        if "mechanical_motion" in caps:
            steps.append("secure belts, rails, gears, and limit switches before powered motion tests")
        if target == "inspection_motion_fixture":
            steps.extend(
                [
                    "test the light bar separately with current limiting before coupling it to motion",
                    "home the rail at low speed against a verified limit switch before full-travel tests",
                    "mount the camera, sensor, or item holder so travel cannot pull on the harness",
                ]
            )
        if "switch_or_button" in caps:
            steps.append("verify switch/button continuity and debounce behavior before using it as an input panel")
        if "speaker_or_audio" in caps:
            steps.append("test speakers or amplifier boards at low volume/current before mounting")
        if "camera_or_vision" in caps:
            steps.append("test camera or IR modules as standalone low-voltage loads before data integration")
        steps.extend(
            [
                "mount the new build so wires have strain relief and cannot short",
                "record a first-power test, thermal check, and final output function",
            ]
        )
        return steps[:10]

    def _mechanical_steps(self, blocks: List[Dict[str, Any]], target: str) -> List[str]:
        steps = [
            "keep strain relief on harvested wires and connectors",
            "mount moving parts so wires cannot touch blades, gears, belts, rails, or hot surfaces",
            "label every reused connector with voltage, polarity, and function after verification",
        ]
        caps = {cap for block in blocks for cap in block.get("capabilities", [])}
        if target == "inspection_motion_fixture":
            steps.extend(
                [
                    "keep the scanner/printer rail straight and preserve the original belt, pulley, or carriage alignment",
                    "add a physical end stop and mark the safe travel distance before powered motion",
                    "mount light/camera/sensor modules so focus distance and illumination angle are repeatable",
                ]
            )
        elif "mechanical_motion" in caps:
            steps.append("mark original gear, belt, and limit-switch positions before removing the mechanism")
        return steps[:7]

    def _integration_contract(
        self,
        blocks: List[Dict[str, Any]],
        top: Dict[str, Any],
        splice_plan: Dict[str, Any],
        hazards: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        caps = {cap for block in blocks for cap in block.get("capabilities", [])}
        interfaces = []
        if "power" in caps or "battery" in caps:
            interfaces.append({"name": "power input", "must_define": ["voltage", "polarity", "current limit", "fuse/protection"]})
        if "motor_or_load" in caps or "mechanical_motion" in caps:
            interfaces.append({"name": "motion/load output", "must_define": ["load resistance/current", "driver rating", "travel limits or mechanical clearance"]})
        if "led_or_light" in caps or "display_or_ui" in caps:
            interfaces.append({"name": "light/UI output", "must_define": ["supply voltage", "current limit", "thermal behavior"]})
        if "sensor_or_adc" in caps or "camera_or_vision" in caps:
            interfaces.append({"name": "signal/sensor interface", "must_define": ["pin order", "logic voltage", "bus/protocol or standalone mode"]})
        if "switch_or_button" in caps:
            interfaces.append({"name": "operator input", "must_define": ["continuity behavior", "debounce need", "pull-up/pull-down"]})
        if "connector" in caps:
            interfaces.append({"name": "connector harness", "must_define": ["pinout", "wire color role", "strain relief"]})

        return {
            "target_build_id": top.get("id"),
            "target_build": top.get("name"),
            "output_function": top.get("output_function"),
            "interfaces_to_define": interfaces,
            "unknowns_to_close": (splice_plan.get("required_measurements") or [])[:8],
            "hazard_state": "hold" if any(item.get("severity") == "hard_stop" for item in hazards) else "measure_before_power",
            "first_demo": self._first_demo(top.get("id")),
        }

    def _first_demo(self, build_id: str | None) -> str:
        if build_id == "inspection_motion_fixture":
            return "show one slow rail movement with the light/camera/sensor powered separately, then record a repeatable before/after inspection image"
        if build_id == "usb_fume_extractor":
            return "show airflow from a current-limited supply and record current draw after one minute"
        if build_id == "smart_relay_box":
            return "switch a dummy low-voltage load through the driver while recording input voltage and load current"
        if build_id == "safety_hold":
            return "record isolated hazardous sections and list which low-voltage parts are safe to recover later"
        return "demonstrate the reused block alone before connecting it to another module"

    def _hazards(self, text: str, blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        lower = text.lower()
        hazards = []
        for term in sorted(self.HARD_HAZARD_TERMS):
            if term in lower:
                hazards.append({"hazard": term, "severity": "hard_stop", "action": "exclude or isolate before reuse"})
        if any("battery" in block.get("capabilities", []) for block in blocks):
            hazards.append({"hazard": "battery_pack", "severity": "review", "action": "verify chemistry, voltage, protection, temperature, and swelling before reuse"})
        if any("power" in block.get("capabilities", []) for block in blocks):
            hazards.append({"hazard": "unknown_power_rating", "severity": "review", "action": "measure voltage/current under current limit before interconnect"})
        return hazards[:8]

    def _verdict(
        self,
        blocks: List[Dict[str, Any]],
        candidates: List[Dict[str, Any]],
        hazards: List[Dict[str, Any]],
        evidence_plan: Dict[str, Any],
    ) -> str:
        if any(item.get("severity") == "hard_stop" for item in hazards):
            return "unsafe_hold"
        if not blocks:
            return "collect_more_evidence"
        if any(item.get("severity") == "review" for item in hazards) and candidates:
            return "ready_after_measurements"
        if candidates and len(evidence_plan.get("measurement_prompts") or []) <= 4:
            return "reuse_ready"
        if candidates:
            return "ready_after_measurements"
        return "inventory_first"

    def _confidence(
        self,
        blocks: List[Dict[str, Any]],
        candidates: List[Dict[str, Any]],
        hazards: List[Dict[str, Any]],
        analysis: Dict[str, Any],
    ) -> float:
        score = 0.18 + 0.05 * min(len(blocks), 8) + 0.10 * min(len(candidates), 3)
        if analysis:
            score += 0.12
        if any(item.get("severity") == "hard_stop" for item in hazards):
            score -= 0.22
        return round(max(0.0, min(score, 0.88)), 3)

    def _stop_conditions(self, hazards: List[Dict[str, Any]], blocks: List[Dict[str, Any]]) -> List[str]:
        stops = [f"{item['hazard']}: {item['action']}" for item in hazards if item.get("severity") == "hard_stop"]
        stops.extend(
            [
                "input voltage or polarity cannot be identified",
                "power-to-ground resistance suggests a short",
                "load current exceeds the wire, connector, switch, driver, or supply rating",
                "module overheats, smells, smokes, or pulls unexpected current",
                "battery chemistry/protection is unknown or the pack is damaged",
            ]
        )
        return self._dedupe(stops)[:8]

    def _session_payload(
        self,
        payload: Dict[str, Any],
        blocks: List[Dict[str, Any]],
        candidates: List[Dict[str, Any]],
        splice_plan: Dict[str, Any],
        evidence_plan: Dict[str, Any],
        hazards: List[Dict[str, Any]],
        verdict: str,
        confidence: float,
        *,
        functional_reports: List[Dict[str, Any]] | None = None,
        functional_reuse_plan: Dict[str, Any] | None = None,
        circuit_reasoning: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        if verdict == "unsafe_hold":
            top = {
                "id": "safety_hold",
                "name": "Safety hold before salvage",
                "output_function": "recover only clearly isolated low-voltage parts after a separate safety review",
                "score": confidence,
            }
        else:
            top = candidates[0] if candidates else {}
        title = str(payload.get("title") or top.get("name") or "Salvage reuse case")
        measurements = evidence_plan.get("measurement_prompts") or splice_plan.get("required_measurements") or []
        captures = evidence_plan.get("capture_prompts") or []
        reviews = evidence_plan.get("review_prompts") or []
        missing_evidence = self._dedupe([*captures[:5], *measurements[:8], *reviews[:3]])
        capability_summary = dict(Counter(cap for block in blocks for cap in block.get("capabilities", [])))
        stop_conditions = self._stop_conditions(hazards, blocks)
        integration_contract = self._integration_contract(blocks, top, splice_plan, hazards)
        functional_reuse_plan = functional_reuse_plan or self._functional_reuse_plan(functional_reports or [], blocks, splice_plan, verdict)
        circuit_reasoning = circuit_reasoning or CircuitAIReasoner(enable_llm=False).assess(
            {
                "goal": payload.get("goal"),
                "salvage_plan": {
                    "verdict": verdict,
                    "splice_plan": splice_plan,
                    "evidence_plan": evidence_plan,
                    "functional_reuse_plan": functional_reuse_plan,
                },
                "functional_reuse_plan": functional_reuse_plan,
            }
        )
        plan_record = {
            "mode": "salvage_splice_reuse_plan",
            "verdict": verdict,
            "confidence": confidence,
            "target": {
                "requested_goal": str(payload.get("goal") or "reuse useful functions from junk electronics"),
                "recommended_build_id": top.get("id"),
                "recommended_build": top.get("name"),
                "output_function": top.get("output_function"),
            },
            "reusable_blocks": blocks[:12],
            "capability_summary": capability_summary,
            "build_candidates": candidates,
            "splice_plan": splice_plan,
            "functional_reuse_plan": functional_reuse_plan,
            "circuit_reasoning": circuit_reasoning,
            "integration_contract": integration_contract,
            "evidence_plan": evidence_plan,
            "stop_conditions": stop_conditions,
            "hazards": hazards,
        }
        analysis = {
            "mode": "salvage_splice_reuse_plan",
            "certainty_ledger": {
                "overall": {
                    "score": confidence,
                    "level": "possible" if verdict in {"ready_after_measurements", "reuse_ready"} else "unknown",
                },
                "counts": {"possible": len(blocks), "total": len(blocks)},
                "missing_evidence": missing_evidence,
                "training_queue": {"should_capture": True, "reason": "salvage/reuse proof needs captures, measurements, and outcome"},
                "items": [
                    {
                        "item_id": f"reuse_block_{index + 1}",
                        "claim_type": "reusable_block",
                        "claim": f"{block.get('name')} can support {', '.join(block.get('capabilities', [])[:4])}",
                        "certainty": "possible",
                        "next_actions": (block.get("required_tests") or [])[:3],
                        "usable_for": ["salvage", "reuse", "splicing", "training"],
                    }
                    for index, block in enumerate(blocks[:8])
                ],
            },
            "salvage_splice_plan": plan_record,
            "machine_connection_map": {"splice_plan": {"required_measurements": measurements}},
            "salvage_opportunities": {
                "best_opportunity": {
                    "type": "salvage_to_build",
                    "id": top.get("id"),
                    "name": top.get("name"),
                    "score": top.get("score", confidence),
                },
                "asset_summary": {
                    "capabilities": capability_summary,
                    "parts": {},
                    "connector_count": len([block for block in blocks if "connector" in block.get("capabilities", [])]),
                    "defect_count": 0,
                    "evidence": [block.get("name") for block in blocks[:12]],
                },
            },
        }
        return {
            "title": title,
            "description": str(payload.get("goal") or payload.get("description") or title),
            "device_hint": str(payload.get("device_hint") or title),
            "symptoms": self._dedupe([str(payload.get("goal") or "reuse useful functions"), verdict.replace("_", " ")]),
            "route": "safety" if verdict == "unsafe_hold" else "salvage",
            "route_label": "safety hold" if verdict == "unsafe_hold" else "salvage to build",
            "analysis": analysis,
            "summary": {
                "summary_text": f"{title}: {verdict.replace('_', ' ')} toward {top.get('name') or 'reuse inventory'}",
            },
            "source": "salvage_splice_plan",
            "salvage_splice_plan": plan_record,
            "case_file": {
                "kind": "salvage_splice_reuse",
                "goal": payload.get("goal"),
                "verdict": verdict,
                "target_build_id": top.get("id"),
                "proof_fields": [
                    "blocks recovered",
                    "measurements recorded",
                    "new output function",
                    "time saved",
                    "value recovered",
                    "training export",
                ],
            },
        }

    def _case_text(self, payload: Dict[str, Any]) -> str:
        parts = [
            str(payload.get("title") or ""),
            str(payload.get("device_hint") or ""),
            str(payload.get("goal") or ""),
            str(payload.get("description") or payload.get("notes") or ""),
        ]
        for key in ["available_parts", "inventory", "modules", "symptoms"]:
            value = payload.get(key)
            if isinstance(value, str):
                parts.append(value)
            elif isinstance(value, list):
                parts.extend(str(item) for item in value)
        return " ".join(parts)

    def _block(
        self,
        block_id: str,
        name: str,
        capabilities: Iterable[str],
        source: str,
        *,
        count: Any = 1,
        confidence: Any = 0.5,
    ) -> Dict[str, Any]:
        caps = sorted(set(str(cap).lower() for cap in capabilities if str(cap).strip()))
        return {
            "block_id": self._safe_id(block_id or name),
            "name": name,
            "capabilities": caps,
            "source": source,
            "quantity": int(float(count or 1)),
            "confidence": round(float(confidence or 0.5), 3),
            "extraction_action": self._extraction_action(caps),
            "required_tests": self._tests_for_caps(caps),
            "suggested_uses": self._uses_for_caps(caps),
        }

    def _extraction_action(self, caps: List[str]) -> str:
        if "battery" in caps:
            return "inspect as a safety item; reuse only if chemistry, protection, voltage, and condition are known"
        if "motor_or_load" in caps or "fan_or_pump" in caps:
            return "recover with original wires if possible and test from current-limited supply"
        if "connector" in caps:
            return "keep harness/connector intact and map pin function before cutting"
        if "controller" in caps:
            return "recover as whole module when possible; do not depend on locked firmware"
        return "recover intact, label source, and test before reuse"

    def _tests_for_caps(self, caps: List[str]) -> List[str]:
        tests = ["visual inspection", "continuity/short check"]
        if "power" in caps or "battery" in caps:
            tests.extend(["voltage and polarity", "current draw under current limit"])
        if "motor_or_load" in caps or "fan_or_pump" in caps:
            tests.extend(["load resistance", "startup current", "mechanical spin or movement"])
        if "actuator_driver" in caps:
            tests.extend(["driver short test", "load output voltage", "flyback/protection check"])
        if "controller" in caps or "usb_serial" in caps:
            tests.extend(["logic voltage", "boot/serial response"])
        if "sensor_or_adc" in caps:
            tests.append("known-good reading or bus response")
        return self._dedupe(tests)[:8]

    def _uses_for_caps(self, caps: List[str]) -> List[str]:
        uses = []
        if "motor_or_load" in caps or "fan_or_pump" in caps:
            uses.extend(["cooling fan", "fume extractor", "small pump/air mover", "motion test rig"])
        if "actuator_driver" in caps:
            uses.extend(["load switch", "relay/MOSFET driver", "motor control stage"])
        if "power" in caps:
            uses.extend(["power breakout", "regulated supply stage", "charging/contact test fixture"])
        if "controller" in caps:
            uses.extend(["automation controller", "sensor logger", "smart switch brain"])
        if "sensor_or_adc" in caps:
            uses.extend(["sensor module", "data logger input", "alarm trigger"])
        if "display_or_ui" in caps or "led_or_light" in caps:
            uses.extend(["status indicator", "task light", "user interface"])
        if "connector" in caps:
            uses.extend(["harness adapter", "breakout cable", "test connector"])
        return self._dedupe(uses)[:7] or ["parts inventory", "evidence for future build"]

    def _capabilities_for_role(self, role: str) -> List[str]:
        text = role.lower()
        mapping = {
            "power": ["power"],
            "regulation": ["power"],
            "controller": ["controller"],
            "compute": ["controller"],
            "wireless": ["wireless", "controller"],
            "communications": ["wireless", "connector"],
            "connector": ["connector"],
            "io": ["connector"],
            "uart": ["usb_serial", "connector"],
            "serial": ["usb_serial", "connector"],
            "actuator": ["actuator_driver"],
            "motor": ["actuator_driver", "motor_or_load"],
            "load": ["actuator_driver", "motor_or_load"],
            "sensor": ["sensor_or_adc"],
            "display": ["display_or_ui"],
            "user_interface": ["display_or_ui", "switch_or_button"],
        }
        caps = []
        for token, token_caps in mapping.items():
            if token in text:
                caps.extend(token_caps)
        return sorted(set(caps)) or [text]

    def _capabilities_for_token(self, token: str) -> List[str]:
        text = token.lower()
        caps = []
        token_map = {
            ("esp32", "esp8266"): ["controller", "wireless"],
            ("arduino", "atmega", "stm32", "pic"): ["controller"],
            ("cp2102", "ch340", "ft232", "uart"): ["usb_serial", "connector"],
            ("lm2596", "ams1117", "buck", "boost", "regulator", "charging", "charger", "usb", "5v", "12v", "24v"): ["power"],
            ("relay", "mosfet", "uln2003", "transistor", "driver"): ["actuator_driver"],
            ("motor", "fan", "pump", "load", "stepper", "servo", "spindle"): ["motor_or_load", "fan_or_pump"],
            ("gear", "gearbox", "wheel", "belt", "rail", "linear", "stepper", "servo"): ["mechanical_motion", "wheel_or_drive"],
            ("sensor", "bme280", "bmp280", "dht", "ads1115"): ["sensor_or_adc"],
            ("camera", "image", "vision"): ["camera_or_vision", "sensor_or_adc"],
            ("display", "oled", "lcd", "led", "light", "screen"): ["display_or_ui", "led_or_light"],
            ("speaker", "audio", "amplifier", "amp", "buzzer"): ["speaker_or_audio"],
            ("wifi", "router", "ethernet", "antenna", "network"): ["wireless", "network_interface"],
            ("remote",): ["switch_or_button", "controller"],
            ("controller",): ["controller"],
            ("switch", "button", "trigger", "joystick", "keyboard", "mouse", "gamepad", "limit"): ["switch_or_button"],
            ("connector", "header", "wire", "harness", "cable", "jack", "sata"): ["connector"],
            ("case", "shell", "enclosure", "frame", "mount"): ["enclosure_candidate"],
            ("battery", "cell", "pack", "bms"): ["battery", "power"],
        }
        for needles, token_caps in token_map.items():
            if any(needle in text for needle in needles):
                caps.extend(token_caps)
        return sorted(set(caps)) or ["unknown_reusable_part"]

    def _first_build_step(self, build_id: str, missing: bool) -> str:
        if missing:
            return "validate matched modules, then source or substitute the missing capability group"
        if build_id == "inspection_motion_fixture":
            return "test rail motion, light output, and limit switch separately before mounting the inspection fixture"
        if build_id in {"usb_fume_extractor", "low_voltage_motor_test_jig"}:
            return "test motor/load current with a current-limited 5V or rated supply"
        if build_id == "smart_relay_box":
            return "test relay/MOSFET driver separately before connecting a real load"
        if build_id == "sensor_logger":
            return "identify sensor voltage and bus pins, then confirm a known-good reading"
        return "build a labeled breakout and run first-power checks"

    def _dedupe_blocks(self, blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        kept: List[Dict[str, Any]] = []
        seen = set()
        for block in blocks:
            key = (block.get("block_id"), tuple(block.get("capabilities", [])))
            if key in seen or not block.get("capabilities"):
                continue
            seen.add(key)
            kept.append(block)
        return kept[:24]

    def _safe_id(self, value: str) -> str:
        safe = "".join(ch.lower() if ch.isalnum() else "_" for ch in str(value)).strip("_")
        return safe[:60] or "block"

    @staticmethod
    def _dedupe(items: Sequence[str]) -> List[str]:
        kept = []
        seen = set()
        for item in items:
            text = str(item).strip()
            key = text.lower()
            if not text or key in seen:
                continue
            seen.add(key)
            kept.append(text)
        return kept
