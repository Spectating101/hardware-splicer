"""Grounded board dossier built from session evidence."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

from src.intelligence.board_evidence_graph import BoardEvidenceGraphBuilder


class BoardDossierBuilder:
    """Summarize a board session into an operator-readable dossier."""

    def build(self, session: Dict[str, Any]) -> Dict[str, Any]:
        graph = BoardEvidenceGraphBuilder().build(session)
        analysis = self._latest_analysis(session)
        production_aoi = analysis.get("production_aoi") if isinstance(analysis.get("production_aoi"), dict) else {}
        repair_guide = session.get("repair_guide") if isinstance(session.get("repair_guide"), dict) else {}
        salvage_plan = session.get("salvage_splice_plan") if isinstance(session.get("salvage_splice_plan"), dict) else {}
        detections = analysis.get("detections") if isinstance(analysis.get("detections"), list) else []
        tasks = session.get("evidence_tasks") if isinstance(session.get("evidence_tasks"), list) else []
        open_tasks = [task for task in tasks if isinstance(task, dict) and str(task.get("status") or "open") == "open"]
        outcomes = session.get("outcomes") if isinstance(session.get("outcomes"), list) else []

        confirmed_findings = self._confirmed_findings(session)
        known = self._known_items(session, analysis, repair_guide, salvage_plan, graph, confirmed_findings)
        weak = self._weak_items(graph, production_aoi)
        next_actions = self._next_actions(graph, open_tasks, production_aoi)
        status = self._dossier_status(production_aoi, graph, open_tasks)

        return {
            "mode": "board_dossier",
            "session_id": session.get("session_id"),
            "title": session.get("title") or session.get("device_hint") or "Board dossier",
            "route": session.get("route"),
            "status": status,
            "executive_summary": self._executive_summary(session, production_aoi, graph, open_tasks),
            "identity": self._identity(session, analysis, repair_guide),
            "aoi": self._aoi_summary(production_aoi),
            "components": self._component_summary(detections, analysis),
            "repair_reuse": self._repair_reuse_summary(repair_guide, salvage_plan, confirmed_findings),
            "evidence": {
                "graph_summary": graph.get("summary", {}),
                "grounded_claims": graph.get("grounded_claims", [])[:8],
                "weak_claims": graph.get("weak_claims", [])[:8],
                "next_grounding_actions": graph.get("next_grounding_actions", [])[:8],
            },
            "known": known,
            "uncertain": weak,
            "next_actions": next_actions,
            "outcomes": outcomes[-5:],
            "open_tasks": open_tasks[:10],
            "confirmed_findings": confirmed_findings,
            "graph": {
                "summary": graph.get("summary", {}),
                "nodes": graph.get("nodes", [])[:80],
                "edges": graph.get("edges", [])[:120],
            },
            "claim_boundary": (
                "This dossier only summarizes evidence already attached to the board session. "
                "Weak claims require additional capture, measurement, review, reference, or outcome evidence."
            ),
        }

    def _known_items(
        self,
        session: Dict[str, Any],
        analysis: Dict[str, Any],
        repair_guide: Dict[str, Any],
        salvage_plan: Dict[str, Any],
        graph: Dict[str, Any],
        confirmed_findings: List[Dict[str, Any]],
    ) -> List[str]:
        items = []
        if session.get("device_hint"):
            items.append(f"Device hint: {session.get('device_hint')}")
        summary = analysis.get("detection_summary") if isinstance(analysis.get("detection_summary"), dict) else {}
        if summary.get("total_components") is not None:
            items.append(f"Detected {summary.get('total_components')} component candidate(s)")
        identity = ((analysis.get("board_understanding") or {}).get("board_identity") or {}) if isinstance(analysis.get("board_understanding"), dict) else {}
        if identity.get("primary_type"):
            items.append(f"Board role candidate: {str(identity.get('primary_type')).replace('_', ' ')}")
        family = repair_guide.get("device_family") if isinstance(repair_guide.get("device_family"), dict) else {}
        if family.get("name") or family.get("id"):
            items.append(f"Repair lane: {family.get('name') or family.get('id')}")
        target = salvage_plan.get("target") if isinstance(salvage_plan.get("target"), dict) else {}
        if target.get("recommended_build") or salvage_plan.get("target_build"):
            items.append(f"Reuse target: {target.get('recommended_build') or salvage_plan.get('target_build')}")
        for claim in graph.get("grounded_claims", [])[:4]:
            if isinstance(claim, dict) and claim.get("claim"):
                items.append(str(claim["claim"]))
        for finding in confirmed_findings[:5]:
            label = finding.get("label")
            evidence = finding.get("evidence")
            if label and evidence:
                items.append(f"{label}: {evidence}")
        return self._dedupe(items)[:10]

    def _weak_items(self, graph: Dict[str, Any], production_aoi: Dict[str, Any]) -> List[str]:
        items = []
        for blocker in production_aoi.get("blockers") or []:
            items.append(str(blocker))
        for claim in graph.get("weak_claims", [])[:8]:
            if isinstance(claim, dict) and claim.get("claim"):
                items.append(str(claim["claim"]))
        return self._dedupe(items)[:10]

    def _next_actions(self, graph: Dict[str, Any], open_tasks: List[Dict[str, Any]], production_aoi: Dict[str, Any]) -> List[str]:
        actions = [str(item) for item in graph.get("next_grounding_actions", []) if str(item).strip()]
        for evidence in production_aoi.get("required_evidence") or []:
            actions.append(str(evidence))
        for task in open_tasks[:6]:
            actions.append(str(task.get("prompt") or "Resolve open evidence task"))
        return self._dedupe(actions)[:10]

    def _identity(self, session: Dict[str, Any], analysis: Dict[str, Any], repair_guide: Dict[str, Any]) -> Dict[str, Any]:
        board = analysis.get("board_understanding") if isinstance(analysis.get("board_understanding"), dict) else {}
        identity = board.get("board_identity") if isinstance(board.get("board_identity"), dict) else {}
        family = repair_guide.get("device_family") if isinstance(repair_guide.get("device_family"), dict) else {}
        return {
            "device_hint": session.get("device_hint"),
            "board_role": identity.get("primary_type"),
            "board_confidence": identity.get("confidence", board.get("confidence")),
            "repair_family": family.get("name") or family.get("id"),
            "repair_confidence": family.get("confidence"),
        }

    def _aoi_summary(self, production_aoi: Dict[str, Any]) -> Dict[str, Any]:
        if not production_aoi:
            return {"available": False, "disposition": None, "release_authorized": False, "blockers": []}
        return {
            "available": True,
            "disposition": production_aoi.get("disposition"),
            "release_authorized": production_aoi.get("release_authorized", False),
            "certainty_score": production_aoi.get("certainty_score", 0.0),
            "certainty_level": production_aoi.get("certainty_level"),
            "blockers": production_aoi.get("blockers") or [],
            "gates": production_aoi.get("gates") or [],
        }

    def _component_summary(self, detections: List[Any], analysis: Dict[str, Any]) -> Dict[str, Any]:
        summary = analysis.get("detection_summary") if isinstance(analysis.get("detection_summary"), dict) else {}
        counts: Dict[str, int] = {}
        for detection in detections:
            if not isinstance(detection, dict):
                continue
            label = str(detection.get("class_name") or detection.get("label") or "component")
            counts[label] = counts.get(label, 0) + 1
        if not counts and isinstance(summary.get("components_by_type"), dict):
            counts = {str(key): int(value or 0) for key, value in summary["components_by_type"].items()}
        return {
            "total": int(summary.get("total_components", len(detections)) or 0),
            "counts": counts,
            "review_required": bool(summary.get("review_required", False)),
            "top_detections": [
                {
                    "label": item.get("class_name") or item.get("label"),
                    "confidence": item.get("confidence"),
                    "part_number": item.get("part_number"),
                    "ocr_text": item.get("ocr_text"),
                }
                for item in detections[:12]
                if isinstance(item, dict)
            ],
        }

    def _repair_reuse_summary(
        self,
        repair_guide: Dict[str, Any],
        salvage_plan: Dict[str, Any],
        confirmed_findings: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        fault = (repair_guide.get("fault_candidates") or [{}])[0] if isinstance(repair_guide.get("fault_candidates"), list) else {}
        target = salvage_plan.get("target") if isinstance(salvage_plan.get("target"), dict) else {}
        confirmed_fault = self._confirmed_fault_label(confirmed_findings)
        return {
            "top_fault": confirmed_fault or ((fault.get("name") or fault.get("fault_id")) if isinstance(fault, dict) else None),
            "top_fault_source": "confirmed_evidence" if confirmed_fault else "repair_guide_candidate",
            "repair_safety": (repair_guide.get("safety_profile") or {}).get("risk_level") if isinstance(repair_guide.get("safety_profile"), dict) else None,
            "reuse_verdict": salvage_plan.get("verdict"),
            "reuse_target": target.get("recommended_build") or salvage_plan.get("target_build"),
            "reusable_blocks": salvage_plan.get("reusable_blocks") or [],
        }

    def _dossier_status(self, production_aoi: Dict[str, Any], graph: Dict[str, Any], open_tasks: List[Dict[str, Any]]) -> str:
        if production_aoi.get("release_authorized"):
            return "release_ready"
        disposition = str(production_aoi.get("disposition") or "")
        if disposition in {"rework", "hold_for_capture", "hold_for_reference", "hold_for_calibration"}:
            return disposition
        if graph.get("summary", {}).get("weak_claim_count", 0) or open_tasks:
            return "needs_evidence"
        return "review_ready"

    def _executive_summary(
        self,
        session: Dict[str, Any],
        production_aoi: Dict[str, Any],
        graph: Dict[str, Any],
        open_tasks: List[Dict[str, Any]],
    ) -> str:
        title = session.get("title") or session.get("device_hint") or "This board"
        graph_summary = graph.get("summary", {})
        parts = [
            f"{title} has {graph_summary.get('grounded_claim_count', 0)} grounded claim(s) and {graph_summary.get('weak_claim_count', 0)} weak claim(s).",
        ]
        if production_aoi:
            disposition = str(production_aoi.get("disposition") or "unknown").replace("_", " ")
            parts.append(f"Production AOI disposition is {disposition}.")
        if open_tasks:
            parts.append(f"{len(open_tasks)} evidence task(s) remain open.")
        return " ".join(parts)

    def _latest_analysis(self, session: Dict[str, Any]) -> Dict[str, Any]:
        analyses = session.get("analyses") if isinstance(session.get("analyses"), list) else []
        if not analyses:
            return {}
        latest = analyses[-1] if isinstance(analyses[-1], dict) else {}
        return latest.get("results") if isinstance(latest.get("results"), dict) else {}

    def _confirmed_findings(self, session: Dict[str, Any]) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []

        evidence = session.get("evidence") if isinstance(session.get("evidence"), dict) else {}
        for measurement in evidence.get("measurements") or []:
            if not isinstance(measurement, dict):
                continue
            value = measurement.get("value")
            unit = measurement.get("unit")
            target = measurement.get("target") or measurement.get("type") or "measurement"
            if value is not None:
                findings.append(
                    {
                        "type": "measurement",
                        "label": "Measurement",
                        "evidence": f"{target} = {value}{(' ' + str(unit)) if unit else ''}",
                        "source": measurement.get("measurement_id"),
                    }
                )
            if measurement.get("notes"):
                findings.append(
                    {
                        "type": "measurement_note",
                        "label": "Measurement note",
                        "evidence": str(measurement.get("notes")),
                        "source": measurement.get("measurement_id"),
                    }
                )

        for task in session.get("evidence_tasks") or []:
            if not isinstance(task, dict) or str(task.get("status") or "") != "resolved":
                continue
            review = task.get("review") if isinstance(task.get("review"), dict) else {}
            notes = str(review.get("notes") or "").strip()
            if notes:
                findings.append(
                    {
                        "type": "resolved_evidence",
                        "label": "Resolved evidence",
                        "evidence": notes,
                        "source": task.get("task_id"),
                    }
                )

        for review in session.get("reviews") or []:
            if not isinstance(review, dict):
                continue
            payload = review.get("payload") if isinstance(review.get("payload"), dict) else {}
            notes = str(payload.get("notes") or review.get("notes") or "").strip()
            if notes:
                findings.append(
                    {
                        "type": "operator_review",
                        "label": "Operator review",
                        "evidence": notes,
                        "source": review.get("review_id"),
                    }
                )

        for outcome in session.get("outcomes") or []:
            if not isinstance(outcome, dict):
                continue
            decision = str(outcome.get("decision") or outcome.get("aoi_actual_status") or "").strip()
            notes = str(outcome.get("notes") or "").strip()
            if decision:
                evidence_text = decision if not notes else f"{decision}; {notes}"
                findings.append(
                    {
                        "type": "outcome",
                        "label": "Recorded outcome",
                        "evidence": evidence_text,
                        "source": outcome.get("outcome_id"),
                    }
                )

        return self._dedupe_findings(findings)[:12]

    def _confirmed_fault_label(self, findings: List[Dict[str, Any]]) -> str | None:
        text = " ".join(str(item.get("evidence") or "") for item in findings).lower()
        connector_terms = ("connector", "harness", "wire", "crimp", "joint")
        solder_terms = ("cracked solder", "reflow", "reflowed", "solder joint", "continuity")
        if any(term in text for term in connector_terms) and any(term in text for term in solder_terms):
            return "Connector, solder joint, or harness intermittency"
        if "battery" in text and ("replaced" in text or "cell" in text):
            return "Battery pack or cell failure"
        if "charging" in text and ("5." in text or "voltage" in text):
            return "Charging input or dock path"
        return None

    @staticmethod
    def _dedupe_findings(findings: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        kept: List[Dict[str, Any]] = []
        seen = set()
        for finding in findings:
            evidence = str(finding.get("evidence") or "").strip()
            key = (str(finding.get("type") or ""), evidence.lower())
            if evidence and key not in seen:
                seen.add(key)
                kept.append(finding)
        return kept

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
