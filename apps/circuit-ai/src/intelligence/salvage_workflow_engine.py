"""Persistent salvage-to-product workflow orchestration."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Sequence

from src.intelligence.recipe_optimizer import RecipeOptimizer
from src.intelligence.build_package_generator import BuildPackageGenerator
from src.intelligence.salvage_opportunity_engine import SalvageOpportunityEngine


@dataclass
class SalvageAsset:
    asset_id: str
    asset_type: str
    name: str
    capabilities: List[str]
    source: str
    condition: str = "unknown"
    test_status: str = "untested"
    confidence: float = 0.0
    estimated_value_usd: float = 0.0
    quantity: int = 1
    evidence: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class SalvageWorkflowEngine:
    """Bridge scans/listings/inventory into practical product decisions."""

    def __init__(self, inventory_path: str | Path = "data/salvage_inventory.json"):
        self.inventory_path = Path(inventory_path)
        self.opportunity_engine = SalvageOpportunityEngine()
        self.recipe_optimizer = RecipeOptimizer()
        self.package_generator = BuildPackageGenerator()
        self.assets: List[SalvageAsset] = []
        self._load()

    def ingest_analysis(
        self,
        analysis: Dict[str, Any],
        source: str = "scan",
        commit: bool = True,
    ) -> Dict[str, Any]:
        assets = self._assets_from_analysis(analysis, source=source)
        if commit:
            self.assets.extend(assets)
            self._save()
        report = self.plan_from_inventory(extra_analyses=[analysis])
        return {
            "mode": "salvage_analysis_ingest",
            "created_assets": [asdict(asset) for asset in assets],
            "inventory_size": len(self.assets),
            "report": report,
        }

    def ingest_listing(
        self,
        listing: Dict[str, Any],
        commit: bool = True,
    ) -> Dict[str, Any]:
        title = str(listing.get("title") or "market listing")
        expected_caps = [str(cap).lower() for cap in listing.get("expected_capabilities", []) or []]
        expected_parts = [str(part).lower() for part in listing.get("expected_parts", []) or []]
        price = float(listing.get("price_usd", 0.0) or 0.0)
        asset = SalvageAsset(
            asset_id=self._asset_id("listing", title),
            asset_type="market_listing",
            name=title,
            capabilities=sorted(set(expected_caps + expected_parts)),
            source=str(listing.get("url") or listing.get("source") or "marketplace"),
            condition=str(listing.get("condition", "unknown")),
            test_status="not_purchased",
            confidence=float(listing.get("confidence", 0.45) or 0.45),
            estimated_value_usd=price,
            evidence=[f"listing price: ${price:.2f}", f"expected: {', '.join(expected_caps + expected_parts)}"],
            metadata=dict(listing),
        )
        if commit:
            self.assets.append(asset)
            self._save()
        report = self.plan_from_inventory(
            market_context={"listings": [listing]},
        )
        return {
            "mode": "salvage_listing_ingest",
            "created_asset": asdict(asset),
            "inventory_size": len(self.assets),
            "report": report,
        }

    def record_test_result(
        self,
        asset_id: str,
        test_status: str,
        condition: str | None = None,
        notes: str | None = None,
    ) -> Dict[str, Any]:
        for asset in self.assets:
            if asset.asset_id == asset_id:
                asset.test_status = test_status
                if condition:
                    asset.condition = condition
                if notes:
                    asset.evidence.append(f"test: {notes}")
                self._save()
                return {"updated": asdict(asset)}
        return {"error": f"asset not found: {asset_id}"}

    def plan_from_inventory(
        self,
        extra_analyses: Sequence[Dict[str, Any]] | None = None,
        market_context: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        synthetic_analysis = self._analysis_from_inventory()
        analyses = [synthetic_analysis] + list(extra_analyses or [])
        opportunities = self.opportunity_engine.evaluate(analyses, market_context=market_context)
        recipe_report = self._recipe_report()
        build_plan = self._build_execution_plan(opportunities, recipe_report)
        report = {
            "mode": "salvage_to_product_workflow",
            "inventory": self.inventory_summary(),
            "opportunity_report": opportunities,
            "recipe_report": recipe_report,
            "execution_plan": build_plan,
            "decision": self._decision(opportunities, build_plan),
        }
        report["build_package"] = self.package_generator.generate(report)
        return report

    def inventory_summary(self) -> Dict[str, Any]:
        by_capability: Dict[str, int] = {}
        by_status: Dict[str, int] = {}
        total_value = 0.0
        for asset in self.assets:
            total_value += float(asset.estimated_value_usd or 0.0) * int(asset.quantity or 1)
            by_status[asset.test_status] = by_status.get(asset.test_status, 0) + asset.quantity
            for capability in asset.capabilities:
                by_capability[capability] = by_capability.get(capability, 0) + asset.quantity
        return {
            "asset_count": sum(asset.quantity for asset in self.assets),
            "unique_records": len(self.assets),
            "estimated_inventory_value_usd": round(total_value, 2),
            "by_capability": dict(sorted(by_capability.items())),
            "by_test_status": dict(sorted(by_status.items())),
            "assets": [asdict(asset) for asset in self.assets],
        }

    def _assets_from_analysis(self, analysis: Dict[str, Any], source: str) -> List[SalvageAsset]:
        assets: List[SalvageAsset] = []
        salvage = analysis.get("salvage_opportunities") or {}
        asset_summary = salvage.get("asset_summary") or {}
        board = analysis.get("board_understanding") or {}
        identity = board.get("board_identity") or {}
        role = identity.get("primary_type", "unknown_board")
        capabilities = sorted((asset_summary.get("capabilities") or {}).keys())
        if role != "unknown_board" or capabilities:
            assets.append(
                SalvageAsset(
                    asset_id=self._asset_id("board", role),
                    asset_type="board_or_module",
                    name=role,
                    capabilities=capabilities,
                    source=source,
                    condition="candidate",
                    test_status="untested",
                    confidence=float(identity.get("confidence", board.get("confidence", 0.0)) or 0.0),
                    estimated_value_usd=self._estimate_capability_value(capabilities),
                    evidence=list(asset_summary.get("evidence", []) or [])[:12],
                    metadata={
                        "board_identity": identity,
                        "functional_blocks": board.get("functional_blocks", []),
                        "machine_connection_map": analysis.get("machine_connection_map", {}),
                    },
                )
            )

        for part, count in (asset_summary.get("parts") or {}).items():
            assets.append(
                SalvageAsset(
                    asset_id=self._asset_id("part", part),
                    asset_type="component",
                    name=part.upper(),
                    capabilities=[part],
                    source=source,
                    condition="candidate",
                    test_status="untested",
                    confidence=float((analysis.get("marking_analysis") or {}).get("confidence", 0.0) or 0.0),
                    estimated_value_usd=self.opportunity_engine.RESALE_PART_VALUES.get(str(part).lower(), 0.0),
                    quantity=int(count or 1),
                    evidence=[f"marking resolved: {part}"],
                    metadata={},
                )
            )
        return assets

    def _analysis_from_inventory(self) -> Dict[str, Any]:
        capabilities: Dict[str, int] = {}
        parts: Dict[str, int] = {}
        evidence: List[str] = []
        connector_count = 0
        for asset in self.assets:
            for capability in asset.capabilities:
                capabilities[capability] = capabilities.get(capability, 0) + asset.quantity
                if capability in self.opportunity_engine.RESALE_PART_VALUES:
                    parts[capability] = parts.get(capability, 0) + asset.quantity
            if "connector" in asset.capabilities:
                connector_count += asset.quantity
            evidence.extend(asset.evidence[:3])
        return {
            "salvage_opportunities": {
                "asset_summary": {
                    "capabilities": capabilities,
                    "parts": parts,
                    "connector_count": connector_count,
                    "defect_count": 0,
                    "evidence": evidence[:30],
                }
            },
            "board_understanding": {
                "board_identity": {"primary_type": "inventory_bundle", "confidence": 0.5},
                "functional_blocks": [],
            },
        }

    def _recipe_report(self) -> Dict[str, Any]:
        inventory = self._optimizer_inventory()
        recipes = self.recipe_optimizer.generate_recipes(inventory, top_n=8)
        recipes = sorted(
            recipes,
            key=lambda recipe: (
                float(recipe.inventory_match_percent),
                -float(recipe.missing_parts_cost),
                float(recipe.roi_percent),
            ),
            reverse=True,
        )
        return {
            "inventory_for_optimizer": inventory,
            "recipes": [self._serialize_recipe(recipe) for recipe in recipes],
            "best_recipe": self._serialize_recipe(recipes[0]) if recipes else None,
        }

    def _optimizer_inventory(self) -> List[Dict[str, Any]]:
        inventory: List[Dict[str, Any]] = []
        capability_to_recipe_ids = {
            "controller": ["esp32", "arduino_nano", "arduino_uno"],
            "wireless": ["esp32", "esp8266"],
            "sensor_or_adc": ["bme280", "dht22"],
            "display_or_ui": ["oled_ssd1306", "lcd_16x2"],
            "actuator_driver": ["relay"],
            "motor_or_servo": ["servo_sg90"],
            "power": ["power_supply"],
            "usb_serial": ["arduino_nano"],
        }
        seen = set()
        for asset in self.assets:
            for capability in asset.capabilities:
                cap = capability.lower()
                ids = capability_to_recipe_ids.get(cap, [cap])
                for comp_id in ids:
                    key = (comp_id, asset.condition)
                    if key in seen:
                        continue
                    seen.add(key)
                    inventory.append(
                        {
                            "id": comp_id,
                            "condition": "used" if asset.condition in {"working", "candidate", "unknown"} else asset.condition,
                            "quantity": max(1, int(asset.quantity or 1)),
                            "source_asset": asset.asset_id,
                        }
                    )
        return inventory

    def _serialize_recipe(self, recipe: Any) -> Dict[str, Any]:
        if recipe is None:
            return {}
        return {
            "name": recipe.name,
            "category": recipe.category.value if hasattr(recipe.category, "value") else str(recipe.category),
            "description": recipe.description,
            "difficulty": recipe.difficulty,
            "required_components": recipe.required_components,
            "components_owned": recipe.components_owned,
            "components_needed": recipe.components_needed,
            "inventory_match_percent": recipe.inventory_match_percent,
            "missing_parts_cost": recipe.missing_parts_cost,
            "parts_cost": recipe.parts_cost,
            "market_price_low": recipe.market_price_low,
            "market_price_high": recipe.market_price_high,
            "profit_margin": recipe.profit_margin,
            "roi_percent": recipe.roi_percent,
            "build_time_hours": recipe.build_time_hours,
        }

    def _build_execution_plan(
        self,
        opportunity_report: Dict[str, Any],
        recipe_report: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        best = opportunity_report.get("best_opportunity")
        best_recipe = (recipe_report or {}).get("best_recipe")
        if not best:
            return {
                "status": "collect_more_assets",
                "steps": ["scan more boards", "capture chip closeups", "test power rails", "add market listings"],
            }
        steps = []
        if best.get("type") == "build_from_salvage":
            steps = [
                "reserve matched salvage assets",
                "run electrical validation on every reused module",
                "source or substitute missing assets" if best.get("missing_assets") else "prototype interconnect between matched modules",
                "generate wiring/pinout checklist",
                "build first functional prototype",
                "estimate enclosure, labor, and resale price",
            ]
        elif best.get("type") == "ecommerce_arbitrage":
            steps = [
                "verify listing photos and seller reliability",
                "calculate shipping/tax/labor/failure-rate adjusted margin",
                "buy only if adjusted margin remains positive",
                "test and split listing into build/resale inventory",
            ]
        else:
            steps = [
                "recover part safely",
                "test part electrically",
                "label and stock inventory",
                "compare resale vs reuse value",
            ]
        return {
            "status": "ready_to_execute",
            "target": best.get("name"),
            "target_type": best.get("type"),
            "recipe_target": best_recipe,
            "steps": steps,
            "validation_gates": [
                "no unknown power polarity",
                "all reused modules pass basic continuity",
                "known voltage domains before interconnect",
                "defect candidates reviewed",
            ],
        }

    def _decision(self, opportunity_report: Dict[str, Any], build_plan: Dict[str, Any]) -> Dict[str, Any]:
        best = opportunity_report.get("best_opportunity") or {}
        score = float(best.get("score", 0.0) or 0.0)
        if score >= 0.65:
            action = "execute_top_opportunity"
        elif score >= 0.4:
            action = "validate_then_execute"
        else:
            action = "inventory_and_collect_more_evidence"
        return {
            "action": action,
            "reason": best.get("name", "No high-confidence opportunity yet"),
            "confidence": opportunity_report.get("confidence", 0.0),
            "next_step": (build_plan.get("steps") or ["scan more assets"])[0],
        }

    def _estimate_capability_value(self, capabilities: List[str]) -> float:
        values = {
            "controller": 5.0,
            "wireless": 4.0,
            "power": 4.0,
            "actuator_driver": 3.0,
            "sensor_or_adc": 3.0,
            "display_or_ui": 3.0,
            "usb_serial": 2.0,
            "connector": 1.0,
        }
        return round(sum(values.get(cap, 0.0) for cap in capabilities), 2)

    def _asset_id(self, prefix: str, name: str) -> str:
        base = "".join(ch.lower() if ch.isalnum() else "_" for ch in str(name or "asset")).strip("_")
        return f"{prefix}_{base}_{len(self.assets) + 1}"

    def _save(self) -> None:
        self.inventory_path.parent.mkdir(parents=True, exist_ok=True)
        self.inventory_path.write_text(
            json.dumps([asdict(asset) for asset in self.assets], indent=2),
            encoding="utf-8",
        )

    def _load(self) -> None:
        if not self.inventory_path.exists():
            self.assets = []
            return
        try:
            data = json.loads(self.inventory_path.read_text(encoding="utf-8"))
            self.assets = [SalvageAsset(**item) for item in data if isinstance(item, dict)]
        except Exception:
            self.assets = []
