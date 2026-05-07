"""Plan build portfolios from piles of salvaged electronics."""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, Iterable, List

from src.intelligence.salvage_splice_planner import SalvageSplicePlanner


class SalvagePortfolioPlanner:
    """Turn many junk items into prioritized builds, safety holds, and work orders."""

    def __init__(self, splice_planner: SalvageSplicePlanner | None = None):
        self.splice_planner = splice_planner or SalvageSplicePlanner()

    def plan(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        items = self._items_from_payload(payload)
        item_plans = [self._plan_item(item, index) for index, item in enumerate(items, start=1)]
        safety_holds = [row for row in item_plans if row["plan"].get("verdict") == "unsafe_hold"]
        usable = [row for row in item_plans if row["plan"].get("verdict") != "unsafe_hold"]
        aggregate_blocks = self._aggregate_blocks(usable)
        aggregate_plan = self.splice_planner.plan(
            {
                "title": str(payload.get("title") or "salvage pile portfolio"),
                "goal": str(payload.get("goal") or "build the most valuable useful gadgets from this pile"),
                "available_parts": aggregate_blocks,
            }
        )
        build_portfolio = self._build_portfolio(aggregate_plan, aggregate_blocks, payload)
        capability_gaps = self._capability_gaps(build_portfolio)
        work_order = self._work_order(build_portfolio, safety_holds, capability_gaps)
        summary = self._summary(item_plans, build_portfolio, safety_holds)
        return {
            "mode": "salvage_reuse_portfolio_plan",
            "summary": summary,
            "item_plans": [
                {
                    "item_id": row["item_id"],
                    "title": row["title"],
                    "verdict": row["plan"].get("verdict"),
                    "target": row["plan"].get("target"),
                    "block_count": len(row["plan"].get("reusable_blocks") or []),
                    "stop_conditions": row["plan"].get("stop_conditions") or [],
                }
                for row in item_plans
            ],
            "safety_holds": [
                {
                    "item_id": row["item_id"],
                    "title": row["title"],
                    "stop_conditions": row["plan"].get("stop_conditions") or [],
                    "recoverable_after_review": self._recoverable_after_review(row["plan"]),
                }
                for row in safety_holds
            ],
            "aggregate_inventory": {
                "reusable_block_count": len(aggregate_blocks),
                "capability_summary": self._capability_summary(aggregate_blocks),
                "blocks": aggregate_blocks[:60],
            },
            "build_portfolio": build_portfolio,
            "capability_gaps": capability_gaps,
            "work_order": work_order,
            "operator_guidance": [
                "Do safety holds first; do not power hazardous items while harvesting low-voltage modules.",
                "Build the first portfolio item as a proof case before splitting attention across many projects.",
                "Treat every cross-item splice as unknown until voltage, polarity, current, ground, and mechanical clearance are measured.",
                "Record final output function, time saved, recovered value, and parts left over for the next portfolio pass.",
            ],
        }

    def _items_from_payload(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        raw_items = payload.get("items") or payload.get("pile") or payload.get("devices")
        if isinstance(raw_items, list) and raw_items:
            return [self._normalize_item(item, index) for index, item in enumerate(raw_items, start=1)]
        if isinstance(raw_items, dict):
            return [self._normalize_item(raw_items, 1)]
        parts = payload.get("available_parts") or payload.get("inventory") or payload.get("modules") or []
        return [
            {
                "title": str(payload.get("title") or "salvage pile"),
                "goal": str(payload.get("goal") or "reuse useful parts"),
                "available_parts": parts,
                "description": str(payload.get("description") or payload.get("notes") or ""),
            }
        ]

    def _normalize_item(self, item: Any, index: int) -> Dict[str, Any]:
        if isinstance(item, dict):
            title = str(item.get("title") or item.get("name") or item.get("device") or f"item {index}")
            parts = item.get("available_parts") or item.get("inventory") or item.get("modules") or item.get("parts") or []
            return {
                **item,
                "title": title,
                "goal": str(item.get("goal") or "reuse useful parts"),
                "available_parts": parts,
            }
        return {"title": str(item), "goal": "reuse useful parts", "available_parts": [str(item)]}

    def _plan_item(self, item: Dict[str, Any], index: int) -> Dict[str, Any]:
        plan = self.splice_planner.plan(item)
        return {
            "item_id": str(item.get("item_id") or item.get("id") or f"item_{index}"),
            "title": str(item.get("title") or f"item {index}"),
            "plan": plan,
        }

    def _aggregate_blocks(self, item_plans: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        blocks = []
        for item in item_plans:
            for block in item["plan"].get("reusable_blocks") or []:
                if not isinstance(block, dict):
                    continue
                blocks.append(
                    {
                        "name": block.get("name") or block.get("block_id") or "reusable block",
                        "capabilities": block.get("capabilities") or [],
                        "quantity": block.get("quantity", 1),
                        "confidence": block.get("confidence", 0.5),
                        "source_item_id": item["item_id"],
                        "source_title": item["title"],
                        "block_id": f"{item['item_id']}::{block.get('block_id') or block.get('name')}",
                        "required_tests": block.get("required_tests") or [],
                        "suggested_uses": block.get("suggested_uses") or [],
                    }
                )
        return blocks

    def _build_portfolio(
        self,
        aggregate_plan: Dict[str, Any],
        blocks: List[Dict[str, Any]],
        payload: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        max_builds = int(payload.get("max_builds", 5) or 5)
        rows = []
        for candidate in (aggregate_plan.get("build_candidates") or [])[: max(1, min(max_builds * 2, 10))]:
            allocated = self._allocated_blocks(blocks, candidate)
            source_items = sorted({block.get("source_title") for block in allocated if block.get("source_title")})
            missing_groups = candidate.get("missing_capability_groups") or []
            readiness = "ready_after_measurements" if not missing_groups else "needs_parts_or_substitute"
            score = float(candidate.get("score", 0.0) or 0.0)
            score += 0.04 * min(len(source_items), 4)
            score += 0.03 * min(len(allocated), 6)
            score -= 0.08 * len(missing_groups)
            rows.append(
                {
                    "rank": 0,
                    "build_id": candidate.get("id"),
                    "name": candidate.get("name"),
                    "readiness": readiness,
                    "portfolio_score": round(max(0.0, min(score, 1.0)), 3),
                    "difficulty": candidate.get("difficulty"),
                    "estimated_output_value_usd": candidate.get("estimated_output_value_usd", 0.0),
                    "output_function": candidate.get("output_function"),
                    "source_items": source_items,
                    "allocated_blocks": allocated[:10],
                    "matched_capabilities": candidate.get("matched_capabilities") or [],
                    "missing_capability_groups": missing_groups,
                    "first_build_step": candidate.get("first_build_step"),
                    "first_proof_demo": self._first_proof_demo(candidate),
                }
            )
        rows = sorted(rows, key=lambda row: (row["readiness"] == "ready_after_measurements", row["portfolio_score"]), reverse=True)
        for index, row in enumerate(rows[:max_builds], start=1):
            row["rank"] = index
        return rows[:max_builds]

    def _allocated_blocks(self, blocks: List[Dict[str, Any]], candidate: Dict[str, Any]) -> List[Dict[str, Any]]:
        matched_caps = set(candidate.get("matched_capabilities") or [])
        nice_caps = set(candidate.get("nice_to_have_matched") or [])
        desired_caps = matched_caps | nice_caps
        if not desired_caps:
            return []

        primary_source = self._primary_source(blocks, desired_caps)
        allocated: List[Dict[str, Any]] = []
        seen = set()

        def add_block(cap: str | None = None, terms: Iterable[str] = (), prefer_primary: bool = True) -> None:
            candidates = self._matching_blocks(blocks, cap, terms)
            candidates = sorted(
                candidates,
                key=lambda item: (
                    item.get("source_title") == primary_source if prefer_primary else False,
                    float(item.get("confidence", 0.0) or 0.0),
                ),
                reverse=True,
            )
            for block in candidates:
                key = (block.get("source_item_id"), block.get("block_id"))
                if key in seen:
                    continue
                seen.add(key)
                allocated.append(self._allocated_block_record(block, desired_caps))
                return

        build_id = str(candidate.get("id") or "")
        if build_id == "inspection_motion_fixture":
            add_block("mechanical_motion", ["rail", "linear", "belt", "carriage"])
            add_block("motor_or_load", ["stepper", "servo", "motor"])
            add_block("led_or_light", ["light", "led", "camera"])
            add_block("sensor_or_adc", ["sensor", "optical", "limit"])
            add_block("switch_or_button", ["switch", "limit"])
            add_block("power", ["adapter", "supply", "usb", "5v", "12v"])
        else:
            for cap in sorted(matched_caps):
                add_block(cap)
            for cap in sorted(nice_caps):
                if len(allocated) >= 8:
                    break
                add_block(cap)

        covered_caps = {cap for block in allocated for cap in block.get("capabilities", [])}
        if matched_caps and matched_caps.issubset(covered_caps):
            return allocated[:8]

        for block in sorted(blocks, key=lambda item: float(item.get("confidence", 0.0) or 0.0), reverse=True):
            if len(allocated) >= 8:
                break
            block_caps = set(block.get("capabilities") or [])
            if not (block_caps & desired_caps):
                continue
            key = (block.get("source_item_id"), block.get("block_id"))
            if key in seen:
                continue
            seen.add(key)
            allocated.append(self._allocated_block_record(block, desired_caps))
        return allocated

    def _primary_source(self, blocks: List[Dict[str, Any]], caps: set[str]) -> str | None:
        scores = Counter()
        for block in blocks:
            source = block.get("source_title")
            if not source:
                continue
            overlap = set(block.get("capabilities") or []) & caps
            if overlap:
                scores[str(source)] += len(overlap)
        return scores.most_common(1)[0][0] if scores else None

    def _matching_blocks(self, blocks: List[Dict[str, Any]], cap: str | None, terms: Iterable[str]) -> List[Dict[str, Any]]:
        lowered_terms = [str(term).lower() for term in terms]
        matches = []
        for block in blocks:
            block_caps = set(block.get("capabilities") or [])
            name = str(block.get("name") or block.get("block_id") or "").lower()
            if cap and cap not in block_caps:
                continue
            if lowered_terms and not any(term in name for term in lowered_terms):
                continue
            matches.append(block)
        if not matches and cap:
            return [block for block in blocks if cap in set(block.get("capabilities") or [])]
        return matches

    def _allocated_block_record(self, block: Dict[str, Any], caps: set[str]) -> Dict[str, Any]:
        block_caps = set(block.get("capabilities") or [])
        return {
            "block_id": block.get("block_id"),
            "name": block.get("name"),
            "source_item_id": block.get("source_item_id"),
            "source_title": block.get("source_title"),
            "capabilities": sorted(block_caps & caps),
            "tests_before_use": (block.get("required_tests") or [])[:4],
        }

    def _capability_summary(self, blocks: List[Dict[str, Any]]) -> Dict[str, int]:
        counts = Counter()
        for block in blocks:
            for cap in block.get("capabilities") or []:
                counts[str(cap)] += int(block.get("quantity", 1) or 1)
        return dict(sorted(counts.items()))

    def _capability_gaps(self, builds: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        gaps = []
        seen = set()
        for build in builds:
            for group in build.get("missing_capability_groups") or []:
                key = tuple(group)
                if key in seen:
                    continue
                seen.add(key)
                gaps.append(
                    {
                        "missing_any_of": list(group),
                        "needed_for": build.get("name"),
                        "source_options": self._source_options(group),
                    }
                )
        return gaps

    def _source_options(self, group: Iterable[str]) -> List[str]:
        options = []
        mapping = {
            "controller": "ESP32/Arduino-class controller module",
            "actuator_driver": "MOSFET, relay, motor driver, or ULN2003 board",
            "power": "known low-voltage adapter, buck converter, or protected USB power module",
            "connector": "matching harness, screw terminal, or labeled breakout",
            "sensor_or_adc": "optical sensor, limit switch, temperature/current sensor, or ADC breakout",
            "led_or_light": "LED strip, scanner light bar, IR LEDs, or task-light board",
            "camera_or_vision": "USB webcam, phone camera module with known interface, or inspection camera",
        }
        for cap in group:
            options.append(mapping.get(str(cap), str(cap).replace("_", " ")))
        return options[:4]

    def _first_proof_demo(self, candidate: Dict[str, Any]) -> str:
        build_id = str(candidate.get("id") or "")
        if build_id == "inspection_motion_fixture":
            return "show one slow rail movement with the light/camera/sensor powered separately, then record a repeatable inspection image"
        if build_id == "usb_fume_extractor":
            return "show airflow, current draw, and a one-minute thermal check from a current-limited supply"
        if build_id == "network_status_indicator":
            return "show a powered status-light pattern or link indicator using a known low-voltage supply"
        if build_id == "salvaged_input_panel":
            return "show each button/switch/joystick input changing state on a continuity tester or controller input"
        if build_id == "small_audio_amp_box":
            return "play a low-volume test tone after checking speaker impedance and amplifier supply voltage"
        return str(candidate.get("first_build_step") or "demonstrate the reused block alone before connecting it to another module")

    def _work_order(
        self,
        builds: List[Dict[str, Any]],
        safety_holds: List[Dict[str, Any]],
        gaps: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        steps = []
        if safety_holds:
            steps.append("isolate safety-hold items and recover only clearly low-voltage disconnected modules after review")
        if builds:
            top = builds[0]
            steps.extend(
                [
                    f"reserve blocks for {top.get('name')}",
                    "capture source photos and connector closeups for every allocated block",
                    "run voltage, polarity, resistance, current-limit, and continuity gates",
                    top.get("first_build_step") or "build the first standalone proof",
                    "record first proof demo, time saved, recovered value, and remaining blocks",
                ]
            )
        if gaps:
            steps.append("source or substitute the highest-impact missing capability group")
        return {
            "first_build": builds[0] if builds else None,
            "steps": steps or ["scan or list more salvage items before building"],
            "review_queue_seed": [
                "confirm each source item and recovered block label",
                "verify all voltage domains before cross-item interconnect",
                "record final output function and whether the build is worth repeating",
            ],
        }

    def _summary(
        self,
        item_plans: List[Dict[str, Any]],
        builds: List[Dict[str, Any]],
        safety_holds: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        top = builds[0] if builds else {}
        return {
            "item_count": len(item_plans),
            "safety_hold_count": len(safety_holds),
            "build_count": len(builds),
            "top_build_id": top.get("build_id"),
            "top_build": top.get("name"),
            "top_build_score": top.get("portfolio_score", 0.0),
            "estimated_output_value_usd": round(sum(float(row.get("estimated_output_value_usd", 0.0) or 0.0) for row in builds), 2),
            "verdict": "build_portfolio_ready" if builds else "collect_more_inventory",
        }

    def _recoverable_after_review(self, plan: Dict[str, Any]) -> List[str]:
        return [
            block.get("name")
            for block in plan.get("reusable_blocks") or []
            if isinstance(block, dict) and "battery" not in set(block.get("capabilities") or [])
        ][:8]
