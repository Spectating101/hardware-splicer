"""Grounded evidence graph for board-in-hand sessions."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List


class BoardEvidenceGraphBuilder:
    """Convert a board session into claims, evidence nodes, and support edges."""

    def build(self, session: Dict[str, Any]) -> Dict[str, Any]:
        analysis = self._latest_analysis(session)
        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []
        claims: List[Dict[str, Any]] = []
        seen_nodes: set[str] = set()

        def add_node(node_id: str, kind: str, label: str, **extra: Any) -> str:
            if node_id in seen_nodes:
                return node_id
            seen_nodes.add(node_id)
            nodes.append({"id": node_id, "kind": kind, "label": label, **extra})
            return node_id

        def add_edge(source: str, target: str, relation: str, **extra: Any) -> None:
            if not source or not target:
                return
            edges.append({"source": source, "target": target, "relation": relation, **extra})

        session_id = str(session.get("session_id") or "session")
        session_node = add_node(
            f"session:{session_id}",
            "session",
            str(session.get("title") or session_id),
            route=session.get("route"),
            status=session.get("status"),
        )

        capture_nodes = self._capture_nodes(session, add_node, add_edge, session_node)
        measurement_nodes = self._measurement_nodes(session, add_node, add_edge, session_node)
        review_nodes = self._review_nodes(session, add_node, add_edge, session_node)
        outcome_nodes = self._outcome_nodes(session, add_node, add_edge, session_node)
        task_nodes = self._task_nodes(session, add_node, add_edge, session_node)

        support_pool = capture_nodes + measurement_nodes + review_nodes + outcome_nodes
        if analysis:
            analysis_node = add_node(f"analysis:{session_id}:latest", "analysis", "latest analysis")
            add_edge(session_node, analysis_node, "has_analysis")
            self._analysis_claims(
                session_id,
                analysis,
                claims,
                add_node,
                add_edge,
                analysis_node,
                support_pool,
                task_nodes,
            )
        self._workflow_claims(
            session_id,
            session,
            claims,
            support_pool,
            task_nodes,
            outcome_nodes,
        )

        for claim in claims:
            claim_node = add_node(
                claim["claim_id"],
                "claim",
                claim["claim"],
                certainty=claim.get("certainty"),
                score=claim.get("score"),
                status=claim.get("grounding_status"),
            )
            add_edge(session_node, claim_node, "asserts")
            for evidence_id in claim.get("supporting_evidence") or []:
                add_edge(evidence_id, claim_node, "supports")
            for missing_id in claim.get("missing_evidence") or []:
                add_edge(claim_node, missing_id, "needs")

        grounded = [claim for claim in claims if claim.get("grounding_status") == "grounded"]
        weak = [claim for claim in claims if claim.get("grounding_status") != "grounded"]
        return {
            "mode": "board_evidence_graph",
            "session_id": session_id,
            "summary": {
                "node_count": len(nodes),
                "edge_count": len(edges),
                "claim_count": len(claims),
                "grounded_claim_count": len(grounded),
                "weak_claim_count": len(weak),
                "source_count": len([node for node in nodes if node.get("kind") in {"capture", "measurement", "review", "outcome", "reference"}]),
            },
            "nodes": nodes,
            "edges": edges,
            "claims": claims,
            "grounded_claims": grounded[:12],
            "weak_claims": weak[:12],
            "next_grounding_actions": self._next_grounding_actions(weak, session),
            "claim_boundary": (
                "This graph shows evidence available inside the board session. "
                "Claims without capture, measurement, review, reference, or outcome support remain weak."
            ),
        }

    def _analysis_claims(
        self,
        session_id: str,
        analysis: Dict[str, Any],
        claims: List[Dict[str, Any]],
        add_node: Any,
        add_edge: Any,
        analysis_node: str,
        support_pool: List[str],
        task_nodes: List[str],
    ) -> None:
        summary = analysis.get("detection_summary") if isinstance(analysis.get("detection_summary"), dict) else {}
        detections = analysis.get("detections") if isinstance(analysis.get("detections"), list) else []
        if summary or detections:
            total = int(summary.get("total_components", len(detections)) or 0)
            self._add_claim(
                claims,
                f"claim:{session_id}:component-count",
                f"{total} component candidate(s) were detected",
                score=self._float(summary.get("average_confidence"), summary.get("average_semantic_confidence", 0.5)),
                evidence=support_pool[:2],
                missing=task_nodes[:2],
                usable_for=["identification", "aoi", "training"],
            )
            for index, detection in enumerate(detections[:18], start=1):
                if not isinstance(detection, dict):
                    continue
                label = str(detection.get("class_name") or detection.get("label") or "component")
                det_node = add_node(
                    f"detection:{session_id}:{index}",
                    "component",
                    label,
                    confidence=detection.get("confidence"),
                    bbox=detection.get("bbox") or [],
                )
                add_edge(analysis_node, det_node, "detected")
                self._add_claim(
                    claims,
                    f"claim:{session_id}:detection:{index}",
                    f"Detected {label}",
                    score=self._float(detection.get("semantic_confidence"), detection.get("confidence", 0.0)),
                    evidence=[det_node] + support_pool[:1],
                    missing=task_nodes[:1],
                    usable_for=["identification", "training"],
                )

        board = analysis.get("board_understanding") if isinstance(analysis.get("board_understanding"), dict) else {}
        identity = board.get("board_identity") if isinstance(board.get("board_identity"), dict) else {}
        if identity:
            role = str(identity.get("primary_type") or "unknown board").replace("_", " ")
            self._add_claim(
                claims,
                f"claim:{session_id}:board-role",
                f"Board role appears to be {role}",
                score=self._float(identity.get("confidence"), board.get("confidence", 0.0)),
                evidence=support_pool[:2],
                missing=task_nodes[:3],
                usable_for=["repair", "salvage", "reuse"],
            )

        production_aoi = analysis.get("production_aoi") if isinstance(analysis.get("production_aoi"), dict) else {}
        if production_aoi:
            disposition = str(production_aoi.get("disposition") or "unknown").replace("_", " ")
            gate_nodes = []
            for gate in (production_aoi.get("gates") or [])[:12]:
                if not isinstance(gate, dict):
                    continue
                gate_node = add_node(
                    f"gate:{session_id}:{gate.get('gate_id')}",
                    "aoi_gate",
                    str(gate.get("gate_id") or "gate").replace("_", " "),
                    status=gate.get("status"),
                    score=gate.get("score"),
                    evidence=gate.get("evidence"),
                )
                add_edge(analysis_node, gate_node, "evaluates")
                gate_nodes.append(gate_node)
            self._add_claim(
                claims,
                f"claim:{session_id}:production-aoi",
                f"Production AOI disposition is {disposition}",
                score=self._float(production_aoi.get("certainty_score"), 0.0),
                evidence=gate_nodes + support_pool[:2],
                missing=task_nodes[:4],
                usable_for=["aoi", "production_gate"],
                force_weak=not bool(production_aoi.get("release_authorized")),
            )
            for index, blocker in enumerate(production_aoi.get("blockers") or [], start=1):
                self._add_claim(
                    claims,
                    f"claim:{session_id}:aoi-blocker:{index}",
                    str(blocker),
                    score=0.4,
                    evidence=gate_nodes,
                    missing=task_nodes[:4],
                    usable_for=["aoi", "production_gate"],
                    force_weak=True,
                )

        salvage_plan = analysis.get("salvage_splice_plan") if isinstance(analysis.get("salvage_splice_plan"), dict) else {}
        if salvage_plan:
            target = salvage_plan.get("target") if isinstance(salvage_plan.get("target"), dict) else {}
            build = target.get("recommended_build") or salvage_plan.get("target_build") or "reuse build"
            self._add_claim(
                claims,
                f"claim:{session_id}:reuse-target",
                f"Recommended reuse target: {build}",
                score=self._float(salvage_plan.get("confidence"), 0.5),
                evidence=support_pool[:3],
                missing=task_nodes[:4],
                usable_for=["reuse", "salvage", "build"],
            )

        ledger = analysis.get("certainty_ledger") if isinstance(analysis.get("certainty_ledger"), dict) else {}
        for index, item in enumerate((ledger.get("items") or [])[:12], start=1):
            if not isinstance(item, dict):
                continue
            self._add_claim(
                claims,
                f"claim:{session_id}:ledger:{index}",
                str(item.get("claim") or item.get("claim_type") or "evidence claim"),
                score=self._float(item.get("score"), 0.0),
                evidence=support_pool[:2],
                missing=task_nodes[:3],
                usable_for=item.get("usable_for") or ["training"],
                force_weak=str(item.get("certainty") or "") in {"unknown", "possible"},
            )

    def _workflow_claims(
        self,
        session_id: str,
        session: Dict[str, Any],
        claims: List[Dict[str, Any]],
        support_pool: List[str],
        task_nodes: List[str],
        outcome_nodes: List[str],
    ) -> None:
        guide = session.get("repair_guide") if isinstance(session.get("repair_guide"), dict) else {}
        family = guide.get("device_family") if isinstance(guide.get("device_family"), dict) else {}
        if family.get("name") or family.get("id"):
            self._add_claim(
                claims,
                f"claim:{session_id}:device-family",
                f"Device family: {family.get('name') or family.get('id')}",
                score=self._float(family.get("confidence"), 0.65),
                evidence=support_pool[:3],
                missing=task_nodes[:3],
                usable_for=["repair", "workflow"],
            )
        fault = (guide.get("fault_candidates") or [{}])[0] if isinstance(guide.get("fault_candidates"), list) else {}
        if isinstance(fault, dict) and (fault.get("name") or fault.get("fault_id")):
            self._add_claim(
                claims,
                f"claim:{session_id}:top-fault",
                f"Top fault candidate: {fault.get('name') or fault.get('fault_id')}",
                score=self._float(fault.get("confidence"), 0.55),
                evidence=support_pool[:3],
                missing=task_nodes[:4],
                usable_for=["repair", "diagnosis"],
            )

        splice = session.get("salvage_splice_plan") if isinstance(session.get("salvage_splice_plan"), dict) else {}
        if splice:
            target = splice.get("target") if isinstance(splice.get("target"), dict) else {}
            build = target.get("recommended_build") or splice.get("target_build") or "reuse build"
            self._add_claim(
                claims,
                f"claim:{session_id}:session-reuse-target",
                f"Reuse target: {build}",
                score=self._float(splice.get("confidence"), 0.55),
                evidence=support_pool[:3],
                missing=task_nodes[:4],
                usable_for=["reuse", "salvage", "build"],
            )

        open_tasks = [
            task for task in (session.get("evidence_tasks") or [])
            if isinstance(task, dict) and str(task.get("status") or "open") == "open"
        ]
        if open_tasks:
            self._add_claim(
                claims,
                f"claim:{session_id}:open-evidence",
                f"{len(open_tasks)} open evidence task(s) must be resolved before strong certainty",
                score=0.35,
                evidence=task_nodes[:6],
                missing=task_nodes[:6],
                usable_for=["review", "training", "certainty"],
                force_weak=True,
            )

        for index, outcome in enumerate((session.get("outcomes") or [])[:5], start=1):
            if not isinstance(outcome, dict):
                continue
            decision = str(outcome.get("decision") or outcome.get("aoi_actual_status") or "").strip()
            if not decision:
                continue
            self._add_claim(
                claims,
                f"claim:{session_id}:outcome:{index}",
                f"Outcome recorded: {decision}",
                score=0.88,
                evidence=outcome_nodes[index - 1:index],
                missing=[],
                usable_for=["value_proof", "calibration", "training"],
            )

    def _add_claim(
        self,
        claims: List[Dict[str, Any]],
        claim_id: str,
        claim: str,
        *,
        score: float,
        evidence: List[str],
        missing: List[str],
        usable_for: Iterable[str],
        force_weak: bool = False,
    ) -> None:
        support = [item for item in evidence if item]
        missing_evidence = [item for item in missing if item]
        status = "grounded" if support and score >= 0.72 and not force_weak else "needs_evidence"
        claims.append(
            {
                "claim_id": claim_id,
                "claim": claim,
                "score": round(max(0.0, min(1.0, score)), 3),
                "certainty": self._certainty(score, bool(support), force_weak),
                "grounding_status": status,
                "supporting_evidence": support[:8],
                "missing_evidence": missing_evidence[:6],
                "usable_for": list(usable_for),
            }
        )

    def _capture_nodes(self, session: Dict[str, Any], add_node: Any, add_edge: Any, session_node: str) -> List[str]:
        nodes = []
        evidence = session.get("evidence") if isinstance(session.get("evidence"), dict) else {}
        for capture in (evidence.get("captures") or [])[:20]:
            if not isinstance(capture, dict):
                continue
            capture_id = str(capture.get("capture_id") or f"capture_{len(nodes) + 1}")
            node = add_node(
                f"capture:{capture_id}",
                "capture",
                str(capture.get("kind") or capture.get("filename") or capture_id).replace("_", " "),
                filename=capture.get("filename"),
                notes=capture.get("notes"),
            )
            add_edge(session_node, node, "has_capture")
            nodes.append(node)
        return nodes

    def _measurement_nodes(self, session: Dict[str, Any], add_node: Any, add_edge: Any, session_node: str) -> List[str]:
        nodes = []
        evidence = session.get("evidence") if isinstance(session.get("evidence"), dict) else {}
        for measurement in (evidence.get("measurements") or [])[:20]:
            if not isinstance(measurement, dict):
                continue
            measurement_id = str(measurement.get("measurement_id") or f"measurement_{len(nodes) + 1}")
            label = f"{measurement.get('type') or 'measurement'} {measurement.get('target') or ''}".strip()
            node = add_node(
                f"measurement:{measurement_id}",
                "measurement",
                label,
                value=measurement.get("value"),
                unit=measurement.get("unit"),
                confidence=measurement.get("confidence"),
            )
            add_edge(session_node, node, "has_measurement")
            nodes.append(node)
        return nodes

    def _review_nodes(self, session: Dict[str, Any], add_node: Any, add_edge: Any, session_node: str) -> List[str]:
        nodes = []
        for review in (session.get("reviews") or [])[:30]:
            if not isinstance(review, dict):
                continue
            review_id = str(review.get("review_id") or f"review_{len(nodes) + 1}")
            node = add_node(
                f"review:{review_id}",
                "review",
                str(review.get("action") or "reviewed"),
                task_id=review.get("task_id"),
            )
            add_edge(session_node, node, "has_review")
            nodes.append(node)
        return nodes

    def _outcome_nodes(self, session: Dict[str, Any], add_node: Any, add_edge: Any, session_node: str) -> List[str]:
        nodes = []
        for outcome in (session.get("outcomes") or [])[:20]:
            if not isinstance(outcome, dict):
                continue
            outcome_id = str(outcome.get("outcome_id") or f"outcome_{len(nodes) + 1}")
            node = add_node(
                f"outcome:{outcome_id}",
                "outcome",
                str(outcome.get("decision") or outcome.get("aoi_actual_status") or "outcome"),
                aoi_actual_status=outcome.get("aoi_actual_status"),
                value_recovered_usd=outcome.get("value_recovered_usd"),
                time_saved_minutes=outcome.get("time_saved_minutes"),
            )
            add_edge(session_node, node, "has_outcome")
            nodes.append(node)
        return nodes

    def _task_nodes(self, session: Dict[str, Any], add_node: Any, add_edge: Any, session_node: str) -> List[str]:
        nodes = []
        for task in (session.get("evidence_tasks") or [])[:40]:
            if not isinstance(task, dict):
                continue
            task_id = str(task.get("task_id") or f"task_{len(nodes) + 1}")
            node = add_node(
                f"task:{task_id}",
                "evidence_task",
                str(task.get("prompt") or task_id)[:120],
                task_type=task.get("type"),
                status=task.get("status"),
                priority=task.get("priority"),
            )
            add_edge(session_node, node, "has_task")
            nodes.append(node)
        return nodes

    def _next_grounding_actions(self, weak_claims: List[Dict[str, Any]], session: Dict[str, Any]) -> List[str]:
        actions = []
        for claim in weak_claims[:8]:
            if claim.get("missing_evidence"):
                actions.append(f"Resolve evidence for: {claim.get('claim')}")
            elif not claim.get("supporting_evidence"):
                actions.append(f"Attach capture, measurement, or review support for: {claim.get('claim')}")
        if not actions and not (session.get("outcomes") or []):
            actions.append("Record an outcome after repair, reuse, or AOI review so future claims can be calibrated.")
        return self._dedupe(actions)[:8]

    def _latest_analysis(self, session: Dict[str, Any]) -> Dict[str, Any]:
        analyses = session.get("analyses") if isinstance(session.get("analyses"), list) else []
        if not analyses:
            return {}
        latest = analyses[-1] if isinstance(analyses[-1], dict) else {}
        return latest.get("results") if isinstance(latest.get("results"), dict) else {}

    def _certainty(self, score: float, has_support: bool, force_weak: bool) -> str:
        if force_weak or not has_support:
            return "weak"
        if score >= 0.86:
            return "strong"
        if score >= 0.72:
            return "supported"
        return "weak"

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
            if text and key not in seen:
                seen.add(key)
                kept.append(text)
        return kept
