"""Persistent board-in-hand sessions, review queue, and training exports."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

try:
    import numpy as np
except Exception:  # pragma: no cover - optional at import time
    np = None


class BoardSessionStore:
    """Local JSON store for turning scans into reviewable board sessions."""

    def __init__(self, store_path: str | Path = "data/board_sessions/sessions.json"):
        self.store_path = Path(store_path)
        self.root_dir = self.store_path.parent
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.sessions: List[Dict[str, Any]] = []
        self._load()

    def create_session(
        self,
        payload: Dict[str, Any],
        *,
        user_id: str = "anonymous",
        commit: bool = True,
    ) -> Dict[str, Any]:
        now = self._now()
        analysis = self._analysis_from_payload(payload)
        summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
        symptoms = self._listify(payload.get("symptoms"))
        session_id = self._session_id(payload)
        title = self._title(payload, analysis)
        route = str(payload.get("route") or self._infer_route(payload, analysis))
        repair_guide = payload.get("repair_guide") if isinstance(payload.get("repair_guide"), dict) else {}
        tasks = self._dedupe_tasks(self._tasks_from_analysis(analysis) + self._tasks_from_repair_guide(repair_guide))
        tasks = self._trim_tasks(tasks)
        captures = self._listify_dict(payload.get("captures"))
        image_info = payload.get("image") if isinstance(payload.get("image"), dict) else None
        if image_info:
            captures.append(
                {
                    "capture_id": f"capture_{len(captures) + 1}",
                    "kind": str(image_info.get("kind") or "uploaded_photo"),
                    "filename": image_info.get("filename"),
                    "content_type": image_info.get("content_type"),
                    "size_bytes": image_info.get("size_bytes"),
                    "created_at": now,
                }
            )

        session = {
            "session_id": session_id,
            "title": title,
            "description": str(payload.get("description") or payload.get("text") or ""),
            "device_hint": str(payload.get("device_hint") or ""),
            "symptoms": symptoms,
            "route": route,
            "route_label": str(payload.get("route_label") or route.replace("_", " ")),
            "status": "open",
            "user_id": user_id,
            "created_at": now,
            "updated_at": now,
            "evidence": {
                "captures": captures,
                "measurements": [],
                "notes": self._listify(payload.get("notes")),
            },
            "analyses": [],
            "certainty": self._certainty_snapshot(analysis),
            "evidence_tasks": tasks,
            "reviews": [],
            "outcomes": [],
            "training_exports": [],
            "coverage": payload.get("coverage") if isinstance(payload.get("coverage"), dict) else {},
            "repair_guide": repair_guide,
            "case_file": payload.get("case_file") if isinstance(payload.get("case_file"), dict) else {},
            "metrics": self._session_metrics(tasks, analysis),
        }
        if analysis:
            session["analyses"].append(
                {
                    "analysis_id": f"analysis_{len(session['analyses']) + 1}",
                    "source": str(payload.get("source") or "session_intake"),
                    "created_at": now,
                    "summary": summary,
                    "results": self._json_safe(analysis),
                }
            )
        if commit:
            self.sessions.append(session)
            self._save()
        return session

    def attach_capture(
        self,
        session_id: str,
        capture: Dict[str, Any],
        *,
        commit: bool = True,
    ) -> Dict[str, Any]:
        session = self.get_session(session_id)
        if not session:
            return {"error": f"session not found: {session_id}"}
        captures = session.setdefault("evidence", {}).setdefault("captures", [])
        capture_record = {
            "capture_id": str(capture.get("capture_id") or f"capture_{len(captures) + 1}"),
            "kind": str(capture.get("kind") or "evidence"),
            "filename": capture.get("filename"),
            "path": capture.get("path"),
            "content_type": capture.get("content_type"),
            "size_bytes": capture.get("size_bytes"),
            "notes": capture.get("notes"),
            "created_at": self._now(),
        }
        captures.append(capture_record)
        resolved_task_types = {"capture"}
        kind_text = f"{capture_record.get('kind') or ''} {capture_record.get('notes') or ''} {capture_record.get('filename') or ''}".lower()
        if any(term in kind_text for term in ["reference", "golden", "netlist", "gerber", "kicad"]):
            resolved_task_types.add("reference")
        self._resolve_first_matching_task(
            session,
            task_types=resolved_task_types,
            resolution={
                "action": "captured",
                "notes": capture_record.get("notes") or f"Added {capture_record['kind']} evidence",
                "capture_id": capture_record["capture_id"],
            },
        )
        session["metrics"] = self._session_metrics(session.get("evidence_tasks") or [], self._latest_analysis(session))
        self._touch(session)
        if commit:
            self._save()
        return {"session": session, "capture": capture_record}

    def add_measurement(
        self,
        session_id: str,
        measurement: Dict[str, Any],
        *,
        commit: bool = True,
    ) -> Dict[str, Any]:
        session = self.get_session(session_id)
        if not session:
            return {"error": f"session not found: {session_id}"}
        record = {
            "measurement_id": str(measurement.get("measurement_id") or f"measurement_{len((session.get('evidence') or {}).get('measurements') or []) + 1}"),
            "type": str(measurement.get("type") or measurement.get("measurement_type") or "measurement"),
            "target": str(measurement.get("target") or ""),
            "value": measurement.get("value"),
            "unit": str(measurement.get("unit") or measurement.get("units") or ""),
            "notes": str(measurement.get("notes") or ""),
            "confidence": float(measurement.get("confidence", 1.0) or 1.0),
            "created_at": self._now(),
        }
        session.setdefault("evidence", {}).setdefault("measurements", []).append(record)
        self._resolve_first_matching_task(
            session,
            task_types={"measurement"},
            resolution={
                "action": "measured",
                "notes": f"{record['type']} {record['target']} = {record['value']} {record['unit']}".strip(),
                "measurement_id": record["measurement_id"],
            },
        )
        session["metrics"] = self._session_metrics(session.get("evidence_tasks") or [], self._latest_analysis(session))
        self._touch(session)
        if commit:
            self._save()
        return {"session": session, "measurement": record}

    def review_task(
        self,
        session_id: str,
        payload: Dict[str, Any],
        *,
        commit: bool = True,
    ) -> Dict[str, Any]:
        session = self.get_session(session_id)
        if not session:
            return {"error": f"session not found: {session_id}"}
        task_id = str(payload.get("task_id") or "")
        task = self._find_task(session, task_id)
        if not task:
            return {"error": f"task not found: {task_id}"}
        action = str(payload.get("action") or "reviewed")
        status = "resolved" if action in {"accepted", "corrected", "rejected", "captured", "measured", "reviewed"} else action
        task["status"] = status
        task["resolved_at"] = self._now()
        task["review"] = {
            "action": action,
            "corrected_label": payload.get("corrected_label"),
            "confidence": payload.get("confidence"),
            "notes": payload.get("notes"),
            "reviewer": payload.get("reviewer"),
        }
        review = {
            "review_id": f"review_{len(session.get('reviews') or []) + 1}",
            "task_id": task_id,
            "task_type": task.get("type"),
            "action": action,
            "payload": self._json_safe(payload),
            "created_at": self._now(),
        }
        session.setdefault("reviews", []).append(review)
        session["metrics"] = self._session_metrics(session.get("evidence_tasks") or [], self._latest_analysis(session))
        self._touch(session)
        if commit:
            self._save()
        return {"session": session, "task": task, "review": review}

    def record_outcome(
        self,
        session_id: str,
        payload: Dict[str, Any],
        *,
        commit: bool = True,
    ) -> Dict[str, Any]:
        session = self.get_session(session_id)
        if not session:
            return {"error": f"session not found: {session_id}"}
        outcome = {
            "outcome_id": f"outcome_{len(session.get('outcomes') or []) + 1}",
            "decision": str(payload.get("decision") or "undecided"),
            "value_recovered_usd": float(payload.get("value_recovered_usd", 0.0) or 0.0),
            "time_saved_minutes": float(payload.get("time_saved_minutes", 0.0) or 0.0),
            "notes": str(payload.get("notes") or ""),
            "created_at": self._now(),
        }
        session.setdefault("outcomes", []).append(outcome)
        if payload.get("close"):
            session["status"] = "closed"
        self._touch(session)
        if commit:
            self._save()
        return {"session": session, "outcome": outcome}

    def export_training_package(
        self,
        session_id: str,
        output_dir: str | Path | None = None,
        *,
        commit: bool = True,
    ) -> Dict[str, Any]:
        session = self.get_session(session_id)
        if not session:
            return {"error": f"session not found: {session_id}"}
        export_id = f"training_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        out = Path(output_dir) if output_dir else self.root_dir / "training_exports" / session_id / export_id
        out.mkdir(parents=True, exist_ok=True)
        latest = self._latest_analysis(session)
        package = self._training_package(session, latest, export_id)
        files = {
            "manifest": out / "manifest.json",
            "component_labels": out / "component_labels.jsonl",
            "ocr_examples": out / "ocr_examples.jsonl",
            "defect_labels": out / "defect_labels.jsonl",
            "board_roles": out / "board_roles.jsonl",
            "repair_cases": out / "repair_cases.jsonl",
            "README": out / "README.md",
        }
        files["manifest"].write_text(json.dumps(package, indent=2), encoding="utf-8")
        self._write_jsonl(files["component_labels"], package["examples"]["component_labels"])
        self._write_jsonl(files["ocr_examples"], package["examples"]["ocr_examples"])
        self._write_jsonl(files["defect_labels"], package["examples"]["defect_labels"])
        self._write_jsonl(files["board_roles"], package["examples"]["board_roles"])
        self._write_jsonl(files["repair_cases"], package["examples"]["repair_cases"])
        files["README"].write_text(self._training_readme(session, package), encoding="utf-8")
        record = {
            "export_id": export_id,
            "created_at": self._now(),
            "path": str(out),
            "files": {key: str(path) for key, path in files.items()},
            "counts": package["counts"],
        }
        session.setdefault("training_exports", []).append(record)
        self._touch(session)
        if commit:
            self._save()
        return {"session": session, "training_export": record, "package": package}

    def list_sessions(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        rows = self.sessions
        if status:
            rows = [session for session in rows if session.get("status") == status]
        rows = sorted(rows, key=lambda item: str(item.get("updated_at") or ""), reverse=True)
        return [self._session_preview(session) for session in rows[: max(1, min(limit, 200))]]

    def get_session(self, session_id: str) -> Dict[str, Any] | None:
        for session in self.sessions:
            if session.get("session_id") == session_id:
                return session
        return None

    def review_queue(
        self,
        *,
        status: str = "open",
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        rows = []
        for session in self.sessions:
            for task in session.get("evidence_tasks", []) or []:
                if status and task.get("status", "open") != status:
                    continue
                rows.append(
                    {
                        **task,
                        "session_id": session.get("session_id"),
                        "session_title": session.get("title"),
                        "route": session.get("route"),
                        "device_hint": session.get("device_hint"),
                        "certainty": session.get("certainty", {}).get("overall", {}),
                        "created_at": task.get("created_at") or session.get("created_at"),
                    }
                )
        rows.sort(key=lambda item: (int(item.get("priority", 3) or 3), str(item.get("created_at") or "")))
        return rows[: max(1, min(limit, 300))]

    def benchmark_report(self) -> Dict[str, Any]:
        sessions = self.sessions
        queue_open = self.review_queue(status="open", limit=10000)
        all_tasks = [
            task for session in sessions for task in (session.get("evidence_tasks") or [])
        ]
        resolved = [task for task in all_tasks if task.get("status") == "resolved"]
        certainty_levels = CounterSafe(
            (session.get("certainty", {}).get("overall") or {}).get("level", "unknown")
            for session in sessions
        )
        avg_task_count = (
            sum(len(session.get("evidence_tasks") or []) for session in sessions) / len(sessions)
            if sessions else 0.0
        )
        avg_capture_burden = (
            sum(float((session.get("metrics") or {}).get("capture_burden", 0) or 0.0) for session in sessions) / len(sessions)
            if sessions else 0.0
        )
        review_completion = len(resolved) / max(len(all_tasks), 1)
        training_exports = sum(len(session.get("training_exports") or []) for session in sessions)
        useful_sessions = sum(
            1 for session in sessions
            if (session.get("certainty", {}).get("overall") or {}).get("level") in {"likely", "certain"}
            or session.get("reviews")
            or session.get("outcomes")
        )
        capture_score = 0.0 if not sessions else (1.0 if avg_capture_burden <= 6 else max(0.0, 1.0 - (avg_capture_burden - 6.0) / 10.0))
        launch_score = min(
            1.0,
            0.25 * min(len(sessions) / 50.0, 1.0)
            + 0.20 * review_completion
            + 0.18 * min(training_exports / 5.0, 1.0)
            + 0.17 * min(useful_sessions / max(len(sessions), 1), 1.0)
            + 0.10 * capture_score
            + 0.10 * min(len([s for s in sessions if s.get("outcomes")]) / 10.0, 1.0),
        )
        return {
            "mode": "board_session_launch_benchmark",
            "summary": {
                "session_count": len(sessions),
                "open_task_count": len(queue_open),
                "resolved_task_count": len(resolved),
                "review_completion": round(review_completion, 3),
                "avg_evidence_tasks_per_session": round(avg_task_count, 2),
                "avg_capture_burden_per_session": round(avg_capture_burden, 2),
                "training_export_count": training_exports,
                "useful_session_count": useful_sessions,
                "launch_readiness_score": round(launch_score, 3),
                "certainty_distribution": dict(certainty_levels),
            },
            "target_thresholds": {
                "pilot_ready": {
                    "session_count": 50,
                    "review_completion": 0.6,
                    "avg_capture_burden_per_session_max": 6,
                    "training_export_count": 5,
                    "outcome_count": 10,
                },
                "paid_beta_ready": {
                    "session_count": 150,
                    "review_completion": 0.75,
                    "repeat_user_or_operator_count": 5,
                    "measured_time_or_value_savings_cases": 20,
                },
            },
            "competitive_scorecard": [
                {
                    "dimension": "capture_burden",
                    "why_it_matters": "Board-in-hand workflows must stay lightweight.",
                    "metric": "average capture prompts per session",
                    "current": round(avg_capture_burden, 2),
                    "target": "<= 6 normal repair/salvage intake captures",
                },
                {
                    "dimension": "certainty_honesty",
                    "why_it_matters": "Avoids overclaiming versus photo-to-schematic and AOI tools.",
                    "metric": "claim ledger level plus missing evidence",
                    "current": dict(certainty_levels),
                    "target": "likely/certain only after markings, measurements, or references",
                },
                {
                    "dimension": "learning_loop",
                    "why_it_matters": "Differentiates the product from one-shot repair chatbots.",
                    "metric": "review completion and training exports",
                    "current": {"review_completion": round(review_completion, 3), "training_exports": training_exports},
                    "target": "reviewed cases produce detector/OCR/defect examples every week",
                },
                {
                    "dimension": "business_value",
                    "why_it_matters": "Portfolio project becomes venture only when outcomes are measurable.",
                    "metric": "closed outcomes with time saved or recovered value",
                    "current": sum(len(session.get("outcomes") or []) for session in sessions),
                    "target": "20 measured cases before paid beta claims",
                },
            ],
            "next_actions": self._benchmark_next_actions(len(sessions), review_completion, avg_capture_burden, training_exports),
        }

    def _tasks_from_analysis(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        ledger = analysis.get("certainty_ledger") if isinstance(analysis.get("certainty_ledger"), dict) else {}
        tasks: List[Dict[str, Any]] = []
        now = self._now()
        seen = set()

        def add(task_type: str, prompt: str, *, priority: int = 3, source: str = "certainty_ledger", claim_id: str | None = None, usable_for: Iterable[str] | None = None) -> None:
            key = (task_type, prompt.strip().lower())
            if not prompt.strip() or key in seen:
                return
            seen.add(key)
            tasks.append(
                {
                    "task_id": f"task_{len(tasks) + 1}",
                    "type": task_type,
                    "prompt": prompt.strip(),
                    "priority": priority,
                    "status": "open",
                    "source": source,
                    "claim_id": claim_id,
                    "usable_for": list(usable_for or []),
                    "created_at": now,
                }
            )

        for missing in (ledger.get("missing_evidence") or [])[:14]:
            text = str(missing)
            add(self._task_type_for_missing(text), text, priority=self._priority_for_missing(text), usable_for=["repair", "salvage", "aoi", "training"])

        for item in (ledger.get("items") or [])[:40]:
            if not isinstance(item, dict):
                continue
            certainty = str(item.get("certainty") or "unknown")
            claim_type = str(item.get("claim_type") or "claim")
            if certainty in {"possible", "unknown"}:
                add(
                    "review",
                    f"Review {claim_type}: {item.get('claim', 'unlabeled claim')}",
                    priority=1 if certainty == "unknown" else 2,
                    source="low_certainty_claim",
                    claim_id=str(item.get("item_id") or ""),
                    usable_for=item.get("usable_for") or [],
                )
            for action in (item.get("next_actions") or [])[:2]:
                task_type = "measurement" if self._looks_like_measurement(str(action)) else "action"
                add(
                    task_type,
                    str(action),
                    priority=2 if task_type == "measurement" else 3,
                    source="claim_next_action",
                    claim_id=str(item.get("item_id") or ""),
                    usable_for=item.get("usable_for") or [],
                )

        connection = analysis.get("machine_connection_map") if isinstance(analysis.get("machine_connection_map"), dict) else {}
        for measurement in ((connection.get("splice_plan") or {}).get("required_measurements") or [])[:8]:
            add("measurement", str(measurement), priority=1, source="splice_measurement_gate", usable_for=["repair", "splicing", "salvage"])

        aoi = analysis.get("aoi_inspection") if isinstance(analysis.get("aoi_inspection"), dict) else {}
        for blocker in (aoi.get("blockers") or [])[:8]:
            add(self._task_type_for_missing(str(blocker)), str(blocker), priority=2, source="aoi_blocker", usable_for=["aoi", "training"])

        return self._trim_tasks(tasks)

    def _tasks_from_repair_guide(self, guide: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not guide:
            return []
        tasks: List[Dict[str, Any]] = []
        now = self._now()

        def add(task_type: str, prompt: str, *, priority: int = 3, source: str = "repair_guide") -> None:
            if not str(prompt).strip():
                return
            tasks.append(
                {
                    "task_id": f"task_{len(tasks) + 1}",
                    "type": task_type,
                    "prompt": str(prompt).strip(),
                    "priority": priority,
                    "status": "open",
                    "source": source,
                    "claim_id": None,
                    "usable_for": ["repair", "safety", "training"],
                    "created_at": now,
                }
            )

        safety = guide.get("safety_profile") if isinstance(guide.get("safety_profile"), dict) else {}
        if safety.get("risk_level") == "high":
            add(
                "review",
                "confirm safe isolation, discharge state, and no live high-voltage probing before continuing",
                priority=1,
                source="repair_safety_gate",
            )

        for item in (guide.get("evidence_to_collect_next") or [])[:8]:
            text = str(item)
            add(
                self._task_type_for_missing(text),
                text,
                priority=self._priority_for_missing(text),
                source="repair_guide_evidence",
            )

        for step in (guide.get("diagnostic_flow") or [])[:3]:
            if not isinstance(step, dict):
                continue
            actions = step.get("actions") if isinstance(step.get("actions"), list) else []
            for action in actions[:1]:
                text = str(action)
                if self._looks_like_measurement(text):
                    add("measurement", text, priority=2, source="repair_diagnostic_flow")

        return tasks

    def _training_package(self, session: Dict[str, Any], analysis: Dict[str, Any], export_id: str) -> Dict[str, Any]:
        detections = analysis.get("detections") or []
        marking = analysis.get("marking_analysis") if isinstance(analysis.get("marking_analysis"), dict) else {}
        defects = (analysis.get("defect_inspection") or {}).get("defects") if isinstance(analysis.get("defect_inspection"), dict) else []
        board = analysis.get("board_understanding") if isinstance(analysis.get("board_understanding"), dict) else {}
        reviews = session.get("reviews") or []
        component_labels = []
        for index, det in enumerate(detections):
            if not isinstance(det, dict):
                continue
            component_labels.append(
                {
                    "session_id": session.get("session_id"),
                    "example_id": f"{session.get('session_id')}_component_{index + 1}",
                    "class_name": det.get("class_name") or det.get("label") or "component",
                    "bbox": det.get("bbox") or [],
                    "confidence": det.get("confidence"),
                    "semantic_confidence": det.get("semantic_confidence"),
                    "ocr_text": det.get("ocr_text"),
                    "part_number": det.get("part_number"),
                    "review_status": self._review_status_for_claim(reviews, f"component_{index + 1}"),
                    "source": "board_session",
                }
            )
        ocr_examples = []
        for index, component in enumerate(marking.get("components", []) or []):
            ocr_examples.append(
                {
                    "session_id": session.get("session_id"),
                    "example_id": f"{session.get('session_id')}_ocr_{index + 1}",
                    "component_id": component.get("component_id"),
                    "text": component.get("text"),
                    "part_tokens": component.get("part_tokens") or [],
                    "silk_labels": component.get("silk_labels") or [],
                    "candidates": component.get("candidates") or [],
                }
            )
        defect_labels = []
        for index, defect in enumerate(defects or []):
            if isinstance(defect, dict):
                defect_labels.append(
                    {
                        "session_id": session.get("session_id"),
                        "example_id": f"{session.get('session_id')}_defect_{index + 1}",
                        "defect_type": defect.get("defect_type"),
                        "bbox": defect.get("bbox") or [],
                        "confidence": defect.get("confidence"),
                        "severity": defect.get("severity"),
                        "repair_action": defect.get("repair_action"),
                    }
                )
        identity = board.get("board_identity") or {}
        board_roles = [
            {
                "session_id": session.get("session_id"),
                "role": identity.get("primary_type", "unknown_board"),
                "confidence": identity.get("confidence", board.get("confidence", 0.0)),
                "evidence": identity.get("evidence") or [],
                "functional_blocks": board.get("functional_blocks") or [],
            }
        ] if board else []
        repair_guide = session.get("repair_guide") if isinstance(session.get("repair_guide"), dict) else {}
        top_fault = (repair_guide.get("fault_candidates") or [{}])[0] if isinstance(repair_guide.get("fault_candidates"), list) else {}
        case_workflow = {
            "session_id": session.get("session_id"),
            "title": session.get("title"),
            "route": session.get("route"),
            "device_hint": session.get("device_hint"),
            "symptoms": session.get("symptoms") or [],
            "repair_family": (repair_guide.get("device_family") or {}).get("id"),
            "top_fault_id": top_fault.get("fault_id"),
            "top_fault_name": top_fault.get("name"),
            "workflow_tasks": [
                {
                    "task_id": task.get("task_id"),
                    "type": task.get("type"),
                    "prompt": task.get("prompt"),
                    "status": task.get("status", "open"),
                    "source": task.get("source"),
                }
                for task in (session.get("evidence_tasks") or [])
            ],
            "reviews": reviews,
            "measurements": (session.get("evidence") or {}).get("measurements") or [],
            "outcomes": session.get("outcomes") or [],
        }
        counts = {
            "component_labels": len(component_labels),
            "ocr_examples": len(ocr_examples),
            "defect_labels": len(defect_labels),
            "board_roles": len(board_roles),
            "repair_cases": 1,
            "reviews": len(reviews),
            "measurements": len((session.get("evidence") or {}).get("measurements") or []),
        }
        return {
            "export_id": export_id,
            "mode": "board_session_training_package",
            "created_at": self._now(),
            "session": self._session_preview(session),
            "counts": counts,
            "examples": {
                "component_labels": component_labels,
                "ocr_examples": ocr_examples,
                "defect_labels": defect_labels,
                "board_roles": board_roles,
                "repair_cases": [case_workflow],
                "reviews": reviews,
                "measurements": (session.get("evidence") or {}).get("measurements") or [],
            },
            "recommended_uses": [
                "YOLO component label review",
                "OCR crop/marking normalization",
                "defect candidate validation",
                "board-role and functional-block benchmark cases",
                "repair-lane and evidence-task workflow tuning",
            ],
        }

    def _session_preview(self, session: Dict[str, Any]) -> Dict[str, Any]:
        tasks = session.get("evidence_tasks") or []
        return {
            "session_id": session.get("session_id"),
            "title": session.get("title"),
            "route": session.get("route"),
            "status": session.get("status"),
            "device_hint": session.get("device_hint"),
            "created_at": session.get("created_at"),
            "updated_at": session.get("updated_at"),
            "certainty": session.get("certainty", {}),
            "metrics": session.get("metrics") or self._session_metrics(tasks, self._latest_analysis(session)),
            "open_task_count": len([task for task in tasks if task.get("status", "open") == "open"]),
            "review_count": len(session.get("reviews") or []),
            "training_export_count": len(session.get("training_exports") or []),
        }

    def _session_metrics(self, tasks: List[Dict[str, Any]], analysis: Dict[str, Any]) -> Dict[str, Any]:
        open_tasks = [task for task in tasks if task.get("status", "open") == "open"]
        resolved = [task for task in tasks if task.get("status") == "resolved"]
        ledger = analysis.get("certainty_ledger") if isinstance(analysis.get("certainty_ledger"), dict) else {}
        return {
            "task_count": len(tasks),
            "open_task_count": len(open_tasks),
            "resolved_task_count": len(resolved),
            "capture_burden": len([task for task in tasks if task.get("type") == "capture"]),
            "measurement_count_required": len([task for task in tasks if task.get("type") == "measurement"]),
            "certainty_level": (ledger.get("overall") or {}).get("level", "unknown"),
            "certainty_score": (ledger.get("overall") or {}).get("score", 0.0),
            "training_capture_recommended": bool((ledger.get("training_queue") or {}).get("should_capture")),
        }

    def _analysis_from_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        analysis = payload.get("analysis")
        if not isinstance(analysis, dict):
            analysis = payload.get("results")
        return analysis if isinstance(analysis, dict) else {}

    def _latest_analysis(self, session: Dict[str, Any]) -> Dict[str, Any]:
        analyses = session.get("analyses") or []
        if not analyses:
            return {}
        latest = analyses[-1]
        return latest.get("results") if isinstance(latest.get("results"), dict) else {}

    def _certainty_snapshot(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        ledger = analysis.get("certainty_ledger") if isinstance(analysis.get("certainty_ledger"), dict) else {}
        return {
            "overall": ledger.get("overall", {}),
            "counts": ledger.get("counts", {}),
            "missing_evidence": ledger.get("missing_evidence", [])[:12],
            "training_queue": ledger.get("training_queue", {}),
        }

    def _infer_route(self, payload: Dict[str, Any], analysis: Dict[str, Any]) -> str:
        text = " ".join(
            [
                str(payload.get("description") or ""),
                str(payload.get("device_hint") or ""),
                " ".join(self._listify(payload.get("symptoms"))),
            ]
        ).lower()
        if any(term in text for term in ["mains", "microwave", "crt", "high voltage", "lithium swollen"]):
            return "safety"
        if any(term in text for term in ["repair", "broken", "dead", "no power", "hot", "warm", "fault", "corrosion", "will not", "won't", "not spin", "no spin", "wiggle", "intermittent"]):
            return "repair"
        if any(term in text for term in ["lot", "sell", "price", "shipping", "resale", "arbitrage"]):
            return "source"
        if (analysis.get("salvage_opportunities") or {}).get("best_opportunity"):
            return "salvage"
        if (analysis.get("certainty_ledger") or {}).get("missing_evidence"):
            return "evidence"
        return "intake"

    def _title(self, payload: Dict[str, Any], analysis: Dict[str, Any]) -> str:
        for key in ["title", "device_hint", "description"]:
            value = str(payload.get(key) or "").strip()
            if value:
                return value[:90]
        role = ((analysis.get("board_understanding") or {}).get("board_identity") or {}).get("primary_type")
        return str(role or "Board session").replace("_", " ")

    def _task_type_for_missing(self, text: str) -> str:
        lower = text.lower()
        if any(term in lower for term in ["golden", "reference", "netlist", "kicad", "gerber"]):
            return "reference"
        if any(term in lower for term in ["photo", "scan", "crop", "image", "lighting", "focus", "close-up", "side"]):
            return "capture"
        if self._looks_like_measurement(lower):
            return "measurement"
        if any(term in lower for term in ["review", "confirm", "verify", "operator"]):
            return "review"
        return "evidence"

    def _trim_tasks(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        caps = {
            "measurement": 3,
            "capture": 3,
            "review": 3,
            "reference": 2,
            "evidence": 2,
            "action": 2,
        }
        kept: List[Dict[str, Any]] = []
        counts: Dict[str, int] = {}
        ordered = sorted(
            tasks,
            key=lambda item: (
                int(item.get("priority", 3) or 3),
                {"measurement": 0, "capture": 1, "review": 2, "reference": 3, "evidence": 4, "action": 5}.get(str(item.get("type")), 6),
            ),
        )
        for task in ordered:
            task_type = str(task.get("type") or "evidence")
            if counts.get(task_type, 0) >= caps.get(task_type, 2):
                continue
            kept.append(task)
            counts[task_type] = counts.get(task_type, 0) + 1
            if len(kept) >= 10:
                break
        for index, task in enumerate(kept, start=1):
            task["task_id"] = f"task_{index}"
        return kept

    def _dedupe_tasks(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        kept: List[Dict[str, Any]] = []
        seen = set()
        for task in tasks:
            key = (str(task.get("type") or ""), str(task.get("prompt") or "").strip().lower())
            if not key[1] or key in seen:
                continue
            seen.add(key)
            kept.append(task)
        return kept

    def _priority_for_missing(self, text: str) -> int:
        lower = text.lower()
        if any(term in lower for term in ["voltage", "continuity", "resistance", "current", "power", "safety", "high-voltage", "mains", "tester readings", "charger rating", "thermal fuse", "flashlight-test", "driver output"]):
            return 1
        if any(term in lower for term in ["retake", "close-up", "marking", "connector", "netlist", "golden"]):
            return 2
        return 3

    def _looks_like_measurement(self, text: str) -> bool:
        lower = text.lower()
        return any(term in lower for term in ["voltage", "continuity", "resistance", "current", "logic level", "measure", "powered", "reading", "tester", "rating", "output"])

    def _find_task(self, session: Dict[str, Any], task_id: str) -> Dict[str, Any] | None:
        for task in session.get("evidence_tasks", []) or []:
            if task.get("task_id") == task_id:
                return task
        return None

    def _resolve_first_matching_task(self, session: Dict[str, Any], task_types: set[str], resolution: Dict[str, Any]) -> None:
        for task in session.get("evidence_tasks", []) or []:
            if task.get("status", "open") == "open" and task.get("type") in task_types:
                task["status"] = "resolved"
                task["resolved_at"] = self._now()
                task["review"] = resolution
                return

    def _benchmark_next_actions(self, session_count: int, review_completion: float, avg_capture_burden: float, training_exports: int) -> List[str]:
        actions = []
        if session_count < 50:
            actions.append("collect 50 real board-in-hand sessions across 1-2 target device categories")
        if review_completion < 0.6:
            actions.append("review or correct open evidence tasks until completion exceeds 60%")
        if avg_capture_burden > 6:
            actions.append("reduce normal intake prompts to the highest-value 2-6 captures or measurements")
        if training_exports < 5:
            actions.append("export reviewed sessions into detector/OCR/defect training packages")
        actions.append("record repair/salvage outcomes with time saved or value recovered")
        return actions

    def _review_status_for_claim(self, reviews: List[Dict[str, Any]], claim_fragment: str) -> str:
        for review in reviews:
            payload = review.get("payload") if isinstance(review.get("payload"), dict) else {}
            if claim_fragment and claim_fragment in str(payload.get("task_id") or ""):
                return str(review.get("action") or "reviewed")
        return "unreviewed"

    def _session_id(self, payload: Dict[str, Any]) -> str:
        explicit = str(payload.get("session_id") or "").strip()
        if explicit:
            return explicit
        return f"board_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

    def _touch(self, session: Dict[str, Any]) -> None:
        session["updated_at"] = self._now()

    def _load(self) -> None:
        if not self.store_path.exists():
            self.sessions = []
            return
        try:
            payload = json.loads(self.store_path.read_text(encoding="utf-8"))
            self.sessions = payload.get("sessions", []) if isinstance(payload, dict) else []
        except Exception:
            self.sessions = []

    def _save(self) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.store_path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"sessions": self._json_safe(self.sessions)}, indent=2), encoding="utf-8")
        tmp.replace(self.store_path)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _listify(value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            if not value.strip():
                return []
            return [item.strip() for item in value.replace(";", "\n").splitlines() if item.strip()]
        return [str(value).strip()] if str(value).strip() else []

    @staticmethod
    def _listify_dict(value: Any) -> List[Dict[str, Any]]:
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            return [value]
        return []

    @staticmethod
    def _write_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

    def _training_readme(self, session: Dict[str, Any], package: Dict[str, Any]) -> str:
        counts = package.get("counts", {})
        return "\n".join(
            [
                f"# Training Package: {session.get('title')}",
                "",
                f"Session: `{session.get('session_id')}`",
                f"Route: `{session.get('route')}`",
                f"Certainty: `{(session.get('certainty', {}).get('overall') or {}).get('level', 'unknown')}`",
                "",
                "## Counts",
                f"- Component labels: {counts.get('component_labels', 0)}",
                f"- OCR examples: {counts.get('ocr_examples', 0)}",
                f"- Defect labels: {counts.get('defect_labels', 0)}",
                f"- Board roles: {counts.get('board_roles', 0)}",
                f"- Repair cases: {counts.get('repair_cases', 0)}",
                f"- Reviews: {counts.get('reviews', 0)}",
                f"- Measurements: {counts.get('measurements', 0)}",
                "",
                "Use this package as reviewed candidate data. Treat unreviewed labels as weak examples.",
                "",
            ]
        )

    def _json_safe(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {str(key): self._json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._json_safe(item) for item in value]
        if np is not None and isinstance(value, np.integer):
            return int(value)
        if np is not None and isinstance(value, np.floating):
            return float(value)
        if np is not None and isinstance(value, np.ndarray):
            return self._json_safe(value.tolist())
        return value


class CounterSafe(dict):
    def __init__(self, values: Iterable[Any]):
        super().__init__()
        for value in values:
            key = str(value)
            self[key] = self.get(key, 0) + 1
