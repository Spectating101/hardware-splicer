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
from src.vision.image_polisher import polish_for_opencv


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
        logger.info("CircuitAnalyzer initialized")
    
    def analyze_pcb(
        self,
        image: np.ndarray,
        backend: str | None = None,
        enable_ocr: bool | None = None,
        reference_counts: Dict[str, int] | None = None,
        reference_topology: Dict[str, Any] | None = None,
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
            
            # Step 2: Detect components
            detections = self.detector.detect_components(processed_image, backend=backend, enable_ocr=enable_ocr)
            
            # Step 3: Generate detection summary
            detection_summary = self.detector.get_detection_summary(detections)

            # Step 3.1: Optional golden/reference component count comparison
            reference_aoi = self._compare_with_reference(detections, reference_counts)
            
            # Step 4: Map to functional metadata
            functionality_data = self.mapper.map_detections_to_functionality(detections)
            
            # Step 5: Estimate visual topology from traces and component geometry
            visual_topology = self._analyze_visual_topology(image, detections, detection_summary)

            # Step 5.1: Optional topology AOI against reference netlist
            topology_aoi = self._compare_with_reference_topology(
                visual_topology,
                reference_topology,
            )

            # Step 6: Detect visual defect candidates
            defect_inspection = self._detect_defect_candidates(image, detections)

            # Step 7: Assess AOI production readiness for this scan
            aoi_inspection = self._assess_aoi_readiness(
                detection_summary,
                visual_topology,
                defect_inspection,
                reference_aoi,
                topology_aoi,
            )

            # Step 8: Generate project recommendations
            recommendations = self.mapper.generate_project_recommendations(functionality_data)
            
            # Step 9: Compile results
            results = {
                "detections": detections,
                "detection_summary": detection_summary,
                "functionality_analysis": functionality_data,
                "visual_topology": visual_topology,
                "topology_aoi": topology_aoi,
                "defect_inspection": defect_inspection,
                "reference_aoi": reference_aoi,
                "aoi_inspection": aoi_inspection,
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
                    "topology_aoi_status": topology_aoi.get("status", "unavailable"),
                    "topology_aoi_delta": topology_aoi.get("topology_delta", 0),
                    "aoi_readiness": aoi_inspection.get("readiness", "unknown"),
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
                "visual_topology": self._empty_visual_topology(str(e)),
                "defect_inspection": self._empty_defect_inspection(str(e)),
                "reference_aoi": self._empty_reference_aoi(str(e)),
                "topology_aoi": self._empty_topology_aoi(str(e)),
                "aoi_inspection": {"readiness": "unavailable", "score": 0.0, "blockers": [str(e)]},
                "project_recommendations": []
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
    ) -> Dict[str, Any]:
        total = int(detection_summary.get("total_components", 0) or 0)
        learned_ratio = self._learned_detection_ratio(detection_summary)
        semantic = float(detection_summary.get("average_semantic_confidence", 0.0) or 0.0)
        topology_conf = float(visual_topology.get("confidence", 0.0) or 0.0)
        defect_count = int((defect_inspection or {}).get("defect_count", 0) or 0)
        reference_status = (reference_aoi or {}).get("status")
        reference_delta = int((reference_aoi or {}).get("component_delta", 0) or 0)
        topology_status = (topology_aoi or {}).get("status")
        topology_delta = int((topology_aoi or {}).get("topology_delta", 0) or 0)
        review_penalty = 0.2 if detection_summary.get("review_required") else 0.0
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
                - (0.05 * min(reference_delta, 8) if reference_status == "FAIL" else 0.0)
                - (0.10 * min(topology_delta, 8) if topology_status == "FAIL" else 0.0),
            ),
        )
        if score >= 0.75:
            readiness = "pilot_ready"
        elif score >= 0.5:
            readiness = "prototype_ready"
        else:
            readiness = "research_preview"

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
        if topology_conf < 0.5:
            blockers.insert(0, "image-only topology confidence is below production threshold")
        if detection_summary.get("review_required"):
            blockers.insert(0, "some detections rely on heuristic supplements and need human review")

        return {
            "readiness": readiness,
            "score": round(float(score), 3),
            "learned_detection_ratio": round(float(learned_ratio), 3),
            "semantic_confidence": round(float(semantic), 3),
            "topology_confidence": round(float(topology_conf), 3),
            "current_capabilities": [
                "component localization and coarse class identification",
                "candidate trace/connection extraction from visible copper geometry",
                "candidate visual defect detection for burns, solder bridges, corrosion, and broken traces",
                "explicit confidence, provenance, and review-required metadata",
            ],
            "defect_candidate_count": defect_count,
            "reference_component_delta": reference_delta,
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
                "project_recommendations": []
            }
    
    def get_analysis_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a human-readable summary of analysis results."""
        detection_summary = results.get("detection_summary", {})
        functionality_data = results.get("functionality_analysis", {})
        recommendations = results.get("project_recommendations", [])
        visual_topology = results.get("visual_topology", {})
        aoi_inspection = results.get("aoi_inspection", {})
        reference_aoi = results.get("reference_aoi", {})
        topology_aoi = results.get("topology_aoi", {})
        
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

        if aoi_inspection:
            summary_text += f"AOI readiness: {aoi_inspection.get('readiness', 'unknown')}. "
        
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
            "aoi_readiness": aoi_inspection.get("readiness"),
            "top_recommendation": recommendations[0] if recommendations else None,
            "reference_aoi": {
                "status": reference_aoi.get("status"),
                "component_delta": reference_aoi.get("component_delta", 0),
                "missing": reference_aoi.get("missing", []),
                "extra": reference_aoi.get("extra", []),
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
