"""Production AOI certainty gate.

This layer is deliberately stricter than the normal scan certainty ledger. It
answers a narrower question: can this inspection result be used as a production
release decision, or must the operator capture more evidence, rework, or hold?
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List


class ProductionAOICertaintyGate:
    """Convert scan, reference, and defect evidence into an auditable AOI gate."""

    DEFAULT_PROFILE = {
        "min_capture_score": 0.72,
        "min_learned_detection_ratio": 0.85,
        "min_semantic_confidence": 0.7,
        "min_topology_confidence": 0.55,
        "min_ledger_score": 0.78,
        "max_release_defect_severity": 0.25,
        "min_release_score": 0.86,
        "min_sampling_score": 0.78,
        "require_component_reference": True,
        "require_golden_reference": True,
        "require_topology_reference": True,
        "require_calibration": True,
    }

    def evaluate(
        self,
        *,
        detection_summary: Dict[str, Any] | None = None,
        visual_topology: Dict[str, Any] | None = None,
        defect_inspection: Dict[str, Any] | None = None,
        reference_aoi: Dict[str, Any] | None = None,
        topology_aoi: Dict[str, Any] | None = None,
        golden_aoi: Dict[str, Any] | None = None,
        aoi_inspection: Dict[str, Any] | None = None,
        certainty_ledger: Dict[str, Any] | None = None,
        profile: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        detection_summary = detection_summary or {}
        visual_topology = visual_topology or {}
        defect_inspection = defect_inspection or {}
        reference_aoi = reference_aoi or {}
        topology_aoi = topology_aoi or {}
        golden_aoi = golden_aoi or {}
        aoi_inspection = aoi_inspection or {}
        certainty_ledger = certainty_ledger or {}
        profile = self._profile(profile)

        gates = [
            self._capture_gate(aoi_inspection, profile),
            self._detector_gate(detection_summary, profile),
            self._component_reference_gate(reference_aoi, profile),
            self._golden_gate(golden_aoi, profile),
            self._topology_gate(topology_aoi, visual_topology, profile),
            self._defect_gate(defect_inspection, golden_aoi, profile),
            self._ledger_gate(certainty_ledger, profile),
            self._calibration_gate(profile),
        ]
        score = self._weighted_score(gates)
        disposition = self._disposition(gates, score, profile)
        blockers = self._blockers(gates)
        release_authorized = disposition == "release"
        level = self._level(score, release_authorized, blockers, profile)

        return {
            "mode": "production_aoi_certainty_gate",
            "disposition": disposition,
            "release_authorized": release_authorized,
            "certainty_score": round(score, 3),
            "certainty_level": level,
            "false_accept_risk": self._risk_band(1.0 - score, release_authorized),
            "false_reject_risk": self._false_reject_risk(gates),
            "gates": gates,
            "blockers": blockers,
            "critical_findings": self._critical_findings(reference_aoi, topology_aoi, golden_aoi, defect_inspection),
            "required_evidence": self._required_evidence(gates),
            "release_conditions": self._release_conditions(profile),
            "operator_checklist": self._operator_checklist(gates),
            "audit_packet": self._audit_packet(profile, reference_aoi, topology_aoi, golden_aoi, certainty_ledger),
            "profile": {
                key: value
                for key, value in profile.items()
                if key
                in {
                    "line_id",
                    "station_id",
                    "fixture_id",
                    "calibration_id",
                    "operator_id",
                    "lot_id",
                    "board_serial",
                    "board_revision",
                    "min_capture_score",
                    "min_learned_detection_ratio",
                    "min_semantic_confidence",
                    "min_topology_confidence",
                    "min_ledger_score",
                    "min_release_score",
                    "min_sampling_score",
                }
            },
            "claim_boundary": (
                "Production AOI release requires calibrated capture, known-good references, "
                "line-specific defect review, and traceable operator/audit data. Without those, "
                "the result can guide review but must not be treated as production release."
            ),
        }

    def _profile(self, value: Dict[str, Any] | None) -> Dict[str, Any]:
        profile = dict(self.DEFAULT_PROFILE)
        if isinstance(value, dict):
            profile.update(value)
        for key in [
            "min_capture_score",
            "min_learned_detection_ratio",
            "min_semantic_confidence",
            "min_topology_confidence",
            "min_ledger_score",
            "max_release_defect_severity",
            "min_release_score",
            "min_sampling_score",
        ]:
            profile[key] = self._float(profile.get(key), self.DEFAULT_PROFILE[key])
        for key in [
            "require_component_reference",
            "require_golden_reference",
            "require_topology_reference",
            "require_calibration",
        ]:
            profile[key] = bool(profile.get(key))
        return profile

    def _capture_gate(self, aoi: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
        quality = aoi.get("scan_quality") if isinstance(aoi.get("scan_quality"), dict) else {}
        score = self._float(quality.get("score"), 0.0)
        minimum = float(profile["min_capture_score"])
        status = "pass" if score >= minimum else "review" if score >= 0.55 else "fail"
        return self._gate(
            "capture_quality",
            status,
            score,
            1.15,
            f"scan quality {score:.2f}; minimum {minimum:.2f}",
            "retake with calibrated fixture, fixed focus, low glare, and full-board coverage",
        )

    def _detector_gate(self, summary: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
        total = int(summary.get("total_components", 0) or 0)
        breakdown = summary.get("backend_breakdown") if isinstance(summary.get("backend_breakdown"), dict) else {}
        learned = sum(int(count or 0) for backend, count in breakdown.items() if str(backend).startswith("yolo"))
        learned_ratio = learned / max(total, 1)
        semantic = self._float(summary.get("average_semantic_confidence"), 0.0)
        review_required = bool(summary.get("review_required"))
        score = max(0.0, min(1.0, 0.55 * learned_ratio + 0.45 * semantic - (0.18 if review_required else 0.0)))
        status = (
            "pass"
            if (
                total > 0
                and learned_ratio >= float(profile["min_learned_detection_ratio"])
                and semantic >= float(profile["min_semantic_confidence"])
                and not review_required
            )
            else "review"
            if total > 0
            else "fail"
        )
        return self._gate(
            "detector_domain",
            status,
            score,
            1.0,
            f"{learned_ratio:.2f} learned detections, semantic confidence {semantic:.2f}, total {total}",
            "review low-confidence detections or collect target-line labels before release",
        )

    def _component_reference_gate(self, reference: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
        status = str(reference.get("status") or "unavailable")
        if status == "PASS":
            return self._gate("component_reference", "pass", 1.0, 1.25, "component counts match reference", "")
        if status == "FAIL":
            delta = int(reference.get("component_delta", 0) or 0)
            return self._gate("component_reference", "fail", max(0.0, 1.0 - 0.15 * delta), 1.35, f"{delta} component mismatch(es)", "rework missing/extra component mismatch and rerun")
        required = bool(profile["require_component_reference"])
        return self._gate("component_reference", "missing" if required else "review", 0.0 if required else 0.45, 1.2, "component reference not supplied", "supply BOM/count reference or known-good reference count")

    def _golden_gate(self, golden: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
        status = str(golden.get("status") or "unavailable")
        if status == "PASS":
            return self._gate("golden_visual_reference", "pass", 1.0, 1.45, "golden image diff passed", "")
        if status == "FAIL":
            defects = int(golden.get("defect_count", 0) or 0)
            max_severity = max(
                (self._float(defect.get("severity"), 0.0) for defect in golden.get("defects", []) if isinstance(defect, dict)),
                default=0.0,
            )
            score = max(0.0, 1.0 - min(1.0, 0.2 * defects + 0.55 * max_severity))
            return self._gate("golden_visual_reference", "fail", score, 1.55, f"{defects} changed region(s), max severity {max_severity:.2f}", "confirm changed regions under magnification, rework, and rerun golden comparison")
        required = bool(profile["require_golden_reference"])
        return self._gate("golden_visual_reference", "missing" if required else "review", 0.0 if required else 0.45, 1.35, "golden image not supplied", "capture known-good golden board under the same fixture and lighting")

    def _topology_gate(self, topology_aoi: Dict[str, Any], visual_topology: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
        status = str(topology_aoi.get("status") or "unavailable")
        topo_conf = self._float(visual_topology.get("confidence"), 0.0)
        if status == "PASS":
            score = max(0.75, min(1.0, 0.6 + 0.4 * topo_conf))
            gate_status = "pass" if topo_conf >= float(profile["min_topology_confidence"]) else "review"
            return self._gate("topology_reference", gate_status, score, 1.15, f"topology reference pass, visual confidence {topo_conf:.2f}", "raise visual topology confidence with better imaging or continuity checks")
        if status == "FAIL":
            delta = int(topology_aoi.get("topology_delta", 0) or 0)
            return self._gate("topology_reference", "fail", max(0.0, 1.0 - 0.16 * delta), 1.25, f"{delta} topology mismatch(es)", "hold board for continuity/netlist review")
        required = bool(profile["require_topology_reference"])
        return self._gate("topology_reference", "missing" if required else "review", 0.0 if required else min(0.5, topo_conf), 1.05, "reference topology not supplied", "supply KiCad/netlist/Gerber topology or continuity reference")

    def _defect_gate(self, defect: Dict[str, Any], golden: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
        defect_count = int(defect.get("defect_count", 0) or 0)
        max_severity = max(
            self._float(defect.get("max_severity"), 0.0),
            max((self._float(item.get("severity"), 0.0) for item in defect.get("defects", []) if isinstance(item, dict)), default=0.0),
            max((self._float(item.get("severity"), 0.0) for item in golden.get("defects", []) if isinstance(item, dict)), default=0.0),
        )
        limit = float(profile["max_release_defect_severity"])
        if defect_count == 0 and int(golden.get("defect_count", 0) or 0) == 0:
            return self._gate("defect_severity", "pass", 1.0, 1.2, "no defect candidates above gate threshold", "")
        status = "fail" if max_severity > limit or str(golden.get("status")) == "FAIL" else "review"
        score = max(0.0, 1.0 - min(1.0, 0.12 * defect_count + 0.75 * max_severity))
        return self._gate("defect_severity", status, score, 1.25, f"{defect_count} candidate defect(s), max severity {max_severity:.2f}", "confirm candidate defects under magnification and record rework outcome")

    def _ledger_gate(self, ledger: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
        overall = ledger.get("overall") if isinstance(ledger.get("overall"), dict) else {}
        score = self._float(overall.get("score"), 0.0)
        minimum = float(profile["min_ledger_score"])
        status = "pass" if score >= minimum else "review" if score >= 0.6 else "fail"
        return self._gate("evidence_ledger", status, score, 0.9, f"evidence ledger {score:.2f}; minimum {minimum:.2f}", "resolve missing evidence and low-certainty claims")

    def _calibration_gate(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        if not profile.get("require_calibration"):
            return self._gate("calibration_traceability", "pass", 0.8, 0.85, "calibration not required by profile", "")
        missing = [
            label
            for key, label in [
                ("fixture_id", "fixture id"),
                ("calibration_id", "calibration id"),
                ("station_id", "station id"),
            ]
            if not str(profile.get(key) or "").strip()
        ]
        if not missing:
            return self._gate("calibration_traceability", "pass", 1.0, 0.95, "fixture, calibration, and station are traceable", "")
        return self._gate("calibration_traceability", "missing", 0.0, 0.95, f"missing {', '.join(missing)}", "record fixture_id, calibration_id, and station_id for the AOI station")

    def _gate(self, gate_id: str, status: str, score: float, weight: float, evidence: str, remediation: str) -> Dict[str, Any]:
        return {
            "gate_id": gate_id,
            "status": status,
            "score": round(max(0.0, min(1.0, float(score or 0.0))), 3),
            "weight": round(float(weight), 3),
            "evidence": evidence,
            "remediation": remediation,
        }

    def _weighted_score(self, gates: List[Dict[str, Any]]) -> float:
        total = sum(float(gate.get("weight", 1.0) or 1.0) for gate in gates)
        if total <= 0:
            return 0.0
        score = sum(float(gate.get("score", 0.0) or 0.0) * float(gate.get("weight", 1.0) or 1.0) for gate in gates) / total
        hard_penalty = 0.16 * len([gate for gate in gates if gate.get("status") == "fail"])
        missing_penalty = 0.1 * len([gate for gate in gates if gate.get("status") == "missing"])
        return max(0.0, min(1.0, score - hard_penalty - missing_penalty))

    def _disposition(self, gates: List[Dict[str, Any]], score: float, profile: Dict[str, Any]) -> str:
        failed = {str(gate.get("gate_id")) for gate in gates if gate.get("status") == "fail"}
        missing = {str(gate.get("gate_id")) for gate in gates if gate.get("status") == "missing"}
        review = {str(gate.get("gate_id")) for gate in gates if gate.get("status") == "review"}
        if failed & {"golden_visual_reference", "component_reference", "topology_reference", "defect_severity"}:
            return "rework"
        if "capture_quality" in failed:
            return "hold_for_capture"
        if missing & {"component_reference", "golden_visual_reference", "topology_reference"}:
            return "hold_for_reference"
        if "calibration_traceability" in missing:
            return "hold_for_calibration"
        if failed or review:
            return "operator_review"
        release_threshold = float(profile.get("min_release_score", self.DEFAULT_PROFILE["min_release_score"]))
        sampling_threshold = float(profile.get("min_sampling_score", self.DEFAULT_PROFILE["min_sampling_score"]))
        if score >= release_threshold:
            return "release"
        return "release_with_sampling" if score >= sampling_threshold else "operator_review"

    def _level(self, score: float, release_authorized: bool, blockers: List[str], profile: Dict[str, Any]) -> str:
        if release_authorized and score >= 0.9:
            return "production_certified"
        if release_authorized:
            return "production_release"
        if score >= float(profile.get("min_sampling_score", self.DEFAULT_PROFILE["min_sampling_score"])) and not blockers:
            return "sampling_ready"
        if score >= 0.6:
            return "review_ready"
        return "not_production_ready"

    def _blockers(self, gates: List[Dict[str, Any]]) -> List[str]:
        return [
            f"{gate.get('gate_id')}: {gate.get('evidence')}"
            for gate in gates
            if gate.get("status") in {"fail", "missing"}
        ][:12]

    def _required_evidence(self, gates: List[Dict[str, Any]]) -> List[str]:
        return [
            str(gate.get("remediation"))
            for gate in gates
            if gate.get("status") in {"fail", "missing", "review"} and str(gate.get("remediation") or "").strip()
        ][:12]

    def _critical_findings(
        self,
        reference: Dict[str, Any],
        topology: Dict[str, Any],
        golden: Dict[str, Any],
        defect: Dict[str, Any],
    ) -> List[str]:
        findings = []
        if reference.get("status") == "FAIL":
            findings.append(f"component reference mismatch: {reference.get('component_delta', 0)} delta")
        if topology.get("status") == "FAIL":
            findings.append(f"topology reference mismatch: {topology.get('topology_delta', 0)} delta")
        if golden.get("status") == "FAIL":
            findings.append(f"golden visual mismatch: {golden.get('defect_count', 0)} changed region(s)")
        for item in (defect.get("defects") or [])[:5]:
            if isinstance(item, dict) and self._float(item.get("severity"), 0.0) >= 0.7:
                findings.append(f"high-severity defect candidate: {item.get('defect_type', 'defect')}")
        return findings[:8]

    def _release_conditions(self, profile: Dict[str, Any]) -> List[str]:
        return [
            "same fixture, camera pose, lighting, focus, and board orientation as the golden reference",
            "component reference count/BOM matches the inspected revision",
            "golden visual diff has no release-blocking changed regions",
            "topology/netlist reference passes or has documented waived differences",
            "operator records lot, board serial, fixture, calibration, and station identifiers",
            f"evidence ledger score is at least {float(profile['min_ledger_score']):.2f}",
            f"production release score is at least {float(profile['min_release_score']):.2f}",
        ]

    def _operator_checklist(self, gates: List[Dict[str, Any]]) -> List[str]:
        items = [
            "verify board revision and orientation before comparing to references",
            "confirm the image is sharp, evenly lit, and fully covers the board",
            "review every failed, missing, or review gate before release",
            "record microscope confirmation for any defect candidate",
        ]
        for gate in gates:
            if gate.get("status") in {"fail", "missing", "review"} and gate.get("remediation"):
                items.append(str(gate["remediation"]))
        return self._dedupe(items)[:12]

    def _audit_packet(
        self,
        profile: Dict[str, Any],
        reference: Dict[str, Any],
        topology: Dict[str, Any],
        golden: Dict[str, Any],
        ledger: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {
            "required_fields": [
                "lot_id",
                "board_serial",
                "board_revision",
                "station_id",
                "fixture_id",
                "calibration_id",
                "operator_id",
                "software_version",
                "model_version",
                "reference_revision",
                "golden_image_id",
                "inspection_timestamp",
            ],
            "present_fields": sorted(
                key
                for key in [
                    "lot_id",
                    "board_serial",
                    "board_revision",
                    "station_id",
                    "fixture_id",
                    "calibration_id",
                    "operator_id",
                    "software_version",
                    "model_version",
                    "reference_revision",
                    "golden_image_id",
                ]
                if str(profile.get(key) or "").strip()
            ),
            "reference_statuses": {
                "component": reference.get("status", "unavailable"),
                "topology": topology.get("status", "unavailable"),
                "golden": golden.get("status", "unavailable"),
            },
            "certainty": (ledger.get("overall") or {}) if isinstance(ledger.get("overall"), dict) else {},
        }

    def _false_reject_risk(self, gates: List[Dict[str, Any]]) -> str:
        missing_or_review = len([gate for gate in gates if gate.get("status") in {"missing", "review"}])
        failed = len([gate for gate in gates if gate.get("status") == "fail"])
        if failed:
            return "medium"
        if missing_or_review >= 3:
            return "high"
        if missing_or_review:
            return "medium"
        return "low"

    def _risk_band(self, risk: float, release_authorized: bool) -> str:
        if release_authorized and risk <= 0.1:
            return "low"
        if risk <= 0.22:
            return "medium"
        return "high"

    @staticmethod
    def _float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _dedupe(items: Iterable[str]) -> List[str]:
        kept = []
        seen = set()
        for item in items:
            text = str(item or "").strip()
            key = text.lower()
            if not text or key in seen:
                continue
            seen.add(key)
            kept.append(text)
        return kept
