"""Turn salvaged electronics evidence into build, resale, and reuse opportunities."""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, Iterable, List, Sequence


class SalvageOpportunityEngine:
    """Score what a pile of boards/components can become."""

    PROJECT_CATALOG = [
        {
            "id": "wifi_relay_switch",
            "name": "Smart WiFi Relay Switch",
            "requires": {"wireless", "actuator_driver", "power"},
            "nice_to_have": {"connector", "enclosure_candidate"},
            "category": "upcycled_gadget",
            "estimated_output_value_usd": 18.0,
            "build_complexity": "medium",
        },
        {
            "id": "bench_power_module",
            "name": "Bench Power Supply Module",
            "requires": {"power"},
            "nice_to_have": {"connector", "display_or_ui"},
            "category": "tooling",
            "estimated_output_value_usd": 22.0,
            "build_complexity": "medium",
        },
        {
            "id": "usb_uart_adapter",
            "name": "USB/UART Debug Adapter",
            "requires": {"usb_serial"},
            "nice_to_have": {"connector"},
            "category": "tooling",
            "estimated_output_value_usd": 8.0,
            "build_complexity": "easy",
        },
        {
            "id": "robot_motor_controller",
            "name": "Robot Motor Controller",
            "requires": {"controller", "actuator_driver"},
            "nice_to_have": {"wireless", "connector"},
            "category": "robotics",
            "estimated_output_value_usd": 28.0,
            "build_complexity": "hard",
        },
        {
            "id": "sensor_gateway",
            "name": "Sensor Gateway / Data Logger",
            "requires": {"controller", "sensor_or_adc"},
            "nice_to_have": {"wireless", "display_or_ui"},
            "category": "iot",
            "estimated_output_value_usd": 24.0,
            "build_complexity": "medium",
        },
        {
            "id": "led_controller",
            "name": "LED / Light Controller",
            "requires": {"controller", "actuator_driver"},
            "nice_to_have": {"wireless", "connector"},
            "category": "consumer_gadget",
            "estimated_output_value_usd": 16.0,
            "build_complexity": "medium",
        },
    ]

    RESALE_PART_VALUES = {
        "esp32": 5.0,
        "esp8266": 3.0,
        "atmega328p": 4.0,
        "stm32": 6.0,
        "cp2102": 2.0,
        "ft232": 3.0,
        "lm2596": 2.0,
        "uln2003": 1.5,
        "relay": 1.0,
        "transformer": 3.0,
        "display": 4.0,
        "sensor": 3.0,
    }

    def evaluate(
        self,
        analyses: Sequence[Dict[str, Any]] | Dict[str, Any],
        market_context: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        views = list(analyses if isinstance(analyses, list) else [analyses])
        assets = self._extract_assets(views)
        project_opportunities = self._project_opportunities(assets)
        resale_opportunities = self._resale_opportunities(assets)
        sourcing_opportunities = self._sourcing_opportunities(assets, market_context or {})
        ranked = sorted(
            project_opportunities + resale_opportunities + sourcing_opportunities,
            key=lambda item: float(item.get("score", 0.0)),
            reverse=True,
        )
        return {
            "mode": "salvage_and_arbitrage_opportunity_engine",
            "asset_summary": assets,
            "opportunities": ranked[:12],
            "best_opportunity": ranked[0] if ranked else None,
            "strategy": self._strategy(ranked, assets),
            "confidence": self._confidence(assets, ranked),
            "limitations": [
                "value estimates are planning estimates until parts are tested and market prices are verified",
                "salvaged modules need electrical validation before resale or reuse",
                "e-commerce arbitrage requires listing price, shipping, failure rate, labor, and demand checks",
            ],
        }

    def _extract_assets(self, analyses: List[Dict[str, Any]]) -> Dict[str, Any]:
        capabilities = Counter()
        parts = Counter()
        defects = 0
        connectors = 0
        evidence = []

        for analysis in analyses:
            direct_summary = (analysis.get("salvage_opportunities") or {}).get("asset_summary") or {}
            for capability, count in (direct_summary.get("capabilities") or {}).items():
                capabilities[str(capability)] += int(count or 1)
            for part, count in (direct_summary.get("parts") or {}).items():
                part_key = str(part).lower()
                parts[part_key] += int(count or 1)
                self._add_part_capabilities(capabilities, part_key)
            connectors += int(direct_summary.get("connector_count", 0) or 0)
            defects += int(direct_summary.get("defect_count", 0) or 0)
            evidence.extend(str(item) for item in (direct_summary.get("evidence") or [])[:12])

            board = analysis.get("board_understanding") or analysis.get("fused_board_understanding") or {}
            role = (board.get("board_identity") or {}).get("primary_type", "")
            if role:
                self._add_role_capabilities(capabilities, role)
                evidence.append(f"board role: {role}")
            for block in board.get("functional_blocks", []) or []:
                self._add_block_capabilities(capabilities, block.get("block_type", ""))
            marking = analysis.get("marking_analysis") or {}
            for component in marking.get("components", []) or []:
                for candidate in component.get("candidates", []) or []:
                    part = str(candidate.get("part_number") or "").lower()
                    if part:
                        parts[part] += 1
                        self._add_part_capabilities(capabilities, part)
                        evidence.append(f"part marking: {part}")
            connection = analysis.get("machine_connection_map") or {}
            connectors += int(connection.get("connector_count", 0) or 0)
            for interface in connection.get("interfaces", []) or []:
                interface_type = str(interface.get("type") or "")
                if interface_type:
                    capabilities[interface_type] += 1
                    evidence.append(f"interface: {interface_type}")
            defects += int((analysis.get("defect_inspection") or {}).get("defect_count", 0) or 0)

        if connectors:
            capabilities["connector"] += connectors
        return {
            "capabilities": dict(sorted(capabilities.items())),
            "parts": dict(sorted(parts.items())),
            "connector_count": connectors,
            "defect_count": defects,
            "evidence": evidence[:30],
        }

    def _project_opportunities(self, assets: Dict[str, Any]) -> List[Dict[str, Any]]:
        caps = set((assets.get("capabilities") or {}).keys())
        opportunities = []
        for project in self.PROJECT_CATALOG:
            required = set(project["requires"])
            present = required & caps
            missing = sorted(required - caps)
            nice = set(project.get("nice_to_have", set()))
            nice_hits = sorted(nice & caps)
            match = len(present) / max(len(required), 1)
            if match <= 0:
                continue
            risk_penalty = min(0.25, 0.05 * int(assets.get("defect_count", 0) or 0))
            score = max(0.0, 0.45 * match + 0.08 * len(nice_hits) - risk_penalty)
            opportunities.append(
                {
                    "type": "build_from_salvage",
                    "id": project["id"],
                    "name": project["name"],
                    "category": project["category"],
                    "score": round(min(score, 0.95), 3),
                    "estimated_output_value_usd": project["estimated_output_value_usd"],
                    "build_complexity": project["build_complexity"],
                    "matched_assets": sorted(present),
                    "missing_assets": missing,
                    "nice_to_have_matched": nice_hits,
                    "next_steps": self._project_next_steps(missing),
                }
            )
        return opportunities

    def _resale_opportunities(self, assets: Dict[str, Any]) -> List[Dict[str, Any]]:
        opportunities = []
        for part, count in (assets.get("parts") or {}).items():
            value = self.RESALE_PART_VALUES.get(part)
            if value is None:
                for key, key_value in self.RESALE_PART_VALUES.items():
                    if key in part:
                        value = key_value
                        break
            if value is None:
                continue
            total = round(value * int(count), 2)
            opportunities.append(
                {
                    "type": "resell_or_stock",
                    "id": f"resell_{part}",
                    "name": f"Recover/stock {part.upper()}",
                    "score": round(min(0.9, 0.35 + total / 40.0), 3),
                    "estimated_output_value_usd": total,
                    "matched_assets": [part],
                    "missing_assets": [],
                    "next_steps": ["test part", "verify marking/package", "sort into inventory", "check live market price"],
                }
            )
        return opportunities

    def _sourcing_opportunities(
        self,
        assets: Dict[str, Any],
        market_context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        listings = market_context.get("listings") or []
        opportunities = []
        for listing in listings:
            price = float(listing.get("price_usd", 0.0) or 0.0)
            expected_caps = set(str(cap).lower() for cap in listing.get("expected_capabilities", []) or [])
            expected_parts = set(str(part).lower() for part in listing.get("expected_parts", []) or [])
            if price <= 0 or not (expected_caps or expected_parts):
                continue
            projected_value = 0.0
            for project in self.PROJECT_CATALOG:
                if set(project["requires"]) & expected_caps:
                    projected_value = max(projected_value, float(project["estimated_output_value_usd"]))
            for part in expected_parts:
                projected_value += self.RESALE_PART_VALUES.get(part, 0.0)
            margin = projected_value - price
            shipping = float(listing.get("shipping_usd", 0.0) or 0.0)
            labor = float(listing.get("labor_usd", 0.0) or 0.0)
            failure_rate = max(0.0, min(0.95, float(listing.get("failure_rate", 0.15) or 0.0)))
            fee_rate = max(0.0, min(0.5, float(listing.get("fee_rate", 0.13) or 0.0)))
            adjusted_value = projected_value * (1.0 - failure_rate) * (1.0 - fee_rate)
            adjusted_margin = adjusted_value - price - shipping - labor
            if adjusted_margin <= 0:
                continue
            opportunities.append(
                {
                    "type": "ecommerce_arbitrage",
                    "id": f"listing_{listing.get('id', len(opportunities) + 1)}",
                    "name": f"Acquire {listing.get('title', 'listing')} for parts/builds",
                    "score": round(min(0.9, 0.35 + adjusted_margin / max(projected_value, 1.0)), 3),
                    "input_cost_usd": price,
                    "estimated_output_value_usd": round(projected_value, 2),
                    "adjusted_output_value_usd": round(adjusted_value, 2),
                    "estimated_margin_usd": round(margin, 2),
                    "adjusted_margin_usd": round(adjusted_margin, 2),
                    "assumptions": {
                        "shipping_usd": shipping,
                        "labor_usd": labor,
                        "failure_rate": failure_rate,
                        "fee_rate": fee_rate,
                    },
                    "matched_assets": sorted(expected_caps | expected_parts),
                    "missing_assets": [],
                    "next_steps": ["verify listing photos", "check shipping", "estimate failure rate", "compare sold prices"],
                }
            )
        return opportunities

    def _add_role_capabilities(self, caps: Counter, role: str) -> None:
        mapping = {
            "power_supply_or_regulator": ["power"],
            "controller_or_embedded_compute": ["controller"],
            "io_interface_or_adapter": ["connector"],
            "motor_or_actuator_driver": ["actuator_driver"],
            "sensor_or_signal_conditioning": ["sensor_or_adc"],
            "wireless_or_communications": ["wireless"],
            "display_or_user_interface": ["display_or_ui"],
        }
        for cap in mapping.get(role, []):
            caps[cap] += 1

    def _add_block_capabilities(self, caps: Counter, block: str) -> None:
        mapping = {
            "power_input_protection": "power",
            "power_regulation": "power",
            "compute_control": "controller",
            "io_connectivity": "connector",
            "user_interface": "display_or_ui",
            "actuator_drive": "actuator_driver",
            "sensor_frontend": "sensor_or_adc",
        }
        if block in mapping:
            caps[mapping[block]] += 1

    def _add_part_capabilities(self, caps: Counter, part: str) -> None:
        if any(token in part for token in ("esp32", "esp8266")):
            caps["controller"] += 1
            caps["wireless"] += 1
        if any(token in part for token in ("atmega", "stm32", "pic")):
            caps["controller"] += 1
        if any(token in part for token in ("cp2102", "ch340", "ft232")):
            caps["usb_serial"] += 1
            caps["connector"] += 1
        if any(token in part for token in ("lm7805", "ams1117", "lm2596")):
            caps["power"] += 1
        if any(token in part for token in ("uln2003", "relay", "mosfet")):
            caps["actuator_driver"] += 1
        if any(token in part for token in ("bmp280", "bme280", "ads1115", "sensor")):
            caps["sensor_or_adc"] += 1

    def _project_next_steps(self, missing: List[str]) -> List[str]:
        steps = ["test harvested modules", "create pin map", "verify power rails"]
        if missing:
            steps.append(f"source missing assets: {', '.join(missing)}")
        else:
            steps.append("prototype build using harvested modules")
        return steps

    def _strategy(self, ranked: List[Dict[str, Any]], assets: Dict[str, Any]) -> Dict[str, Any]:
        if not ranked:
            return {
                "recommendation": "inventory_first",
                "reason": "No strong opportunity yet; collect more views, OCR closeups, and part tests.",
            }
        best = ranked[0]
        if best["type"] == "build_from_salvage" and not best.get("missing_assets"):
            action = "build_now"
        elif best["type"] == "build_from_salvage":
            action = "source_missing_parts_then_build"
        elif best["type"] == "ecommerce_arbitrage":
            action = "verify_listing_then_buy"
        else:
            action = "recover_and_stock_parts"
        return {
            "recommendation": action,
            "reason": f"Top opportunity is {best['name']} with score {best['score']}.",
            "inventory_focus": sorted((assets.get("capabilities") or {}).keys()),
        }

    def _confidence(self, assets: Dict[str, Any], ranked: List[Dict[str, Any]]) -> float:
        evidence_count = len(assets.get("evidence", []) or [])
        opportunity_bonus = 0.15 if ranked else 0.0
        defect_penalty = min(0.2, 0.04 * int(assets.get("defect_count", 0) or 0))
        return round(max(0.0, min(0.9, 0.25 + 0.04 * evidence_count + opportunity_bonus - defect_penalty)), 3)
