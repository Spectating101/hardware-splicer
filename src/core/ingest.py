import numpy as np
from PIL import Image
from typing import Dict, Any, List, Tuple
from loguru import logger
from src.vision.detector import ComponentDetector
from src.vision.defect_detector import DefectDetector
from src.llm.mapper import FunctionalMapper
from src.intelligence.trace_analyzer import TraceAnalyzer
from src.intelligence.inspection_diff import InspectionDiff
from src.intelligence.topology_diff import TopologyDiff
from src.intelligence.board_function_inference import BoardFunctionInferencer
from src.intelligence.marking_resolver import MarkingResolver
from src.intelligence.connection_mapper import ConnectionMapper
from src.intelligence.salvage_opportunity_engine import SalvageOpportunityEngine
from src.intelligence.certainty_ledger import CertaintyLedgerBuilder
from src.vision.image_polisher import polish_for_opencv
from src.vision.golden_reference import GoldenReferenceInspector


class CircuitAnalyzer:
    """Main orchestrator for PCB analysis pipeline."""
    
    def __init__(self):
        """Initialize the circuit analyzer."""
        self.detector = ComponentDetector()
        self.defect_detector = DefectDetector(use_classical_fallback=True)
        self.mapper = FunctionalMapper()
        self.trace_analyzer = TraceAnalyzer()
        self.reference_diff = InspectionDiff()
        self.topology_diff = TopologyDiff()
        self.golden_inspector = GoldenReferenceInspector()
        self.board_inferencer = BoardFunctionInferencer()
        self.marking_resolver = MarkingResolver()
        self.connection_mapper = ConnectionMapper()
        self.salvage_engine = SalvageOpportunityEngine()
        self.certainty_builder = CertaintyLedgerBuilder()
        logger.info("CircuitAnalyzer initialized")
    
    def analyze_pcb(
        self,
        image: np.ndarray,
        backend: str | None = None,
        enable_ocr: bool | None = None,
        reference_counts: Dict[str, int] | None = None,
        reference_topology: Dict[str, Any] | None = None,
        reference_image: np.ndarray | None = None,
    ) -> Dict[str, Any]:
        """Complete PCB analysis pipeline."""
        try:
            logger.info("Starting PCB analysis")

            # Step 1: Preprocess image
            preprocessing = {}
            try:
                processed_image_raw = self.detector.preprocess_image(image, include_metadata=True)
            except TypeError:
                processed_image_raw = self.detector.preprocess_image(image)
            if isinstance(processed_image_raw, tuple):
                processed_image, preprocessing = processed_image_raw
            else:
                processed_image = processed_image_raw
            scan_quality = preprocessing.get("scan_quality") if isinstance(preprocessing, dict) else None
            
            # Step 2: Detect components
            detections = self.detector.detect_components(processed_image, backend=backend, enable_ocr=enable_ocr)
            
            # Step 3: Generate detection summary
            detection_summary = self.detector.get_detection_summary(detections)

            # Step 3.1: Optional golden/reference component count comparison
            reference_aoi = self._compare_with_reference(detections, reference_counts)
            golden_aoi = self._compare_with_golden_image(image, reference_image)
            
            # Step 4: Map to functional metadata
            functionality_data = self.mapper.map_detections_to_functionality(detections)
            marking_analysis = self._resolve_markings(detections)
            
            # Step 5: Estimate visual topology from traces and component geometry
            visual_topology = self._analyze_visual_topology(image, detections, detection_summary)

            # Step 5.1: Optional topology AOI against reference netlist
            topology_aoi = self._compare_with_reference_topology(
                visual_topology,
                reference_topology,
            )

            # Step 6: Detect visual defect candidates
            defect_inspection = self._detect_defect_candidates(image, detections)

            # Step 7: Infer board role, machine context, and reusable regions
            board_understanding = self._infer_board_understanding(
                image,
                detections,
                detection_summary,
                visual_topology,
                defect_inspection,
                marking_analysis,
            )
            machine_connection_map = self._map_machine_connections(
                detections,
                marking_analysis,
                board_understanding,
            )
            salvage_opportunities = self._evaluate_salvage_opportunities(
                {
                    "detection_summary": detection_summary,
                    "marking_analysis": marking_analysis,
                    "board_understanding": board_understanding,
                    "machine_connection_map": machine_connection_map,
                    "defect_inspection": defect_inspection,
                }
            )

            # Step 8: Assess AOI production readiness for this scan
            aoi_inspection = self._assess_aoi_readiness(
                detection_summary,
                visual_topology,
                defect_inspection,
                reference_aoi,
                topology_aoi,
                scan_quality=scan_quality,
                golden_aoi=golden_aoi,
            )

            # Step 9: Generate project recommendations
            recommendations = self.mapper.generate_project_recommendations(functionality_data)

            # Step 9.1: Build auditable certainty ledger across all evidence.
            certainty_ledger = self.certainty_builder.build(
                detections=detections,
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
                salvage_opportunities=salvage_opportunities,
                scan_quality=scan_quality,
            )
            
            # Step 10: Compile results
            results = {
                "detections": detections,
                "detection_summary": detection_summary,
                "functionality_analysis": functionality_data,
                "marking_analysis": marking_analysis,
                "board_understanding": board_understanding,
                "machine_connection_map": machine_connection_map,
                "salvage_opportunities": salvage_opportunities,
                "visual_topology": visual_topology,
                "topology_aoi": topology_aoi,
                "defect_inspection": defect_inspection,
                "reference_aoi": reference_aoi,
                "golden_aoi": golden_aoi,
                "aoi_inspection": aoi_inspection,
                "certainty_ledger": certainty_ledger,
                "project_recommendations": recommendations,
                "analysis_metadata": {
                    "total_processing_time": "~2 seconds",
                    "detection_quality": detection_summary.get("detection_quality", "unknown"),
                    "semantic_quality": detection_summary.get("semantic_quality", "unknown"),
                    "review_required": detection_summary.get("review_required", False),
                    "limitations": detection_summary.get("limitations", []),
                    "preprocessing": preprocessing,
                    "circuit_understanding_confidence": visual_topology.get("confidence", 0.0),
                    "defect_count": defect_inspection.get("defect_count", 0),
                    "reference_aoi_status": reference_aoi.get("status", "unavailable"),
                    "reference_component_delta": reference_aoi.get("component_delta", 0),
                    "golden_aoi_status": golden_aoi.get("status", "unavailable"),
                    "golden_defect_count": golden_aoi.get("defect_count", 0),
                    "topology_aoi_status": topology_aoi.get("status", "unavailable"),
                    "topology_aoi_delta": topology_aoi.get("topology_delta", 0),
                    "board_type": board_understanding.get("board_identity", {}).get("primary_type", "unknown_board"),
                    "board_function_confidence": board_understanding.get("confidence", 0.0),
                    "marking_confidence": marking_analysis.get("confidence", 0.0),
                    "resolved_marking_count": len(marking_analysis.get("components", []) or []),
                    "machine_connection_confidence": machine_connection_map.get("confidence", 0.0),
                    "connector_count": machine_connection_map.get("connector_count", 0),
                    "salvage_opportunity_count": len(salvage_opportunities.get("opportunities", []) or []),
                    "best_salvage_opportunity": (salvage_opportunities.get("best_opportunity") or {}).get("name"),
                    "functional_block_count": len(board_understanding.get("functional_blocks", []) or []),
                    "aoi_readiness": aoi_inspection.get("readiness", "unknown"),
                    "certainty_score": certainty_ledger.get("overall", {}).get("score", 0.0),
                    "certainty_level": certainty_ledger.get("overall", {}).get("level", "unknown"),
                    "certain_claim_count": certainty_ledger.get("counts", {}).get("certain", 0),
                    "likely_claim_count": certainty_ledger.get("counts", {}).get("likely", 0),
                    "missing_evidence_count": len(certainty_ledger.get("missing_evidence", []) or []),
                    "training_capture_recommended": bool((certainty_ledger.get("training_queue") or {}).get("should_capture")),
                    "scan_quality": aoi_inspection.get("scan_quality", {}),
                    "project_potential": functionality_data.get("project_potential", "none"),
                    "backend": backend or self.detector.default_backend,
                    "ocr": bool(enable_ocr) if enable_ocr is not None else self.detector.ocr_enabled_default
                }
            }
            
            logger.info(f"Analysis complete: {detection_summary.get('total_components', 0)} components detected")
            return results
            
        except Exception as e:
            logger.error(f"Error in PCB analysis: {e}")
            return {
                "error": str(e),
                "detection_summary": {"total_components": 0},
                "functionality_analysis": {"components": [], "capabilities": []},
                "marking_analysis": self._empty_marking_analysis(str(e)),
                "board_understanding": self._empty_board_understanding(str(e)),
                "machine_connection_map": self._empty_machine_connection_map(str(e)),
                "salvage_opportunities": self._empty_salvage_opportunities(str(e)),
                "visual_topology": self._empty_visual_topology(str(e)),
                "defect_inspection": self._empty_defect_inspection(str(e)),
                "reference_aoi": self._empty_reference_aoi(str(e)),
                "golden_aoi": self._empty_golden_aoi(str(e)),
                "topology_aoi": self._empty_topology_aoi(str(e)),
                "aoi_inspection": {"readiness": "unavailable", "score": 0.0, "blockers": [str(e)]},
                "certainty_ledger": self.certainty_builder.empty(str(e)),
                "project_recommendations": []
            }

    def analyze_board_set(
        self,
        images: List[np.ndarray],
        backend: str | None = None,
        enable_ocr: bool | None = None,
        reference_image: np.ndarray | None = None,
    ) -> Dict[str, Any]:
        """Analyze multiple views/crops of the same board and fuse evidence."""
        if not images:
            return {
                "error": "No images supplied",
                "views": [],
                "fused_board_understanding": self._empty_board_understanding("No images supplied"),
            }

        views = []
        for idx, image in enumerate(images):
            result = self.analyze_pcb(
                image,
                backend=backend,
                enable_ocr=enable_ocr,
                reference_image=reference_image if idx == 0 else None,
            )
            result["view_id"] = f"view_{idx + 1}"
            views.append(result)

        fused = self._fuse_board_views(views)
        certainty_ledger = self.certainty_builder.build_multiview(
            views=views,
            fused_board_understanding=fused,
        )
        return {
            "mode": "multi_image_board_analysis",
            "view_count": len(views),
            "views": views,
            "fused_board_understanding": fused,
            "certainty_ledger": certainty_ledger,
            "summary": self._multi_view_summary(fused, views),
        }

    def _compare_with_reference(
        self,
        detections: List[Dict[str, Any]],
        reference_counts: Dict[str, int] | None,
    ) -> Dict[str, Any]:
        if not reference_counts:
            return self._empty_reference_aoi()
        try:
            result = self.reference_diff.compare(reference_counts, detections)
            if result.get("status") == "PASS":
                result["notes"] = [
                    "Reference component counts match detected components.",
                    "Use this as a component-level production control gate alongside topology checks.",
                ]
            else:
                result["notes"] = [
                    "Component presence/quantity mismatch detected vs reference.",
                    "Run focused rework and retest before continuing AOI interpretation.",
                ]
            result["mode"] = "reference_component_count_aoi"
            return result
        except Exception as e:
            logger.warning(f"Reference AOI comparison failed: {e}")
            return self._empty_reference_aoi(str(e))

    def _fuse_board_views(self, views: List[Dict[str, Any]]) -> Dict[str, Any]:
        role_scores: Dict[str, float] = {}
        role_evidence: Dict[str, List[str]] = {}
        block_counts: Dict[str, int] = {}
        connector_labels = set()
        pinout_evidence = []
        connection_maps = []
        candidate_regions = []
        component_counts: Dict[str, int] = {}

        for view in views:
            view_id = view.get("view_id", "view")
            board = view.get("board_understanding") or {}
            identity = board.get("board_identity") or {}
            primary = identity.get("primary_type", "unknown_board")
            confidence = float(identity.get("confidence", board.get("confidence", 0.0)) or 0.0)
            role_scores[primary] = max(role_scores.get(primary, 0.0), confidence)
            role_evidence.setdefault(primary, []).extend([f"{view_id}: {item}" for item in identity.get("evidence", [])])
            for alt in identity.get("alternatives", []) or []:
                role = alt.get("type", "unknown_board")
                score = float(alt.get("confidence", 0.0) or 0.0) * 0.85
                role_scores[role] = max(role_scores.get(role, 0.0), score)
                role_evidence.setdefault(role, []).extend([f"{view_id}: {item}" for item in alt.get("evidence", [])])

            for block in board.get("functional_blocks", []) or []:
                block_type = block.get("block_type", "unknown")
                block_counts[block_type] = block_counts.get(block_type, 0) + 1

            marking = view.get("marking_analysis") or {}
            connector_labels.update(marking.get("connector_labels", []) or [])
            pinout_evidence.extend((board.get("machine_context") or {}).get("pinout_evidence", []) or [])
            connection = view.get("machine_connection_map") or {}
            for connector_map in connection.get("connector_maps", []) or []:
                next_map = dict(connector_map)
                next_map["view_id"] = view_id
                connection_maps.append(next_map)

            for candidate in (board.get("reuse_and_splice") or {}).get("candidate_regions", []) or []:
                next_candidate = dict(candidate)
                next_candidate["view_id"] = view_id
                candidate_regions.append(next_candidate)

            for cls, count in (view.get("detection_summary", {}).get("components_by_type") or {}).items():
                component_counts[cls] = component_counts.get(cls, 0) + int(count or 0)

        best_role = max(role_scores, key=role_scores.get) if role_scores else "unknown_board"
        best_conf = role_scores.get(best_role, 0.0)
        view_bonus = min(0.14, 0.04 * max(0, len(views) - 1))
        marking_bonus = 0.08 if pinout_evidence or connector_labels else 0.0
        fused_conf = min(0.95, best_conf + view_bonus + marking_bonus)
        candidate_regions.sort(key=lambda item: float(item.get("confidence", 0.0) or 0.0), reverse=True)

        return {
            "mode": "multi_image_evidence_fusion",
            "board_identity": {
                "primary_type": best_role,
                "confidence": round(fused_conf, 3),
                "evidence": role_evidence.get(best_role, [])[:12],
                "alternatives": [
                    {"type": role, "confidence": round(score, 3), "evidence": role_evidence.get(role, [])[:6]}
                    for role, score in sorted(role_scores.items(), key=lambda item: item[1], reverse=True)
                    if role != best_role
                ][:4],
            },
            "functional_block_votes": dict(sorted(block_counts.items())),
            "machine_context": {
                "connector_label_evidence": sorted(connector_labels),
                "pinout_evidence": pinout_evidence[:20],
                "connector_maps": connection_maps[:20],
                "integration_notes": [
                    "Use front/back/crop fusion as evidence aggregation, not geometric registration.",
                    "Calibrate scale and align views before mechanical splice planning.",
                    "Prioritize labels and pinout evidence that appear in multiple views or closeups.",
                ],
            },
            "reuse_and_splice": {
                "candidate_regions": candidate_regions[:12],
                "warnings": [
                    "candidate crop coordinates are per-view pixels",
                    "front/back geometry is not yet registered into one metric coordinate frame",
                ],
            },
            "observed_inventory": {"component_counts": dict(sorted(component_counts.items()))},
            "salvage_opportunities": self.salvage_engine.evaluate(views),
            "confidence": round(fused_conf, 3),
        }

    def _multi_view_summary(self, fused: Dict[str, Any], views: List[Dict[str, Any]]) -> str:
        identity = fused.get("board_identity", {})
        labels = fused.get("machine_context", {}).get("connector_label_evidence", [])
        return (
            f"Fused {len(views)} board view(s). Likely role: "
            f"{identity.get('primary_type', 'unknown_board')} at "
            f"{float(identity.get('confidence', 0.0) or 0.0):.2f} confidence. "
            f"Connector/label evidence: {', '.join(labels[:8]) if labels else 'none'}."
        )

    def _compare_with_golden_image(
        self,
        image: np.ndarray,
        reference_image: np.ndarray | None,
    ) -> Dict[str, Any]:
        if reference_image is None:
            return self._empty_golden_aoi()
        try:
            return self.golden_inspector.compare(reference_image, image)
        except Exception as e:
            logger.warning(f"Golden image AOI comparison failed: {e}")
            return self._empty_golden_aoi(str(e))

    def _compare_with_reference_topology(
        self,
        visual_topology: Dict[str, Any] | None,
        reference_topology: Dict[str, Any] | None,
    ) -> Dict[str, Any]:
        if not reference_topology:
            return self._empty_topology_aoi()
        try:
            result = self.topology_diff.compare(reference_topology, visual_topology or {})
            if result.get("status") == "PASS":
                result["notes"] = [
                    "Reference topology classes match observed visual connectivity clusters.",
                    "Use with image caveats for hidden/bottom-side/bus routing.",
                ]
            else:
                result["notes"] = [
                    "Visual-to-reference topology mismatch detected.",
                    "Use with caution for production release decisions.",
                ]
            result["mode"] = "reference_topology_aoi"
            return result
        except Exception as e:
            logger.warning(f"Reference topology AOI comparison failed: {e}")
            return self._empty_topology_aoi(str(e))

    def _analyze_visual_topology(
        self,
        image: np.ndarray,
        detections: List[Dict[str, Any]],
        detection_summary: Dict[str, Any],
    ) -> Dict[str, Any]:
        try:
            image_bgr, scaled_detections, resize_scale = self._prepare_opencv_analysis_inputs(
                image,
                detections,
                max_dim=1600,
            )
            coordinate_scale = 1.0 / resize_scale if resize_scale > 0 else 1.0
            trace_result = self.trace_analyzer.analyze_traces(image_bgr, scaled_detections)
            traces = trace_result.get("traces") or []
            connections = trace_result.get("connections") or []
            issues = trace_result.get("issues") or []
            scale_mm_per_px = trace_result.get("scale_mm_per_px")
            if isinstance(scale_mm_per_px, (int, float, np.integer, np.floating)):
                scale_mm_per_px = float(scale_mm_per_px) * resize_scale
            component_count = int(detection_summary.get("total_components", len(detections)) or 0)
            connection_density = len(connections) / max(component_count, 1)
            learned_ratio = self._learned_detection_ratio(detection_summary)
            confidence = min(
                0.6,
                0.15
                + 0.35 * min(connection_density, 1.0)
                + 0.2 * learned_ratio
            )
            if detection_summary.get("review_required"):
                confidence *= 0.75

            return {
                "mode": "image_only_visual_estimate",
                "trace_count": int(trace_result.get("trace_count", len(traces)) or 0),
                "connection_count": int(trace_result.get("connection_count", len(connections)) or 0),
                "scale_mm_per_px": self._json_safe(scale_mm_per_px),
                "analysis_resize_scale": round(float(resize_scale), 4),
                "confidence": round(float(confidence), 3),
                "uncertainty": self._confidence_band(float(confidence)),
                "component_instances": [
                    {
                        "instance_id": str(det.get("topology_id")),
                        "class_name": self._normalize_class_name(det.get("class_name")),
                    }
                    for det in scaled_detections
                ],
                "traces": [self._serialize_trace(trace, coordinate_scale=coordinate_scale) for trace in traces[:50]],
                "connections": [self._serialize_connection(conn) for conn in connections[:50]],
                "issues": self._json_safe(issues[:20]),
                "limitations": [
                    "single-image trace extraction is a visual estimate, not a verified netlist",
                    "hidden, internal, bottom-side, and solder-mask-covered traces may be missed",
                    "use Gerber/KiCad/netlist input for high-confidence circuit topology",
                ],
            }
        except Exception as e:
            logger.warning(f"Visual topology analysis failed: {e}")
            return self._empty_visual_topology(str(e))

    def _assess_aoi_readiness(
        self,
        detection_summary: Dict[str, Any],
        visual_topology: Dict[str, Any],
        defect_inspection: Dict[str, Any] | None = None,
        reference_aoi: Dict[str, Any] | None = None,
        topology_aoi: Dict[str, Any] | None = None,
        scan_quality: Dict[str, Any] | None = None,
        golden_aoi: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        total = int(detection_summary.get("total_components", 0) or 0)
        learned_ratio = self._learned_detection_ratio(detection_summary)
        semantic = float(detection_summary.get("average_semantic_confidence", 0.0) or 0.0)
        topology_conf = float(visual_topology.get("confidence", 0.0) or 0.0)
        scan_score = 1.0
        scan_reason = "not_tracked"
        if isinstance(scan_quality, dict):
            scan_score = float(scan_quality.get("score", 1.0) or 0.0)
            scan_reason = str(scan_quality.get("reason", "tracked"))
        defect_count = int((defect_inspection or {}).get("defect_count", 0) or 0)
        reference_status = (reference_aoi or {}).get("status")
        reference_delta = int((reference_aoi or {}).get("component_delta", 0) or 0)
        topology_status = (topology_aoi or {}).get("status")
        topology_delta = int((topology_aoi or {}).get("topology_delta", 0) or 0)
        golden_status = (golden_aoi or {}).get("status")
        golden_defect_count = int((golden_aoi or {}).get("defect_count", 0) or 0)
        golden_max_severity = max(
            (
                float(defect.get("severity", 0.0) or 0.0)
                for defect in ((golden_aoi or {}).get("defects") or [])
                if isinstance(defect, dict)
            ),
            default=0.0,
        )
        review_penalty = 0.2 if detection_summary.get("review_required") else 0.0
        scan_penalty = 0.20 * min(1.0, max(0.0, 0.55 - scan_score) / 0.55)
        golden_penalty = 0.25 * min(1.0, golden_defect_count / 6.0) + 0.20 * golden_max_severity
        score = max(
            0.0,
            min(
                1.0,
                (
                    0.35 * learned_ratio
                    + 0.35 * semantic
                    + 0.2 * topology_conf
                    + 0.1 * min(total / 10.0, 1.0)
                    - review_penalty
                )
                + (0.15 if reference_status == "PASS" else 0.0)
                + (0.2 if topology_status == "PASS" else 0.0)
                + (0.15 if golden_status == "PASS" else 0.0)
                - (0.05 * min(reference_delta, 8) if reference_status == "FAIL" else 0.0)
                - (0.10 * min(topology_delta, 8) if topology_status == "FAIL" else 0.0)
                - (golden_penalty if golden_status == "FAIL" else 0.0)
                - scan_penalty,
            ),
        )
        if score >= 0.75:
            readiness = "pilot_ready"
        elif score >= 0.5:
            readiness = "prototype_ready"
        else:
            readiness = "research_preview"
        if scan_score < 0.30:
            readiness = "research_preview"
        elif scan_score < 0.55 and readiness == "pilot_ready":
            readiness = "prototype_ready"
        if golden_status == "FAIL" and readiness == "pilot_ready":
            readiness = "prototype_ready"

        blockers = [
            "calibrated camera/lighting fixture and focus checks",
            "labeled defect dataset from the target production line",
            "model/license review for any sourced checkpoints before redistribution",
        ]
        if reference_status is None:
            blockers.append("supply reference_counts or reference image for production AOI comparison")
        elif reference_status == "FAIL":
            blockers.insert(0, "reference AOI detected mismatches vs expected counts")
        if topology_status is None:
            blockers.append("supply reference_topology for topology-level AOI comparison")
        elif topology_status == "FAIL":
            blockers.insert(0, "topology AOI detected connectivity mismatches vs reference")
        if golden_status is None:
            blockers.append("supply reference_image/golden board for visual golden AOI comparison")
        elif golden_status == "FAIL":
            blockers.insert(0, f"golden image AOI found {golden_defect_count} changed region(s)")
        if topology_conf < 0.5:
            blockers.insert(0, "image-only topology confidence is below production threshold")
        if detection_summary.get("review_required"):
            blockers.insert(0, "some detections rely on heuristic supplements and need human review")
        if scan_score < 0.55:
            blockers.insert(0, f"scan quality is below production threshold ({scan_score:.2f}, {scan_reason})")

        return {
            "readiness": readiness,
            "score": round(float(score), 3),
            "learned_detection_ratio": round(float(learned_ratio), 3),
            "semantic_confidence": round(float(semantic), 3),
            "topology_confidence": round(float(topology_conf), 3),
            "scan_quality": {"score": round(float(scan_score), 3), "reason": scan_reason},
            "current_capabilities": [
                "component localization and coarse class identification",
                "candidate trace/connection extraction from visible copper geometry",
                "candidate visual defect detection for burns, solder bridges, corrosion, and broken traces",
                "explicit confidence, provenance, and review-required metadata",
            ],
            "defect_candidate_count": defect_count,
            "reference_component_delta": reference_delta,
            "golden_status": golden_status or "unavailable",
            "golden_defect_count": golden_defect_count,
            "topology_status": topology_status or "unavailable",
            "topology_delta": topology_delta,
            "blockers": blockers,
        }

    def _empty_reference_aoi(self, reason: str = "") -> Dict[str, Any]:
        return {
            "status": "unavailable",
            "reference_counts": {},
            "current_counts": {},
            "missing": [],
            "extra": [],
            "matched": [],
            "component_delta": 0,
            "mode": "reference_component_count_aoi",
            "summary": "Reference AOI comparison not run.",
            "notes": [
                reason,
            ] if reason else ["Reference AOI comparison not run."],
        }

    def _empty_topology_aoi(self, reason: str = "") -> Dict[str, Any]:
        return {
            "status": "unavailable",
            "mode": "reference_topology_aoi",
            "reference_signatures": [],
            "observed_signatures": [],
            "matched_clusters": 0,
            "topology_delta": 0,
            "missing": [],
            "extra": [],
            "reference_stats": {"net_count": 0, "component_count": 0, "isolated_count": 0},
            "observed_stats": {"net_count": 0, "component_count": 0, "isolated_count": 0},
            "summary": "Topology AOI comparison not run.",
            "notes": [
                reason,
            ] if reason else ["Topology AOI comparison not run."],
        }

    def _empty_golden_aoi(self, reason: str = "") -> Dict[str, Any]:
        return {
            "status": "unavailable",
            "mode": "golden_image_diff",
            "defect_count": 0,
            "defects": [],
            "summary": "Golden image comparison not run.",
            "notes": [reason] if reason else ["Golden image comparison not run."],
        }

    def _detect_defect_candidates(
        self,
        image: np.ndarray,
        detections: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        try:
            image_bgr, scaled_detections, resize_scale = self._prepare_opencv_analysis_inputs(
                image,
                detections,
                max_dim=1800,
            )
            coordinate_scale = 1.0 / resize_scale if resize_scale > 0 else 1.0
            defects = self.defect_detector.detect_defects(
                image_bgr,
                component_detections=scaled_detections,
                confidence_threshold=0.65,
            )
            defects = sorted(defects, key=lambda d: d.severity, reverse=True)
            max_severity = max((float(d.severity) for d in defects), default=0.0)
            return {
                "mode": "candidate_visual_defect_inspection",
                "defect_count": len(defects),
                "max_severity": round(max_severity, 3),
                "analysis_resize_scale": round(float(resize_scale), 4),
                "review_required": bool(defects),
                "defects": [self._serialize_defect(defect, coordinate_scale=coordinate_scale) for defect in defects[:20]],
                "limitations": [
                    "classical defect checks are candidate flags until validated against a golden board",
                    "lighting, glare, solder mask color, and board finish can cause false positives",
                    "production defect detection requires labeled line-specific defect data",
                ],
            }
        except Exception as e:
            logger.warning(f"Defect candidate detection failed: {e}")
            return self._empty_defect_inspection(str(e))

    def _infer_board_understanding(
        self,
        image: np.ndarray,
        detections: List[Dict[str, Any]],
        detection_summary: Dict[str, Any],
        visual_topology: Dict[str, Any],
        defect_inspection: Dict[str, Any],
        marking_analysis: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        try:
            return self.board_inferencer.analyze(
                detections,
                detection_summary=detection_summary,
                visual_topology=visual_topology,
                defect_inspection=defect_inspection,
                marking_analysis=marking_analysis,
                image_shape=tuple(np.asarray(image).shape),
            )
        except Exception as e:
            logger.warning(f"Board function inference failed: {e}")
            return self._empty_board_understanding(str(e))

    def _resolve_markings(self, detections: List[Dict[str, Any]]) -> Dict[str, Any]:
        try:
            return self.marking_resolver.resolve_detections(detections)
        except Exception as e:
            logger.warning(f"Marking resolution failed: {e}")
            return self._empty_marking_analysis(str(e))

    def _map_machine_connections(
        self,
        detections: List[Dict[str, Any]],
        marking_analysis: Dict[str, Any],
        board_understanding: Dict[str, Any],
    ) -> Dict[str, Any]:
        try:
            return self.connection_mapper.map_connections(
                detections,
                marking_analysis=marking_analysis,
                board_understanding=board_understanding,
            )
        except Exception as e:
            logger.warning(f"Machine connection mapping failed: {e}")
            return self._empty_machine_connection_map(str(e))

    def _evaluate_salvage_opportunities(
        self,
        analysis: Dict[str, Any],
        market_context: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        try:
            return self.salvage_engine.evaluate(analysis, market_context=market_context)
        except Exception as e:
            logger.warning(f"Salvage opportunity evaluation failed: {e}")
            return self._empty_salvage_opportunities(str(e))

    def _learned_detection_ratio(self, detection_summary: Dict[str, Any]) -> float:
        breakdown = detection_summary.get("backend_breakdown") or {}
        total = float(detection_summary.get("total_components", 0) or 0)
        if total <= 0:
            return 0.0
        learned = sum(
            count for backend, count in breakdown.items()
            if str(backend).startswith("yolo")
        )
        return float(learned) / total

    def _confidence_band(self, confidence: float) -> str:
        if confidence >= 0.65:
            return "high"
        if confidence >= 0.4:
            return "medium"
        return "low"

    @staticmethod
    def _normalize_class_name(name: Any) -> str:
        return str(name or "unknown").strip().lower().replace(" ", "_").replace("-", "_")

    def _empty_visual_topology(self, reason: str = "") -> Dict[str, Any]:
        return {
            "mode": "image_only_visual_estimate",
            "trace_count": 0,
            "connection_count": 0,
            "confidence": 0.0,
            "component_instances": [],
            "uncertainty": "high",
            "traces": [],
            "connections": [],
            "issues": [],
            "limitations": [
                "visual topology unavailable for this scan",
                reason,
            ] if reason else ["visual topology unavailable for this scan"],
        }

    def _empty_defect_inspection(self, reason: str = "") -> Dict[str, Any]:
        return {
            "mode": "candidate_visual_defect_inspection",
            "defect_count": 0,
            "max_severity": 0.0,
            "review_required": False,
            "defects": [],
            "limitations": [
                "defect inspection unavailable for this scan",
                reason,
            ] if reason else ["defect inspection unavailable for this scan"],
        }

    def _empty_board_understanding(self, reason: str = "") -> Dict[str, Any]:
        return {
            "mode": "image_only_board_function_inference",
            "board_identity": {
                "primary_type": "unknown_board",
                "description": "Board role could not be inferred.",
                "confidence": 0.0,
                "evidence": [],
                "alternatives": [],
            },
            "functional_blocks": [],
            "machine_context": {"likely_roles": [], "integration_notes": []},
            "reuse_and_splice": {
                "candidate_regions": [],
                "board_spec_for_splicer": {},
                "warnings": [
                    reason,
                ] if reason else ["Board function inference not run."],
            },
            "observed_inventory": {"component_counts": {}, "recognized_component_count": 0},
            "confidence": 0.0,
            "limitations": [
                "board function inference unavailable for this scan",
                reason,
            ] if reason else ["board function inference unavailable for this scan"],
        }

    def _empty_marking_analysis(self, reason: str = "") -> Dict[str, Any]:
        return {
            "mode": "ocr_marking_resolution",
            "components": [],
            "connector_labels": [],
            "confidence": 0.0,
            "limitations": [
                "marking resolution unavailable for this scan",
                reason,
            ] if reason else ["marking resolution unavailable for this scan"],
        }

    def _empty_machine_connection_map(self, reason: str = "") -> Dict[str, Any]:
        return {
            "mode": "machine_connection_map",
            "connector_count": 0,
            "connector_maps": [],
            "interfaces": [],
            "pinout_evidence": [],
            "splice_plan": {
                "safest_entry_points": [],
                "required_measurements": [],
                "do_not_assume": [],
            },
            "confidence": 0.0,
            "limitations": [
                "machine connection mapping unavailable for this scan",
                reason,
            ] if reason else ["machine connection mapping unavailable for this scan"],
        }

    def _empty_salvage_opportunities(self, reason: str = "") -> Dict[str, Any]:
        return {
            "mode": "salvage_and_arbitrage_opportunity_engine",
            "asset_summary": {"capabilities": {}, "parts": {}, "connector_count": 0, "defect_count": 0, "evidence": []},
            "opportunities": [],
            "best_opportunity": None,
            "strategy": {"recommendation": "inventory_first", "reason": reason or "No opportunity evaluation available."},
            "confidence": 0.0,
            "limitations": [
                "salvage opportunity evaluation unavailable",
                reason,
            ] if reason else ["salvage opportunity evaluation unavailable"],
        }

    def _serialize_trace(self, trace: Any, coordinate_scale: float = 1.0) -> Dict[str, Any]:
        return {
            "trace_id": getattr(trace, "trace_id", "trace"),
            "start_point": self._scale_point(getattr(trace, "start_point", []) or [], coordinate_scale),
            "end_point": self._scale_point(getattr(trace, "end_point", []) or [], coordinate_scale),
            "width_px": float(getattr(trace, "width_px", 0.0) or 0.0) * coordinate_scale,
            "length_px": float(getattr(trace, "length_px", 0.0) or 0.0) * coordinate_scale,
            "width_mm": self._json_safe(getattr(trace, "width_mm", None)),
            "length_mm": self._json_safe(getattr(trace, "length_mm", None)),
            "current_capacity_a": self._json_safe(getattr(trace, "current_capacity_a", None)),
            "connected_components": [str(v) for v in (getattr(trace, "connected_components", []) or [])],
            "trace_type": getattr(trace, "trace_type", "signal"),
        }

    def _serialize_connection(self, connection: Any) -> Dict[str, Any]:
        return {
            "component1": getattr(connection, "component1", "unknown"),
            "component2": getattr(connection, "component2", "unknown"),
            "trace_id": getattr(connection, "trace_id", "trace"),
            "connection_type": getattr(connection, "connection_type", "visual"),
            "resistance_estimate_ohm": self._json_safe(getattr(connection, "resistance_estimate_ohm", None)),
            "verified": bool(getattr(connection, "verified", False)),
        }

    def _serialize_defect(self, defect: Any, coordinate_scale: float = 1.0) -> Dict[str, Any]:
        return {
            "defect_type": str(getattr(defect, "defect_type", "unknown")),
            "bbox": self._scale_bbox(getattr(defect, "bbox", []) or [], coordinate_scale),
            "confidence": float(getattr(defect, "confidence", 0.0) or 0.0),
            "severity": float(getattr(defect, "severity", 0.0) or 0.0),
            "component_id": getattr(defect, "component_id", None),
            "description": str(getattr(defect, "description", "")),
            "repair_action": str(getattr(defect, "repair_action", "")),
            "metadata": self._json_safe(getattr(defect, "metadata", {}) or {}),
        }

    def _as_uint8_image(self, image: np.ndarray) -> np.ndarray:
        img = np.asarray(image)
        if img.dtype == np.uint8:
            return img
        if img.max(initial=0.0) <= 1.0:
            return (np.clip(img, 0.0, 1.0) * 255).astype(np.uint8)
        return np.clip(img, 0, 255).astype(np.uint8)

    def _as_bgr_image(self, image: np.ndarray) -> np.ndarray:
        img = self._as_uint8_image(image)
        if img.ndim == 2:
            return np.stack([img, img, img], axis=-1)
        if img.ndim == 3 and img.shape[-1] == 4:
            img = img[..., :3]
        if img.ndim == 3 and img.shape[-1] == 3:
            return img[..., ::-1].copy()
        raise ValueError(f"Unsupported image shape for OpenCV analysis: {img.shape}")

    @staticmethod
    def _decode_image_file(image_path: str) -> np.ndarray:
        """Load image from disk with a PIL-first, OpenCV fallback path."""
        try:
            with Image.open(image_path) as pil_image:
                return np.array(pil_image.convert("RGB"))
        except Exception:
            pass

        try:
            import cv2

            img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
            if img is None:
                raise ValueError("OpenCV could not decode image")

            if img.ndim == 2:
                img = np.stack([img, img, img], axis=-1)
            elif img.ndim == 3 and img.shape[-1] == 3:
                img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            elif img.ndim == 3 and img.shape[-1] == 4:
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2RGB)
            else:
                raise ValueError(f"Unsupported image shape: {img.shape}")

            return img
        except Exception as exc:
            raise ValueError(f"Could not decode image from disk: {exc}") from exc

    def _prepare_opencv_analysis_inputs(
        self,
        image: np.ndarray,
        detections: List[Dict[str, Any]],
        max_dim: int,
    ) -> Tuple[np.ndarray, List[Dict[str, Any]], float]:
        img = self._as_bgr_image(image)
        img, _ = polish_for_opencv(img, input_is_bgr=True)
        height, width = img.shape[:2]
        largest = max(height, width)
        if largest <= max_dim:
            return img, detections, 1.0

        resize_scale = float(max_dim) / float(largest)
        target_size = (
            max(1, int(round(width * resize_scale))),
            max(1, int(round(height * resize_scale))),
        )
        resample = getattr(Image, "Resampling", Image).BILINEAR
        resized = np.asarray(Image.fromarray(img).resize(target_size, resample=resample))
        return resized, self._scale_detections(detections, resize_scale), resize_scale

    def _scale_detections(
        self,
        detections: List[Dict[str, Any]],
        scale: float,
    ) -> List[Dict[str, Any]]:
        scaled: List[Dict[str, Any]] = []
        for idx, detection in enumerate(detections):
            next_detection = dict(detection)
            if isinstance(detection.get("bbox"), (list, tuple)):
                next_detection["bbox"] = [float(v) * scale for v in detection["bbox"]]
            if isinstance(detection.get("center"), (list, tuple)):
                next_detection["center"] = [float(v) * scale for v in detection["center"][:2]]
            class_name = str(detection.get("class_name") or detection.get("label") or "component")
            next_detection["topology_id"] = f"cmp_{idx}_{self._normalize_class_name(class_name)}"
            scaled.append(next_detection)
        return scaled

    def _scale_point(self, values: Any, scale: float) -> List[int]:
        if not isinstance(values, (list, tuple)) or len(values) < 2:
            return []
        return [int(round(float(v) * scale)) for v in values[:2]]

    def _scale_bbox(self, values: Any, scale: float) -> List[int]:
        if not isinstance(values, (list, tuple)) or len(values) < 4:
            return []
        return [int(round(float(v) * scale)) for v in values[:4]]

    def _json_safe(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {str(k): self._json_safe(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._json_safe(v) for v in value]
        if isinstance(value, np.integer):
            return int(value)
        if isinstance(value, np.floating):
            return float(value)
        if isinstance(value, np.ndarray):
            return self._json_safe(value.tolist())
        return value
    
    def analyze_from_file(self, image_path: str) -> Dict[str, Any]:
        """Analyze PCB from image file."""
        try:
            image_np = self._decode_image_file(image_path)
            return self.analyze_pcb(image_np)
            
        except Exception as e:
            logger.error(f"Error loading image from {image_path}: {e}")
            return {
                "error": f"Could not load image: {str(e)}",
                "detection_summary": {"total_components": 0},
                "functionality_analysis": {"components": [], "capabilities": []},
                "certainty_ledger": self.certainty_builder.empty(str(e)),
                "project_recommendations": []
            }
    
    def get_analysis_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a human-readable summary of analysis results."""
        detection_summary = results.get("detection_summary", {})
        functionality_data = results.get("functionality_analysis", {})
        recommendations = results.get("project_recommendations", [])
        visual_topology = results.get("visual_topology", {})
        marking_analysis = results.get("marking_analysis", {})
        board_understanding = results.get("board_understanding", {})
        machine_connection_map = results.get("machine_connection_map", {})
        salvage_opportunities = results.get("salvage_opportunities", {})
        aoi_inspection = results.get("aoi_inspection", {})
        reference_aoi = results.get("reference_aoi", {})
        golden_aoi = results.get("golden_aoi", {})
        topology_aoi = results.get("topology_aoi", {})
        certainty_ledger = results.get("certainty_ledger", {})
        
        total_components = detection_summary.get("total_components", 0)
        components_by_type = detection_summary.get("components_by_type", {})
        project_potential = functionality_data.get("project_potential", "none")
        
        # Generate summary text
        summary_text = f"Found {total_components} components on this PCB. "
        
        if components_by_type:
            component_list = [f"{count} {comp_type}" for comp_type, count in components_by_type.items()]
            summary_text += f"Components include: {', '.join(component_list)}. "

        if detection_summary.get("review_required"):
            summary_text += "These are candidate detections and class labels should be reviewed against the photo. "

        if visual_topology:
            trace_count = visual_topology.get("trace_count", 0)
            connection_count = visual_topology.get("connection_count", 0)
            topo_conf = visual_topology.get("confidence", 0.0)
            summary_text += (
                f"Visible topology estimate: {trace_count} trace regions and "
                f"{connection_count} candidate connections at {topo_conf:.2f} confidence. "
            )

        if board_understanding:
            identity = board_understanding.get("board_identity", {})
            board_type = identity.get("primary_type", "unknown_board")
            board_conf = identity.get("confidence", board_understanding.get("confidence", 0.0))
            block_count = len(board_understanding.get("functional_blocks", []) or [])
            summary_text += (
                f"Likely board role: {board_type} at {float(board_conf or 0.0):.2f} confidence "
                f"with {block_count} functional block candidate(s). "
            )

        if marking_analysis:
            resolved_count = len(marking_analysis.get("components", []) or [])
            if resolved_count:
                summary_text += f"OCR/marking lookup resolved evidence on {resolved_count} component(s). "

        if machine_connection_map:
            connector_count = machine_connection_map.get("connector_count", 0)
            conn_conf = machine_connection_map.get("confidence", 0.0)
            summary_text += f"Machine connection map: {connector_count} connector candidate(s) at {float(conn_conf or 0.0):.2f} confidence. "

        if salvage_opportunities:
            best = salvage_opportunities.get("best_opportunity") or {}
            if best:
                summary_text += f"Best salvage/build opportunity: {best.get('name')} ({best.get('type')}). "

        if reference_aoi:
            ref_status = reference_aoi.get("status", "unavailable")
            ref_delta = reference_aoi.get("component_delta", 0)
            if ref_status == "PASS":
                summary_text += "Reference AOI match: PASS. "
            elif ref_status == "FAIL":
                summary_text += f"Reference AOI match: FAIL with {ref_delta} component mismatches. "
            else:
                summary_text += "Reference AOI not executed. "

        if topology_aoi:
            topo_status = topology_aoi.get("status", "unavailable")
            topo_delta = topology_aoi.get("topology_delta", 0)
            if topo_status == "PASS":
                summary_text += "Topology AOI match: PASS. "
            elif topo_status == "FAIL":
                summary_text += f"Topology AOI match: FAIL with {topo_delta} signature mismatches. "
            else:
                summary_text += "Topology AOI not executed. "

        if golden_aoi:
            golden_status = golden_aoi.get("status", "unavailable")
            golden_count = golden_aoi.get("defect_count", 0)
            if golden_status == "PASS":
                summary_text += "Golden image AOI: PASS. "
            elif golden_status == "FAIL":
                summary_text += f"Golden image AOI: FAIL with {golden_count} changed region(s). "
            else:
                summary_text += "Golden image AOI not executed. "

        if aoi_inspection:
            summary_text += f"AOI readiness: {aoi_inspection.get('readiness', 'unknown')}. "

        if certainty_ledger:
            overall = certainty_ledger.get("overall", {})
            certainty_level = overall.get("level", "unknown")
            certainty_score = float(overall.get("score", 0.0) or 0.0)
            missing_count = len(certainty_ledger.get("missing_evidence", []) or [])
            summary_text += (
                f"Evidence certainty: {certainty_level} at {certainty_score:.2f} "
                f"with {missing_count} missing evidence item(s). "
            )
        
        if project_potential != "none":
            summary_text += f"Project potential: {project_potential}. "
        
        if recommendations:
            top_recommendation = recommendations[0]
            summary_text += f"Top recommendation: {top_recommendation['name']} ({top_recommendation['difficulty']} level)."
        else:
            summary_text += "No specific project recommendations available."
        
        return {
            "summary_text": summary_text,
            "total_components": total_components,
            "project_potential": project_potential,
            "visual_topology": {
                "trace_count": visual_topology.get("trace_count", 0),
                "connection_count": visual_topology.get("connection_count", 0),
                "confidence": visual_topology.get("confidence", 0.0),
                "uncertainty": visual_topology.get("uncertainty", "high"),
            },
            "board_understanding": {
                "primary_type": board_understanding.get("board_identity", {}).get("primary_type", "unknown_board"),
                "confidence": board_understanding.get("confidence", 0.0),
                "functional_blocks": board_understanding.get("functional_blocks", []),
                "machine_context": board_understanding.get("machine_context", {}),
                "reuse_and_splice": board_understanding.get("reuse_and_splice", {}),
            },
            "marking_analysis": {
                "confidence": marking_analysis.get("confidence", 0.0),
                "resolved_component_count": len(marking_analysis.get("components", []) or []),
                "connector_labels": marking_analysis.get("connector_labels", []),
                "components": marking_analysis.get("components", []),
            },
            "machine_connection_map": machine_connection_map,
            "salvage_opportunities": {
                "confidence": salvage_opportunities.get("confidence", 0.0),
                "best_opportunity": salvage_opportunities.get("best_opportunity"),
                "strategy": salvage_opportunities.get("strategy", {}),
                "opportunities": salvage_opportunities.get("opportunities", []),
                "asset_summary": salvage_opportunities.get("asset_summary", {}),
            },
            "aoi_readiness": aoi_inspection.get("readiness"),
            "certainty_ledger": {
                "overall": certainty_ledger.get("overall", {}),
                "counts": certainty_ledger.get("counts", {}),
                "missing_evidence": certainty_ledger.get("missing_evidence", []),
                "next_actions": certainty_ledger.get("next_actions", []),
                "training_queue": certainty_ledger.get("training_queue", {}),
                "top_items": (certainty_ledger.get("items", []) or [])[:12],
            },
            "top_recommendation": recommendations[0] if recommendations else None,
            "reference_aoi": {
                "status": reference_aoi.get("status"),
                "component_delta": reference_aoi.get("component_delta", 0),
                "missing": reference_aoi.get("missing", []),
                "extra": reference_aoi.get("extra", []),
            },
            "golden_aoi": {
                "status": golden_aoi.get("status"),
                "defect_count": golden_aoi.get("defect_count", 0),
                "defects": golden_aoi.get("defects", []),
            },
            "topology_aoi": {
                "status": topology_aoi.get("status"),
                "topology_delta": topology_aoi.get("topology_delta", 0),
                "missing": topology_aoi.get("missing", []),
                "extra": topology_aoi.get("extra", []),
            },
            "component_breakdown": components_by_type,
        }
    
    def generate_demo_data(self) -> Dict[str, Any]:
        """Generate demo data for testing and presentation."""
        return {
            "detection_summary": {
                "total_components": 47,
                "components_by_type": {
                    "ic_chip": 8,
                    "capacitor": 12,
                    "resistor": 27
                },
                "average_confidence": 0.85,
                "detection_quality": "high"
            },
            "functionality_analysis": {
                "components": [
                    {
                        "id": "ic_chip_1",
                        "type": "ic_chip",
                        "capabilities": ["arduino_projects", "iot_devices"],
                        "reuse_value": "high",
                        "difficulty": "beginner"
                    }
                ],
                "capabilities": ["arduino_projects", "iot_devices", "power_filtering"],
                "component_counts": {"ic_chip": 8, "capacitor": 12, "resistor": 27},
                "total_components": 47,
                "project_potential": "excellent"
            },
            "project_recommendations": [
                {
                    "project_id": "weather_station",
                    "name": "Arduino Weather Station",
                    "description": "Monitor temperature, humidity, and pressure",
                    "difficulty": "beginner",
                    "time_estimate": "2-4 hours",
                    "score": 0.8,
                    "components_available": ["microcontroller"],
                    "components_needed": ["microcontroller", "sensor", "display"],
                    "instructions": "Connect sensors to Arduino, upload code, display readings"
                }
            ],
            "analysis_metadata": {
                "total_processing_time": "1.8 seconds",
                "detection_quality": "high",
                "project_potential": "excellent"
            }
        } 
