"""Evidence ledger for separating known, likely, weak, and missing scan claims."""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, Iterable, List, Sequence


class CertaintyLedgerBuilder:
    """Build a deterministic confidence ledger from the existing analysis outputs.

    The ledger is intentionally conservative. It does not try to make the vision
    model smarter; it makes every downstream claim auditable and tells the user
    what evidence would move the claim from possible to likely or certain.
    """

    def build(
        self,
        *,
        detections: Sequence[Any] | None = None,
        detection_summary: Dict[str, Any] | None = None,
        marking_analysis: Dict[str, Any] | None = None,
        board_understanding: Dict[str, Any] | None = None,
        machine_connection_map: Dict[str, Any] | None = None,
        visual_topology: Dict[str, Any] | None = None,
        defect_inspection: Dict[str, Any] | None = None,
        aoi_inspection: Dict[str, Any] | None = None,
        reference_aoi: Dict[str, Any] | None = None,
        topology_aoi: Dict[str, Any] | None = None,
        golden_aoi: Dict[str, Any] | None = None,
        salvage_opportunities: Dict[str, Any] | None = None,
        scan_quality: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        detection_summary = detection_summary or {}
        marking_analysis = marking_analysis or {}
        board_understanding = board_understanding or {}
        machine_connection_map = machine_connection_map or {}
        visual_topology = visual_topology or {}
        defect_inspection = defect_inspection or {}
        aoi_inspection = aoi_inspection or {}
        reference_aoi = reference_aoi or {}
        topology_aoi = topology_aoi or {}
        golden_aoi = golden_aoi or {}
        salvage_opportunities = salvage_opportunities or {}
        scan_quality = scan_quality or (aoi_inspection.get("scan_quality") if isinstance(aoi_inspection.get("scan_quality"), dict) else {}) or {}

        items: List[Dict[str, Any]] = []
        for index, detection in enumerate(detections or []):
            items.append(self._component_item(index, detection, detection_summary))

        items.extend(self._marking_items(marking_analysis))
        board_item = self._board_role_item(
            board_understanding,
            marking_analysis,
            visual_topology,
            detection_summary,
        )
        if board_item:
            items.append(board_item)
        items.extend(self._functional_block_items(board_understanding))

        connector_item = self._connector_item(machine_connection_map, marking_analysis)
        if connector_item:
            items.append(connector_item)

        topology_item = self._topology_item(visual_topology, topology_aoi)
        if topology_item:
            items.append(topology_item)

        defect_items = self._defect_items(defect_inspection, golden_aoi)
        items.extend(defect_items)

        aoi_item = self._aoi_item(aoi_inspection, reference_aoi, topology_aoi, golden_aoi)
        if aoi_item:
            items.append(aoi_item)

        salvage_item = self._salvage_item(salvage_opportunities, board_understanding, marking_analysis)
        if salvage_item:
            items.append(salvage_item)

        global_missing = self._global_missing_evidence(
            detections=detections or [],
            detection_summary=detection_summary,
            marking_analysis=marking_analysis,
            board_understanding=board_understanding,
            machine_connection_map=machine_connection_map,
            visual_topology=visual_topology,
            defect_inspection=defect_inspection,
            aoi_inspection=aoi_inspection,
            reference_aoi=reference_aoi,
            topology_aoi=topology_aoi,
            golden_aoi=golden_aoi,
            scan_quality=scan_quality,
        )
        missing = self._dedupe(
            global_missing
            + [
                str(item)
                for claim in items
                for item in (claim.get("missing_evidence") or [])
                if str(item).strip()
            ]
        )
        next_actions = self._dedupe(
            [
                str(action)
                for claim in items
                for action in (claim.get("next_actions") or [])
                if str(action).strip()
            ]
        )
        counts = Counter(str(item.get("certainty") or "unknown") for item in items)
        overall_score = self._overall_score(items, detection_summary, scan_quality)
        overall_level = self._level(overall_score)

        return {
            "mode": "evidence_certainty_ledger",
            "overall": {
                "score": round(overall_score, 3),
                "level": overall_level,
                "summary": self._overall_summary(overall_level, overall_score, counts, missing),
                "claim_boundary": (
                    "Claims are evidence-weighted scan conclusions, not proof. Use measurements, "
                    "known-good references, datasheets, or design files before powering, repairing, "
                    "selling, or splicing hardware."
                ),
            },
            "items": sorted(items, key=lambda item: float(item.get("score", 0.0)), reverse=True)[:90],
            "missing_evidence": missing[:30],
            "next_actions": next_actions[:30],
            "training_queue": self._training_queue(items, missing, detection_summary, marking_analysis),
            "counts": {
                "certain": int(counts.get("certain", 0)),
                "likely": int(counts.get("likely", 0)),
                "possible": int(counts.get("possible", 0)),
                "unknown": int(counts.get("unknown", 0)),
                "total": len(items),
            },
        }

    def build_multiview(
        self,
        *,
        views: Sequence[Dict[str, Any]],
        fused_board_understanding: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        fused_board_understanding = fused_board_understanding or {}
        child_ledgers = [
            view.get("certainty_ledger") for view in views
            if isinstance(view.get("certainty_ledger"), dict)
        ]
        child_items = [
            item
            for ledger in child_ledgers
            for item in (ledger.get("items") or [])
            if isinstance(item, dict)
        ]
        identity = fused_board_understanding.get("board_identity") or {}
        labels = (fused_board_understanding.get("machine_context") or {}).get("connector_label_evidence") or []
        score = self._clamp(
            float(identity.get("confidence", fused_board_understanding.get("confidence", 0.0)) or 0.0)
            + min(0.12, 0.03 * max(0, len(views) - 1))
            + (0.05 if labels else 0.0)
        )
        items = [
            {
                "item_id": "multiview_fused_board_role",
                "claim_type": "board_role",
                "claim": f"Fused board role is {identity.get('primary_type', 'unknown_board')}",
                "certainty": self._level(score),
                "score": round(score, 3),
                "evidence": self._evidence(
                    ("view_count", len(views), 0.18),
                    ("fused_identity_confidence", identity.get("confidence", fused_board_understanding.get("confidence", 0.0)), 0.3),
                    ("connector_label_evidence", ", ".join(str(label) for label in labels[:12]), 0.12),
                    ("role_evidence", "; ".join(str(item) for item in (identity.get("evidence") or [])[:8]), 0.2),
                ),
                "missing_evidence": [
                    "calibrated front/back registration or design files"
                ] if score < 0.82 else [],
                "next_actions": [
                    "use repeated evidence across views before committing to repair or salvage",
                    "capture targeted closeups for labels that appear only in one view",
                ],
                "usable_for": ["repair", "salvage", "training", "aoi"],
            }
        ]
        items.extend(sorted(child_items, key=lambda item: float(item.get("score", 0.0)), reverse=True)[:40])
        missing = self._dedupe(
            [
                str(item)
                for ledger in child_ledgers
                for item in (ledger.get("missing_evidence") or [])
                if str(item).strip()
            ]
            + [
                "calibrated scale and board-side registration for mechanical splice planning",
                "known-good reference or netlist for production AOI decisions",
            ]
        )
        counts = Counter(str(item.get("certainty") or "unknown") for item in items)
        overall_score = self._overall_score(items, {}, {})
        overall_level = self._level(overall_score)
        return {
            "mode": "multi_view_evidence_certainty_ledger",
            "overall": {
                "score": round(overall_score, 3),
                "level": overall_level,
                "summary": self._overall_summary(overall_level, overall_score, counts, missing),
                "claim_boundary": (
                    "Multi-view fusion aggregates evidence but does not geometrically register board sides. "
                    "Use calibration or design files for splice dimensions and production release gates."
                ),
            },
            "items": items[:90],
            "missing_evidence": missing[:30],
            "next_actions": self._dedupe(
                [
                    "compare repeated markings/components across views",
                    "capture connector closeups and reverse-side photos",
                    "add netlist, BOM, or golden reference for production AOI confidence",
                ]
            ),
            "training_queue": {
                "should_capture": bool(missing),
                "reasons": missing[:8],
                "candidate_labels": self._candidate_labels(items),
            },
            "counts": {
                "certain": int(counts.get("certain", 0)),
                "likely": int(counts.get("likely", 0)),
                "possible": int(counts.get("possible", 0)),
                "unknown": int(counts.get("unknown", 0)),
                "total": len(items),
            },
        }

    def empty(self, reason: str = "") -> Dict[str, Any]:
        missing = ["valid PCB/device image and analysis output"]
        if reason:
            missing.append(reason)
        return {
            "mode": "evidence_certainty_ledger",
            "overall": {
                "score": 0.0,
                "level": "unknown",
                "summary": "No reliable evidence was available for this scan.",
                "claim_boundary": "No scan claims should be used until analysis succeeds.",
            },
            "items": [],
            "missing_evidence": missing,
            "next_actions": ["retry analysis with a valid image", "capture a clear whole-board photo"],
            "training_queue": {"should_capture": True, "reasons": missing, "candidate_labels": []},
            "counts": {"certain": 0, "likely": 0, "possible": 0, "unknown": 0, "total": 0},
        }

    def _component_item(
        self,
        index: int,
        detection: Any,
        detection_summary: Dict[str, Any],
    ) -> Dict[str, Any]:
        record = self._detection_record(index, detection)
        backend = record.get("backend", "unknown")
        score = self._component_score(record, detection_summary)
        class_name = record.get("class_name", "unknown")
        text = record.get("ocr_text") or record.get("part_number")
        missing = []
        next_actions = []
        if backend.startswith("classical"):
            missing.append("learned detector or human confirmation for heuristic component class")
        if class_name in {"ic_chip", "connector", "microcontroller", "usb_connector"} and not text:
            missing.append("close-up OCR crop for markings or connector labels")
        if score < 0.6:
            next_actions.append("review bounding box and class label against the photo")
        if text and score >= 0.6:
            next_actions.append("resolve marking against datasheet/pinout evidence")
        return {
            "item_id": f"component_{index + 1}_{self._slug(class_name)}",
            "claim_type": "component",
            "claim": f"Detected {class_name}",
            "certainty": self._level(score),
            "score": round(score, 3),
            "evidence": self._evidence(
                ("visual_detection", record.get("bbox"), 0.35),
                ("detector_confidence", record.get("confidence"), 0.25),
                ("semantic_confidence", record.get("semantic_confidence"), 0.15),
                ("detector_backend", backend, 0.12),
                ("ocr_text", text, 0.1),
            ),
            "missing_evidence": missing,
            "next_actions": next_actions,
            "usable_for": ["inventory", "repair", "salvage", "training"],
        }

    def _marking_items(self, marking_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        items = []
        for index, component in enumerate(marking_analysis.get("components", []) or []):
            candidates = component.get("candidates") or []
            best = max(candidates, key=lambda item: float(item.get("confidence", 0.0) or 0.0), default={})
            labels = component.get("silk_labels") or []
            part = best.get("part_number") or (component.get("part_tokens") or [""])[0] or ""
            has_datasheet = isinstance(best.get("datasheet"), dict)
            has_pinout = isinstance(best.get("pinout"), dict)
            base = float(best.get("confidence", 0.35 if labels else 0.18) or 0.0)
            if has_datasheet:
                base += 0.08
            if has_pinout:
                base += 0.1
            if str(best.get("match_type", "")).startswith("unresolved"):
                base = min(base, 0.34)
            score = self._clamp(base)
            missing = []
            if not has_datasheet:
                missing.append("datasheet match or trusted part database entry")
            if not has_pinout and part:
                missing.append("pinout/package confirmation")
            if score < 0.6:
                missing.append("sharper marking crop from the package top")
            items.append(
                {
                    "item_id": f"marking_{index + 1}_{self._slug(part or component.get('class_name', 'component'))}",
                    "claim_type": "marking",
                    "claim": (
                        f"Marking {component.get('text', '').strip() or part or 'unknown'} "
                        f"maps to {part or 'an unresolved part'}"
                    ),
                    "certainty": self._level(score),
                    "score": round(score, 3),
                    "evidence": self._evidence(
                        ("ocr_text", component.get("text"), 0.22),
                        ("part_tokens", ", ".join(component.get("part_tokens") or []), 0.18),
                        ("silk_labels", ", ".join(labels), 0.12),
                        ("match_type", best.get("match_type"), 0.15),
                        ("datasheet", has_datasheet, 0.14),
                        ("pinout", has_pinout, 0.16),
                    ),
                    "missing_evidence": missing,
                    "next_actions": [
                        "verify package orientation and pin count",
                        "use datasheet/pinout evidence before wiring or resale",
                    ],
                    "usable_for": ["repair", "salvage", "pinout", "training"],
                }
            )
        return items

    def _board_role_item(
        self,
        board_understanding: Dict[str, Any],
        marking_analysis: Dict[str, Any],
        visual_topology: Dict[str, Any],
        detection_summary: Dict[str, Any],
    ) -> Dict[str, Any] | None:
        identity = board_understanding.get("board_identity") or {}
        role = identity.get("primary_type") or "unknown_board"
        if role == "unknown_board" and not board_understanding:
            return None
        score = self._clamp(
            float(identity.get("confidence", board_understanding.get("confidence", 0.0)) or 0.0)
            + (0.07 if identity.get("evidence") else 0.0)
            + 0.08 * min(float(marking_analysis.get("confidence", 0.0) or 0.0), 1.0)
            + 0.05 * min(float(visual_topology.get("confidence", 0.0) or 0.0), 1.0)
            + 0.03 * min(float(detection_summary.get("total_components", 0) or 0) / 8.0, 1.0)
        )
        missing = []
        if score < 0.82:
            missing.extend(["device model/use context", "reverse-side photo or board file"])
        if float(visual_topology.get("confidence", 0.0) or 0.0) < 0.45:
            missing.append("stronger topology evidence from traces, netlist, or continuity measurements")
        return {
            "item_id": "board_role_primary",
            "claim_type": "board_role",
            "claim": f"Board role is {role}",
            "certainty": self._level(score),
            "score": round(score, 3),
            "evidence": self._evidence(
                ("role_confidence", identity.get("confidence", board_understanding.get("confidence")), 0.28),
                ("role_evidence", "; ".join(str(item) for item in (identity.get("evidence") or [])[:8]), 0.22),
                ("functional_blocks", len(board_understanding.get("functional_blocks", []) or []), 0.18),
                ("marking_confidence", marking_analysis.get("confidence"), 0.14),
                ("topology_confidence", visual_topology.get("confidence"), 0.12),
            ),
            "missing_evidence": missing,
            "next_actions": [
                "tie the inferred board role to symptoms, connector labels, and measurements",
                "capture missing side/label evidence before committing to a repair or build plan",
            ],
            "usable_for": ["repair", "salvage", "build_planning", "training"],
        }

    def _functional_block_items(self, board_understanding: Dict[str, Any]) -> List[Dict[str, Any]]:
        items = []
        for index, block in enumerate((board_understanding.get("functional_blocks") or [])[:12]):
            score = self._clamp(float(block.get("confidence", 0.0) or 0.0) + 0.04 * min(int(block.get("component_count", 0) or 0), 4))
            items.append(
                {
                    "item_id": f"functional_block_{index + 1}_{self._slug(block.get('block_type', 'block'))}",
                    "claim_type": "functional_block",
                    "claim": f"{block.get('label') or block.get('block_type', 'Functional block')} exists",
                    "certainty": self._level(score),
                    "score": round(score, 3),
                    "evidence": self._evidence(
                        ("block_type", block.get("block_type"), 0.18),
                        ("component_count", block.get("component_count"), 0.18),
                        ("block_confidence", block.get("confidence"), 0.22),
                        ("bbox", block.get("bbox"), 0.12),
                        ("function", block.get("function"), 0.12),
                    ),
                    "missing_evidence": [
                        "crop-level verification of the grouped components"
                    ] if score < 0.7 else [],
                    "next_actions": [
                        "use crop hint for closer visual inspection",
                        "validate rails/signals before harvesting this block",
                    ],
                    "usable_for": ["repair", "salvage", "splicing", "training"],
                }
            )
        return items

    def _connector_item(
        self,
        machine_connection_map: Dict[str, Any],
        marking_analysis: Dict[str, Any],
    ) -> Dict[str, Any] | None:
        connector_count = int(machine_connection_map.get("connector_count", 0) or 0)
        labels = marking_analysis.get("connector_labels", []) or []
        interfaces = machine_connection_map.get("interfaces", []) or []
        if connector_count <= 0 and not labels and not interfaces:
            return None
        score = self._clamp(
            float(machine_connection_map.get("confidence", 0.0) or 0.0)
            + 0.04 * min(connector_count, 4)
            + 0.03 * min(len(labels), 8)
            + 0.05 * min(len(interfaces), 4)
        )
        missing = [
            "connector close-up with pin-1 marker and label side"
        ] if score < 0.82 else []
        missing.append("continuity and voltage measurements before splicing")
        return {
            "item_id": "machine_connector_map",
            "claim_type": "connector",
            "claim": f"{connector_count} connector candidate(s) mapped for machine integration",
            "certainty": self._level(score),
            "score": round(score, 3),
            "evidence": self._evidence(
                ("connector_count", connector_count, 0.2),
                ("labels", ", ".join(labels[:16]), 0.2),
                ("interfaces", ", ".join(str(item.get("type")) for item in interfaces[:8] if isinstance(item, dict)), 0.22),
                ("map_confidence", machine_connection_map.get("confidence"), 0.24),
            ),
            "missing_evidence": missing,
            "next_actions": (machine_connection_map.get("splice_plan") or {}).get("required_measurements", [])[:8]
            or ["measure power/ground resistance and rail voltage before wiring"],
            "usable_for": ["repair", "salvage", "splicing", "build_planning"],
        }

    def _topology_item(
        self,
        visual_topology: Dict[str, Any],
        topology_aoi: Dict[str, Any],
    ) -> Dict[str, Any] | None:
        if not visual_topology:
            return None
        topo_status = topology_aoi.get("status", "unavailable")
        score = self._clamp(
            float(visual_topology.get("confidence", 0.0) or 0.0)
            + (0.25 if topo_status == "PASS" else 0.0)
            - (0.18 if topo_status == "FAIL" else 0.0)
        )
        missing = []
        if topo_status == "unavailable":
            missing.append("reference netlist or continuity measurements for topology verification")
        if score < 0.6:
            missing.append("reverse-side/hidden-trace evidence")
        return {
            "item_id": "visible_topology",
            "claim_type": "topology",
            "claim": "Visible trace topology is estimated from the scan",
            "certainty": self._level(score),
            "score": round(score, 3),
            "evidence": self._evidence(
                ("trace_count", visual_topology.get("trace_count"), 0.16),
                ("connection_count", visual_topology.get("connection_count"), 0.18),
                ("topology_confidence", visual_topology.get("confidence"), 0.22),
                ("reference_topology_status", topo_status, 0.18),
            ),
            "missing_evidence": missing,
            "next_actions": [
                "use netlist, KiCad file, or continuity checks for high-confidence circuit understanding",
                "capture the reverse side if traces are hidden",
            ],
            "usable_for": ["repair", "aoi", "training"],
        }

    def _defect_items(
        self,
        defect_inspection: Dict[str, Any],
        golden_aoi: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        items = []
        golden_status = golden_aoi.get("status", "unavailable")
        for index, defect in enumerate((defect_inspection.get("defects") or [])[:20]):
            score = self._clamp(
                0.45 * float(defect.get("confidence", 0.0) or 0.0)
                + 0.35 * float(defect.get("severity", 0.0) or 0.0)
                + (0.18 if golden_status == "FAIL" else 0.0)
            )
            items.append(
                {
                    "item_id": f"defect_{index + 1}_{self._slug(defect.get('defect_type', 'defect'))}",
                    "claim_type": "defect",
                    "claim": f"Possible {defect.get('defect_type', 'visual defect')}",
                    "certainty": self._level(score),
                    "score": round(score, 3),
                    "evidence": self._evidence(
                        ("defect_bbox", defect.get("bbox"), 0.18),
                        ("defect_confidence", defect.get("confidence"), 0.22),
                        ("severity", defect.get("severity"), 0.2),
                        ("golden_aoi_status", golden_status, 0.18),
                        ("repair_action", defect.get("repair_action"), 0.12),
                    ),
                    "missing_evidence": [
                        "golden/reference photo from a known-good board"
                    ] if golden_status == "unavailable" else [],
                    "next_actions": [
                        defect.get("repair_action") or "inspect and rework only after visual confirmation",
                        "confirm defect under magnification before replacing parts",
                    ],
                    "usable_for": ["repair", "aoi", "training"],
                }
            )
        return items

    def _aoi_item(
        self,
        aoi_inspection: Dict[str, Any],
        reference_aoi: Dict[str, Any],
        topology_aoi: Dict[str, Any],
        golden_aoi: Dict[str, Any],
    ) -> Dict[str, Any] | None:
        if not aoi_inspection:
            return None
        readiness = aoi_inspection.get("readiness", "unknown")
        base = float(aoi_inspection.get("score", 0.0) or 0.0)
        pass_bonus = 0.0
        for status in [reference_aoi.get("status"), topology_aoi.get("status"), golden_aoi.get("status")]:
            if status == "PASS":
                pass_bonus += 0.08
            elif status == "FAIL":
                pass_bonus -= 0.1
        score = self._clamp(base + pass_bonus)
        missing = [
            blocker for blocker in (aoi_inspection.get("blockers") or [])
            if isinstance(blocker, str) and blocker.strip()
        ][:10]
        return {
            "item_id": "aoi_readiness",
            "claim_type": "aoi",
            "claim": f"AOI readiness is {readiness}",
            "certainty": self._level(score),
            "score": round(score, 3),
            "evidence": self._evidence(
                ("aoi_score", aoi_inspection.get("score"), 0.24),
                ("reference_component_status", reference_aoi.get("status"), 0.16),
                ("reference_topology_status", topology_aoi.get("status"), 0.16),
                ("golden_image_status", golden_aoi.get("status"), 0.18),
                ("scan_quality", aoi_inspection.get("scan_quality"), 0.14),
            ),
            "missing_evidence": missing,
            "next_actions": [
                "add known-good reference, netlist, or golden image before production release",
                "collect labeled defect examples from the target camera/lighting setup",
            ],
            "usable_for": ["aoi", "production_gate", "training"],
        }

    def _salvage_item(
        self,
        salvage_opportunities: Dict[str, Any],
        board_understanding: Dict[str, Any],
        marking_analysis: Dict[str, Any],
    ) -> Dict[str, Any] | None:
        best = salvage_opportunities.get("best_opportunity") or {}
        opportunities = salvage_opportunities.get("opportunities") or []
        if not best and not opportunities:
            return None
        score = self._clamp(
            float(salvage_opportunities.get("confidence", 0.0) or 0.0)
            + 0.18 * float(best.get("score", 0.0) or 0.0)
            + 0.05 * min(len(opportunities), 5)
            + 0.05 * min(float(marking_analysis.get("confidence", 0.0) or 0.0), 1.0)
            + 0.04 * min(float(board_understanding.get("confidence", 0.0) or 0.0), 1.0)
        )
        missing = []
        if best.get("missing_assets"):
            missing.append(f"missing assets for top opportunity: {', '.join(str(item) for item in best.get('missing_assets')[:8])}")
        missing.extend([
            "electrical validation before reuse/resale",
            "live market price check before arbitrage decision",
        ])
        return {
            "item_id": "salvage_opportunity",
            "claim_type": "salvage",
            "claim": f"Best salvage/build route is {best.get('name', 'unknown')}",
            "certainty": self._level(score),
            "score": round(score, 3),
            "evidence": self._evidence(
                ("salvage_confidence", salvage_opportunities.get("confidence"), 0.22),
                ("best_opportunity_score", best.get("score"), 0.2),
                ("opportunity_type", best.get("type"), 0.14),
                ("matched_assets", ", ".join(str(item) for item in (best.get("matched_assets") or [])[:8]), 0.18),
            ),
            "missing_evidence": missing,
            "next_actions": best.get("next_steps", [])[:8]
            or ["test part", "verify marking/package", "estimate resale or build value"],
            "usable_for": ["salvage", "build_planning", "arbitrage"],
        }

    def _global_missing_evidence(
        self,
        *,
        detections: Sequence[Any],
        detection_summary: Dict[str, Any],
        marking_analysis: Dict[str, Any],
        board_understanding: Dict[str, Any],
        machine_connection_map: Dict[str, Any],
        visual_topology: Dict[str, Any],
        defect_inspection: Dict[str, Any],
        aoi_inspection: Dict[str, Any],
        reference_aoi: Dict[str, Any],
        topology_aoi: Dict[str, Any],
        golden_aoi: Dict[str, Any],
        scan_quality: Dict[str, Any],
    ) -> List[str]:
        missing = []
        scan_score = float(scan_quality.get("score", 1.0) or 0.0) if scan_quality else 1.0
        if scan_score < 0.55:
            missing.append("retake scan with sharper focus, flatter angle, and more even lighting")
        if not detections:
            missing.append("whole-board image with visible components")
        if detection_summary.get("review_required"):
            missing.append("operator review of heuristic or low-confidence detections")
        if not marking_analysis.get("components"):
            missing.append("close-up photos of IC/package markings and silk labels")
        identity = board_understanding.get("board_identity") or {}
        if float(identity.get("confidence", board_understanding.get("confidence", 0.0)) or 0.0) < 0.6:
            missing.append("device context, model number, symptoms, or known function")
        if int(machine_connection_map.get("connector_count", 0) or 0) > 0 and machine_connection_map.get("confidence", 0.0) < 0.7:
            missing.append("connector close-up plus voltage/continuity measurements")
        if float(visual_topology.get("confidence", 0.0) or 0.0) < 0.5:
            missing.append("netlist, KiCad/Gerber files, reverse-side photo, or continuity map")
        if reference_aoi.get("status") == "unavailable":
            missing.append("reference component counts or known-good board for component AOI")
        if topology_aoi.get("status") == "unavailable":
            missing.append("reference topology/netlist for circuit-level AOI")
        if golden_aoi.get("status") == "unavailable":
            missing.append("golden reference image for defect AOI")
        if int(defect_inspection.get("defect_count", 0) or 0) > 0:
            missing.append("microscope confirmation and before/after repair photo for each defect")
        if aoi_inspection.get("readiness") in {"research_preview", "unknown", None}:
            missing.append("calibrated camera/lighting fixture and labeled target-domain examples")
        return self._dedupe(missing)

    def _training_queue(
        self,
        items: Sequence[Dict[str, Any]],
        missing: Sequence[str],
        detection_summary: Dict[str, Any],
        marking_analysis: Dict[str, Any],
    ) -> Dict[str, Any]:
        weak_items = [
            item for item in items
            if str(item.get("certainty")) in {"possible", "unknown"}
        ]
        reasons = []
        if weak_items:
            reasons.append(f"{len(weak_items)} low-certainty claim(s) need labels or evidence")
        if detection_summary.get("review_required"):
            reasons.append("detector emitted review-required component candidates")
        if not marking_analysis.get("components"):
            reasons.append("OCR/marking evidence absent or unresolved")
        reasons.extend(str(item) for item in missing[:6])
        return {
            "should_capture": bool(weak_items or missing or detection_summary.get("review_required")),
            "reasons": self._dedupe(reasons)[:10],
            "candidate_labels": self._candidate_labels(items),
        }

    def _candidate_labels(self, items: Sequence[Dict[str, Any]]) -> List[str]:
        labels = []
        for item in items:
            if item.get("claim_type") in {"component", "defect", "functional_block", "marking"}:
                claim = str(item.get("claim", "")).strip()
                if claim:
                    labels.append(claim)
        return self._dedupe(labels)[:25]

    def _overall_score(
        self,
        items: Sequence[Dict[str, Any]],
        detection_summary: Dict[str, Any],
        scan_quality: Dict[str, Any],
    ) -> float:
        if not items:
            return 0.0
        weights = {
            "board_role": 1.4,
            "marking": 1.25,
            "connector": 1.2,
            "aoi": 1.25,
            "salvage": 1.15,
            "topology": 1.1,
            "defect": 1.0,
            "functional_block": 0.95,
            "component": 0.85,
        }
        total_weight = 0.0
        total_score = 0.0
        for item in items:
            weight = weights.get(str(item.get("claim_type")), 0.8)
            total_weight += weight
            total_score += weight * float(item.get("score", 0.0) or 0.0)
        score = total_score / max(total_weight, 1e-9)
        if detection_summary.get("review_required"):
            score -= 0.08
        if scan_quality:
            score -= 0.08 * max(0.0, 0.55 - float(scan_quality.get("score", 1.0) or 0.0)) / 0.55
        return self._clamp(score)

    def _overall_summary(
        self,
        level: str,
        score: float,
        counts: Counter,
        missing: Sequence[str],
    ) -> str:
        if level == "certain":
            lead = "Evidence is strong enough for operator-confirmed planning."
        elif level == "likely":
            lead = "Evidence is useful for repair, salvage, and next-action planning."
        elif level == "possible":
            lead = "The scan can suggest directions, but key claims need more evidence."
        else:
            lead = "The scan is not reliable enough for action yet."
        return (
            f"{lead} Ledger score {score:.2f}; "
            f"{counts.get('certain', 0)} certain, {counts.get('likely', 0)} likely, "
            f"{counts.get('possible', 0)} possible, {counts.get('unknown', 0)} unknown claim(s). "
            f"Top missing evidence: {missing[0] if missing else 'none'}."
        )

    def _component_score(self, record: Dict[str, Any], detection_summary: Dict[str, Any]) -> float:
        confidence = float(record.get("confidence", 0.0) or 0.0)
        semantic = record.get("semantic_confidence")
        semantic_score = float(semantic if isinstance(semantic, (int, float)) else confidence)
        backend = str(record.get("backend") or "unknown")
        backend_bonus = 0.0
        if backend == "yolo":
            backend_bonus = 0.12
        elif backend.startswith("yolo"):
            backend_bonus = 0.09
        elif backend == "remote":
            backend_bonus = 0.06
        elif backend.startswith("classical"):
            backend_bonus = -0.12
        text_bonus = 0.06 if record.get("ocr_text") or record.get("part_number") else 0.0
        class_bonus = 0.04 if record.get("class_name") not in {"unknown", "component"} else -0.04
        semantic_bonus = 0.06 if semantic_score >= 0.6 else 0.0
        review_penalty = 0.08 if detection_summary.get("review_required") else 0.0
        return self._clamp(0.62 * confidence + 0.18 * semantic_score + 0.08 + backend_bonus + text_bonus + class_bonus + semantic_bonus - review_penalty)

    def _detection_record(self, index: int, detection: Any) -> Dict[str, Any]:
        if isinstance(detection, dict):
            class_name = detection.get("class_name") or detection.get("label") or detection.get("type") or "component"
            provenance = detection.get("provenance") if isinstance(detection.get("provenance"), dict) else {}
            return {
                "id": detection.get("id") or f"cmp_{index + 1}",
                "class_name": self._norm(class_name),
                "bbox": self._jsonish(detection.get("bbox") or []),
                "confidence": self._float(detection.get("confidence", detection.get("score", 0.0))),
                "semantic_confidence": self._maybe_float(detection.get("semantic_confidence")),
                "backend": str(provenance.get("backend") or detection.get("backend") or "unknown"),
                "ocr_text": str(detection.get("ocr_text") or detection.get("text_content") or detection.get("text") or ""),
                "part_number": str(detection.get("part_number") or ""),
            }
        class_name = getattr(detection, "class_name", None) or getattr(detection, "label", None) or "component"
        return {
            "id": getattr(detection, "id", f"cmp_{index + 1}"),
            "class_name": self._norm(class_name),
            "bbox": self._jsonish(getattr(detection, "bbox", []) or []),
            "confidence": self._float(getattr(detection, "confidence", 0.0)),
            "semantic_confidence": self._maybe_float(getattr(detection, "semantic_confidence", None)),
            "backend": str(getattr(detection, "backend", "unknown")),
            "ocr_text": str(getattr(detection, "ocr_text", "") or getattr(detection, "text_content", "")),
            "part_number": str(getattr(detection, "part_number", "") or ""),
        }

    @staticmethod
    def _evidence(*entries: tuple[str, Any, float]) -> List[Dict[str, Any]]:
        evidence = []
        for evidence_type, value, weight in entries:
            if value is None or value == "" or value == [] or value == {}:
                continue
            evidence.append({"type": evidence_type, "value": value, "weight": round(float(weight), 3)})
        return evidence

    @staticmethod
    def _level(score: float) -> str:
        if score >= 0.82:
            return "certain"
        if score >= 0.6:
            return "likely"
        if score >= 0.35:
            return "possible"
        return "unknown"

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(1.0, float(value or 0.0)))

    @staticmethod
    def _float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @classmethod
    def _maybe_float(cls, value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _norm(value: Any) -> str:
        return str(value or "unknown").strip().lower().replace(" ", "_").replace("-", "_")

    @classmethod
    def _slug(cls, value: Any) -> str:
        text = cls._norm(value)
        return "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in text).strip("_") or "item"

    @staticmethod
    def _dedupe(items: Iterable[str]) -> List[str]:
        seen = set()
        result = []
        for item in items:
            text = str(item or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            result.append(text)
        return result

    def _jsonish(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {str(k): self._jsonish(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._jsonish(v) for v in value]
        if hasattr(value, "item"):
            try:
                return value.item()
            except Exception:
                pass
        return value
