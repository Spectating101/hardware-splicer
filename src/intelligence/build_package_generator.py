"""Generate actionable build/resale packages from salvage workflow reports."""

from __future__ import annotations

from typing import Any, Dict, List

from src.intelligence.build_instructions import BuildInstructionsGenerator


class BuildPackageGenerator:
    """Convert workflow decisions into a concrete work order."""

    def __init__(self):
        self.instructions = BuildInstructionsGenerator()

    def generate(self, workflow_report: Dict[str, Any]) -> Dict[str, Any]:
        decision = workflow_report.get("decision") or {}
        candidate_recipe = ((workflow_report.get("execution_plan") or {}).get("recipe_target") or {})
        best = ((workflow_report.get("opportunity_report") or {}).get("best_opportunity") or {})
        if decision.get("action") == "inventory_and_collect_more_evidence":
            candidate_recipe = {}
            best = {}
        recipe = candidate_recipe if self._recipe_matches_opportunity(candidate_recipe, best) else {}
        inventory = workflow_report.get("inventory") or {}
        target = recipe or best
        package_type = self._package_type(best, recipe)
        build_instructions = self._instructions(recipe, best)
        return {
            "mode": "salvage_build_package",
            "package_type": package_type,
            "target": target,
            "target_source": "recipe" if recipe else "opportunity" if best else "evidence",
            "candidate_recipe": candidate_recipe if candidate_recipe and not recipe else {},
            "work_order": self._work_order(workflow_report, target, build_instructions),
            "bom": self._bom(recipe, best),
            "validation": self._validation(workflow_report, best),
            "wiring_plan": self._wiring_plan(workflow_report, build_instructions),
            "firmware_plan": self._firmware_plan(recipe, best),
            "commercialization": self._commercialization(recipe, best, inventory),
            "source_inventory": inventory,
            "confidence": self._confidence(workflow_report, recipe, best),
        }

    def _recipe_matches_opportunity(self, recipe: Dict[str, Any], best: Dict[str, Any]) -> bool:
        if not recipe:
            return False
        if not best:
            return True
        if best.get("type") == "ecommerce_arbitrage":
            return True
        if best.get("type") != "build_from_salvage":
            return False

        recipe_text = self._domain_text(
            [
                recipe.get("name"),
                recipe.get("category"),
                recipe.get("description"),
                *(recipe.get("required_components") or []),
            ]
        )
        best_text = self._domain_text(
            [
                best.get("name"),
                best.get("category"),
                *(best.get("matched_assets") or []),
                *(best.get("nice_to_have_matched") or []),
            ]
        )
        if recipe.get("category") and recipe.get("category") == best.get("category"):
            return True
        return (
            ("sensor" in best_text and self._has_any(recipe_text, {"sensor", "bme", "bmp", "dht", "weather", "monitor"}))
            or (self._has_any(best_text, {"relay", "switch"}) and "relay" in recipe_text)
            or (self._has_any(best_text, {"motor", "servo", "robot"}) and self._has_any(recipe_text, {"motor", "servo", "robot"}))
            or ("power" in best_text and self._has_any(recipe_text, {"power", "supply", "regulator"}))
            or (self._has_any(best_text, {"uart", "debug", "usb"}) and self._has_any(recipe_text, {"uart", "debug", "usb"}))
        )

    def _domain_text(self, values: List[Any]) -> str:
        return " ".join(str(value or "").replace("_", " ").lower() for value in values)

    def _has_any(self, text: str, needles: set[str]) -> bool:
        return any(needle in text for needle in needles)

    def _package_type(self, best: Dict[str, Any], recipe: Dict[str, Any]) -> str:
        if recipe:
            return "known_recipe_build"
        if best.get("type") == "ecommerce_arbitrage":
            return "listing_arbitrage_work_order"
        if best.get("type") == "resell_or_stock":
            return "part_recovery_stocking"
        if best:
            return "salvage_project_build"
        return "evidence_collection"

    def _instructions(self, recipe: Dict[str, Any], best: Dict[str, Any]) -> Dict[str, Any]:
        if recipe.get("name"):
            return self.instructions.generate_instructions(
                recipe["name"],
                recipe.get("required_components", []),
            )
        if best.get("name"):
            return self.instructions.generate_instructions(
                best["name"],
                list(best.get("matched_assets", []) or []),
            )
        return {}

    def _work_order(
        self,
        workflow_report: Dict[str, Any],
        target: Dict[str, Any],
        build_instructions: Dict[str, Any],
    ) -> Dict[str, Any]:
        execution = workflow_report.get("execution_plan") or {}
        steps = list(execution.get("steps", []) or [])
        if build_instructions.get("steps"):
            steps.append(f"follow {len(build_instructions['steps'])} generated assembly step(s)")
        return {
            "status": execution.get("status", "collect_more_assets"),
            "target_name": target.get("name"),
            "steps": steps or ["scan more assets", "add OCR closeups", "record test results"],
            "validation_gates": execution.get("validation_gates", []),
            "operator_notes": [
                "treat salvaged parts as untrusted until tested",
                "record test results back into inventory after each gate",
                "separate resale-grade parts from build-only parts",
            ],
        }

    def _bom(self, recipe: Dict[str, Any], best: Dict[str, Any]) -> Dict[str, Any]:
        if recipe:
            return {
                "required": recipe.get("required_components", []),
                "owned": recipe.get("components_owned", []),
                "missing": recipe.get("components_needed", []),
                "missing_parts_cost_usd": recipe.get("missing_parts_cost", 0.0),
                "parts_cost_usd": recipe.get("parts_cost", 0.0),
            }
        return {
            "required": sorted(set((best.get("matched_assets") or []) + (best.get("missing_assets") or []))),
            "owned": best.get("matched_assets", []),
            "missing": best.get("missing_assets", []),
            "missing_parts_cost_usd": None,
            "parts_cost_usd": best.get("input_cost_usd"),
        }

    def _validation(self, workflow_report: Dict[str, Any], best: Dict[str, Any]) -> Dict[str, Any]:
        execution = workflow_report.get("execution_plan") or {}
        required = [
            "visual inspection",
            "continuity power-to-ground",
            "current-limited first power-up",
            "connector pin map",
        ]
        if "relay" in " ".join(best.get("matched_assets", [])).lower() or "actuator" in " ".join(best.get("matched_assets", [])).lower():
            required.extend(["load current measurement", "flyback/protection check"])
        return {
            "required_tests": required,
            "gates": execution.get("validation_gates", []),
            "pass_criteria": [
                "no short on main rail",
                "rails within expected voltage range",
                "thermal behavior stable for first 5 minutes",
                "all external pins labeled before integration",
            ],
        }

    def _wiring_plan(
        self,
        workflow_report: Dict[str, Any],
        build_instructions: Dict[str, Any],
    ) -> Dict[str, Any]:
        connector_maps = (((workflow_report.get("opportunity_report") or {}).get("asset_summary") or {}).get("connector_maps") or [])
        wiring_steps = []
        for step in build_instructions.get("steps", []) or []:
            if isinstance(step, dict) and step.get("wiring"):
                wiring_steps.extend(step.get("wiring") or [])
        return {
            "known_wiring_steps": wiring_steps[:30],
            "connector_maps": connector_maps,
            "notes": [
                "use workflow machine_connection_map when available for harvested modules",
                "map every salvaged connector with continuity before connecting recipe wiring",
            ],
        }

    def _firmware_plan(self, recipe: Dict[str, Any], best: Dict[str, Any]) -> Dict[str, Any]:
        name = f"{recipe.get('name') or best.get('name') or 'salvage_project'}".lower()
        features: List[str] = []
        if "wifi" in name or "iot" in name or "esp" in " ".join(recipe.get("required_components", [])).lower():
            features.append("wifi")
        if "relay" in name or "switch" in name:
            features.append("digital_output_control")
        if "sensor" in name or "monitor" in name or "weather" in name:
            features.append("sensor_read_loop")
        return {
            "target_platform": self._target_platform(recipe, best),
            "features": features,
            "starter_code": self._starter_code(self._target_platform(recipe, best), features),
            "starter_tasks": [
                "blink/status LED test",
                "serial boot log",
                "read each attached sensor or toggle each output individually",
                "add fault timeout before unattended use",
            ],
        }

    def _commercialization(
        self,
        recipe: Dict[str, Any],
        best: Dict[str, Any],
        inventory: Dict[str, Any],
    ) -> Dict[str, Any]:
        market_low = recipe.get("market_price_low") or best.get("estimated_output_value_usd")
        market_high = recipe.get("market_price_high") or best.get("estimated_output_value_usd")
        adjusted_margin = best.get("adjusted_margin_usd")
        return {
            "positioning": self._positioning(recipe, best),
            "estimated_market_price_low_usd": market_low,
            "estimated_market_price_high_usd": market_high,
            "adjusted_margin_usd": adjusted_margin,
            "inventory_value_used_usd": inventory.get("estimated_inventory_value_usd"),
            "listing_checklist": [
                "photograph tested module",
                "include voltage/current limits",
                "state salvaged/refurbished condition clearly",
                "include safety disclaimers for high-voltage or load-switching products",
            ],
        }

    def _target_platform(self, recipe: Dict[str, Any], best: Dict[str, Any]) -> str:
        text = " ".join(recipe.get("required_components", []) + best.get("matched_assets", [])).lower()
        if "esp32" in text:
            return "esp32"
        if "esp8266" in text:
            return "esp8266"
        if "arduino_nano" in text:
            return "arduino_nano"
        if "arduino_uno" in text or "atmega" in text:
            return "arduino_uno"
        return "unknown_controller"

    def _starter_code(self, platform: str, features: List[str]) -> str:
        serial_speed = 115200 if platform in {"esp32", "esp8266"} else 9600
        lines = [
            "/*",
            " * Circuit-AI salvage starter firmware",
            f" * Target platform: {platform}",
            f" * Features: {', '.join(features) if features else 'manual validation'}",
            " */",
            "",
            "const int STATUS_LED = 2;",
            "",
            "void setup() {",
            f"  Serial.begin({serial_speed});",
            "  pinMode(STATUS_LED, OUTPUT);",
            "  Serial.println(\"Circuit-AI salvage validation boot\");",
            "}",
            "",
            "void loop() {",
            "  digitalWrite(STATUS_LED, HIGH);",
            "  delay(250);",
            "  digitalWrite(STATUS_LED, LOW);",
            "  delay(750);",
        ]
        if "sensor_read_loop" in features:
            lines.extend(
                [
                    "  // TODO: read each salvaged sensor one at a time after pinout validation.",
                    "  Serial.println(\"sensor validation tick\");",
                ]
            )
        if "digital_output_control" in features:
            lines.extend(
                [
                    "  // TODO: toggle outputs only through a current-limited test load first.",
                    "  Serial.println(\"output validation tick\");",
                ]
            )
        lines.append("}")
        return "\n".join(lines)

    def _positioning(self, recipe: Dict[str, Any], best: Dict[str, Any]) -> str:
        category = recipe.get("category") or best.get("category")
        if category in {"home_automation", "iot", "consumer_gadget"}:
            return "assembled/refurbished smart gadget or DIY kit"
        if category in {"robotics"}:
            return "robotics module or educational kit"
        if best.get("type") == "resell_or_stock":
            return "tested recovered component inventory"
        return "upcycled electronics module"

    def _confidence(self, workflow_report: Dict[str, Any], recipe: Dict[str, Any], best: Dict[str, Any]) -> float:
        base = float(((workflow_report.get("opportunity_report") or {}).get("confidence", 0.0)) or 0.0)
        if recipe:
            base += min(0.2, float(recipe.get("inventory_match_percent", 0.0) or 0.0) / 500.0)
        if best:
            base += min(0.15, float(best.get("score", 0.0) or 0.0) * 0.15)
        return round(max(0.0, min(0.95, base)), 3)
