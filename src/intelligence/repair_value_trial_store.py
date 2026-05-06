"""Measured value trials for repair, salvage, and reuse workflows."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from src.intelligence.board_session_store import BoardSessionStore


class RepairValueTrialStore:
    """Persist and score whether a case produced practical value."""

    def __init__(
        self,
        store_path: str | Path = "data/repair_value_trials/trials.json",
        *,
        session_store: BoardSessionStore | None = None,
    ):
        self.store_path = Path(store_path)
        self.root_dir = self.store_path.parent
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.session_store = session_store or BoardSessionStore()
        self.trials: List[Dict[str, Any]] = []
        self._load()

    def create_trial(
        self,
        payload: Dict[str, Any],
        *,
        user_id: str = "anonymous",
        commit: bool = True,
    ) -> Dict[str, Any]:
        now = self._now()
        session_id = str(payload.get("session_id") or "").strip()
        session = self.session_store.get_session(session_id) if session_id else None
        baseline = self._baseline(payload)
        assisted = self._assisted(payload, session)
        scorecard = self._scorecard(payload, session, baseline, assisted)
        value_score = round(sum(float(row["weighted_score"]) for row in scorecard), 3)
        evidence_gates = self._evidence_gates(session, assisted)
        verdict = self._verdict(value_score, evidence_gates, assisted, session)

        trial = {
            "trial_id": str(payload.get("trial_id") or f"value_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"),
            "session_id": session_id,
            "case_id": str(payload.get("case_id") or ""),
            "title": str(payload.get("title") or (session or {}).get("title") or "Repair value trial"),
            "lane_id": str(payload.get("lane_id") or payload.get("expected_lane") or ""),
            "goal": str(payload.get("goal") or self._infer_goal(payload, session)),
            "status": "recorded",
            "verdict": verdict,
            "value_score": value_score,
            "baseline": baseline,
            "assisted": assisted,
            "scorecard": scorecard,
            "evidence_gates": evidence_gates,
            "honesty_notes": self._honesty_notes(verdict, evidence_gates, assisted, session),
            "created_at": now,
            "updated_at": now,
            "user_id": user_id,
        }
        if commit:
            self.trials.append(trial)
            self._save()
        return trial

    def list_trials(self, *, limit: int = 50) -> List[Dict[str, Any]]:
        rows = sorted(self.trials, key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)
        return [self._trial_preview(row) for row in rows[: max(1, min(limit, 200))]]

    def get_trial(self, trial_id: str) -> Dict[str, Any] | None:
        for trial in self.trials:
            if trial.get("trial_id") == trial_id:
                return trial
        return None

    def benchmark_report(self) -> Dict[str, Any]:
        trials = self.trials
        counts = self._counts(row.get("verdict") for row in trials)
        avg_score = round(sum(float(row.get("value_score", 0.0) or 0.0) for row in trials) / max(len(trials), 1), 3)
        measured = [
            row for row in trials
            if float(((row.get("assisted") or {}).get("time_saved_minutes")) or 0.0) > 0
            or float(((row.get("assisted") or {}).get("value_recovered_usd")) or 0.0) > 0
        ]
        proven = counts.get("value_proven", 0)
        likely = counts.get("value_likely", 0)
        readiness = min(
            1.0,
            0.25 * min(len(trials) / 30.0, 1.0)
            + 0.25 * min(len(measured) / 15.0, 1.0)
            + 0.20 * ((proven + 0.5 * likely) / max(len(trials), 1))
            + 0.15 * min(self._trial_artifact_count(trials) / 20.0, 1.0)
            + 0.15 * min(self._distinct_lanes(trials) / 3.0, 1.0),
        )
        return {
            "mode": "repair_value_trial_benchmark",
            "summary": {
                "trial_count": len(trials),
                "average_value_score": avg_score,
                "value_proven": proven,
                "value_likely": likely,
                "not_valuable_yet": counts.get("not_valuable_yet", 0),
                "plumbing_only": counts.get("plumbing_only", 0),
                "measured_outcome_count": len(measured),
                "distinct_lane_count": self._distinct_lanes(trials),
                "value_readiness_score": round(readiness, 3),
            },
            "target_thresholds": {
                "honest_pilot_ready": {
                    "trial_count": 30,
                    "measured_outcome_count": 15,
                    "value_proven_or_likely_rate": 0.6,
                    "distinct_lane_count": 3,
                },
                "paid_beta_ready": {
                    "trial_count": 100,
                    "measured_outcome_count": 50,
                    "value_proven_rate": 0.45,
                    "repeat_operator_count": 5,
                },
            },
            "scorecard": [
                {
                    "dimension": "truth_over_uptime",
                    "metric": "plumbing-only trials",
                    "current": counts.get("plumbing_only", 0),
                    "target": "falls as real evidence, outcomes, and training exports accumulate",
                },
                {
                    "dimension": "customer_value",
                    "metric": "measured outcomes with time saved or value recovered",
                    "current": len(measured),
                    "target": "15 measured outcomes before claiming pilot value",
                },
                {
                    "dimension": "repeatability",
                    "metric": "value-proven or value-likely trials",
                    "current": proven + likely,
                    "target": "same workflow works across the target lanes, not only one lucky case",
                },
            ],
            "next_actions": self._next_actions(trials, counts, len(measured)),
        }

    def _baseline(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        baseline = payload.get("baseline") if isinstance(payload.get("baseline"), dict) else {}
        return {
            "method": str(baseline.get("method") or payload.get("baseline_method") or "manual_search_or_guesswork"),
            "estimated_time_minutes": self._float(baseline.get("estimated_time_minutes", payload.get("baseline_time_minutes")), 0.0),
            "confidence": self._clamp(self._float(baseline.get("confidence", payload.get("baseline_confidence")), 0.25)),
            "expected_value_usd": self._float(baseline.get("expected_value_usd", payload.get("expected_value_usd")), 0.0),
            "known_blockers": self._listify(baseline.get("known_blockers", payload.get("baseline_blockers"))),
        }

    def _assisted(
        self,
        payload: Dict[str, Any],
        session: Dict[str, Any] | None,
    ) -> Dict[str, Any]:
        session = session or {}
        metrics = session.get("metrics") if isinstance(session.get("metrics"), dict) else {}
        evidence = session.get("evidence") if isinstance(session.get("evidence"), dict) else {}
        outcomes = session.get("outcomes") if isinstance(session.get("outcomes"), list) else []
        repair_guide = session.get("repair_guide") if isinstance(session.get("repair_guide"), dict) else {}
        confidence = payload.get("assisted_confidence")
        if confidence is None:
            confidence = repair_guide.get("confidence")
        if confidence is None:
            confidence = (session.get("certainty") or {}).get("overall", {}).get("score") if isinstance(session.get("certainty"), dict) else None
        if confidence is None:
            confidence = self._resolution_ratio(session)
        value_recovered = sum(self._float(outcome.get("value_recovered_usd"), 0.0) for outcome in outcomes if isinstance(outcome, dict))
        time_saved = sum(self._float(outcome.get("time_saved_minutes"), 0.0) for outcome in outcomes if isinstance(outcome, dict))
        decisions = [str(outcome.get("decision") or "") for outcome in outcomes if isinstance(outcome, dict)]
        return {
            "session_found": bool(session),
            "workflow_score": self._float(payload.get("workflow_score"), 0.0),
            "verdict": str(payload.get("case_verdict") or payload.get("verdict") or ""),
            "confidence": self._clamp(self._float(confidence, 0.0)),
            "capture_count": len(evidence.get("captures") or []),
            "measurement_count": len(evidence.get("measurements") or []),
            "review_count": len(session.get("reviews") or []),
            "outcome_count": len(outcomes),
            "training_export_count": len(session.get("training_exports") or []),
            "task_count": int(metrics.get("task_count", len(session.get("evidence_tasks") or [])) or 0),
            "resolved_task_count": int(metrics.get("resolved_task_count", 0) or 0),
            "open_task_count": int(metrics.get("open_task_count", 0) or 0),
            "safety_risk": str((repair_guide.get("safety_profile") or {}).get("risk_level") or "unknown"),
            "route": str(session.get("route") or ""),
            "outcome_decisions": decisions,
            "value_recovered_usd": round(value_recovered + self._float(payload.get("value_recovered_usd"), 0.0), 2),
            "time_saved_minutes": round(time_saved + self._float(payload.get("time_saved_minutes"), 0.0), 2),
        }

    def _scorecard(
        self,
        payload: Dict[str, Any],
        session: Dict[str, Any] | None,
        baseline: Dict[str, Any],
        assisted: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        title = str(payload.get("title") or (session or {}).get("title") or "")
        lane = str(payload.get("lane_id") or payload.get("expected_lane") or "")
        symptoms = self._listify(payload.get("symptoms") or (session or {}).get("symptoms"))
        relevance = 0.25 + (0.25 if title else 0.0) + (0.2 if lane else 0.0) + (0.2 if symptoms else 0.0) + (0.1 if str(payload.get("source_url") or "") else 0.0)
        guidance = min(1.0, 0.25 * min(assisted["task_count"] / 4.0, 1.0) + 0.25 * min(assisted["workflow_score"] / 0.7, 1.0) + 0.25 * assisted["confidence"] + 0.25 * (1.0 if assisted["verdict"] in {"solvable_now", "value_likely", "value_proven"} else 0.55 if assisted["task_count"] else 0.0))
        evidence = min(
            1.0,
            0.20 * min(assisted["capture_count"] / 2.0, 1.0)
            + 0.25 * min(assisted["measurement_count"] / 2.0, 1.0)
            + 0.25 * min(assisted["review_count"] / 2.0, 1.0)
            + 0.30 * min(assisted["resolved_task_count"] / max(assisted["task_count"], 1), 1.0),
        )
        certainty_delta = self._clamp(0.5 + assisted["confidence"] - float(baseline.get("confidence", 0.25) or 0.25))
        high_risk = assisted["route"] == "safety" or assisted["safety_risk"] == "high"
        safety = 0.85 if not high_risk else 0.6 + 0.25 * min(assisted["review_count"], 1)
        economic = min(
            1.0,
            0.45 * min(assisted["time_saved_minutes"] / 30.0, 1.0)
            + 0.45 * min(assisted["value_recovered_usd"] / max(float(baseline.get("expected_value_usd") or 20.0), 20.0), 1.0)
            + 0.10 * (1.0 if any(decision in {"repaired", "salvaged", "reused", "sold", "built"} for decision in assisted["outcome_decisions"]) else 0.0),
        )
        learning = min(1.0, 0.4 * min(assisted["training_export_count"], 1) + 0.3 * min(assisted["review_count"] / 2.0, 1.0) + 0.3 * min(assisted["outcome_count"], 1))
        dimensions = [
            ("case_relevance", 0.12, relevance, "case has a lane, real device context, symptoms, and source"),
            ("actionable_guidance", 0.20, guidance, "system created a usable guide and evidence queue"),
            ("evidence_followthrough", 0.22, evidence, "operator captured, measured, reviewed, and resolved tasks"),
            ("certainty_delta", 0.14, certainty_delta, "assisted workflow increases confidence over baseline"),
            ("safety_handling", 0.10, safety, "unsafe cases get gated instead of overclaimed"),
            ("economic_outcome", 0.14, economic, "trial records saved time, recovered value, or successful reuse"),
            ("learning_asset", 0.08, learning, "case becomes data for model/workflow improvement"),
        ]
        return [
            {
                "dimension": name,
                "weight": weight,
                "score": round(self._clamp(score), 3),
                "weighted_score": round(weight * self._clamp(score), 3),
                "why": why,
            }
            for name, weight, score, why in dimensions
        ]

    def _evidence_gates(self, session: Dict[str, Any] | None, assisted: Dict[str, Any]) -> List[Dict[str, Any]]:
        gates = [
            ("session_exists", assisted["session_found"], "a persisted board/case session exists"),
            ("has_action_queue", assisted["task_count"] > 0, "system produced specific evidence or diagnostic tasks"),
            ("has_capture", assisted["capture_count"] > 0, "operator attached at least one real capture or reference"),
            ("has_measurement", assisted["measurement_count"] > 0, "operator recorded at least one electrical/mechanical measurement"),
            ("has_review", assisted["review_count"] > 0, "human reviewed or corrected a system task"),
            ("has_outcome", assisted["outcome_count"] > 0, "case ended with a repair, salvage, reuse, or no-fix outcome"),
            ("has_measured_value", assisted["time_saved_minutes"] > 0 or assisted["value_recovered_usd"] > 0, "outcome includes saved time or recovered value"),
            ("has_learning_export", assisted["training_export_count"] > 0, "reviewed case was exported as reusable training/workflow data"),
        ]
        return [
            {"gate": gate, "passed": bool(passed), "why": why}
            for gate, passed, why in gates
        ]

    def _verdict(
        self,
        value_score: float,
        gates: List[Dict[str, Any]],
        assisted: Dict[str, Any],
        session: Dict[str, Any] | None,
    ) -> str:
        passed = {gate["gate"] for gate in gates if gate["passed"]}
        if "session_exists" not in passed or "has_action_queue" not in passed:
            return "plumbing_only"
        if assisted["safety_risk"] == "high" and "has_review" not in passed:
            return "not_valuable_yet"
        if value_score >= 0.72 and {"has_measurement", "has_review", "has_outcome", "has_measured_value"}.issubset(passed):
            return "value_proven"
        if value_score >= 0.55 and {"has_capture", "has_measurement"}.issubset(passed) and ("has_review" in passed or "has_outcome" in passed):
            return "value_likely"
        if "has_capture" not in passed and "has_measurement" not in passed and "has_outcome" not in passed:
            return "plumbing_only"
        return "not_valuable_yet"

    def _honesty_notes(
        self,
        verdict: str,
        gates: List[Dict[str, Any]],
        assisted: Dict[str, Any],
        session: Dict[str, Any] | None,
    ) -> List[str]:
        missing = [gate["gate"].replace("_", " ") for gate in gates if not gate["passed"]]
        notes = []
        if verdict == "plumbing_only":
            notes.append("This run proves software flow only; it does not prove repair or salvage value yet.")
        if "has measurement" in missing:
            notes.append("No practical certainty claim should be made until at least one relevant measurement is recorded.")
        if "has outcome" in missing:
            notes.append("Do not claim customer value until the case has a repair, no-fix, salvage, reuse, or sale outcome.")
        if "has measured value" in missing:
            notes.append("Business value is unmeasured until time saved or recovered value is recorded.")
        if "has learning export" in missing:
            notes.append("The case is not improving the engine until it is reviewed and exported as training/workflow data.")
        if assisted["safety_risk"] == "high" and assisted["review_count"] == 0:
            notes.append("High-risk repair cases need a resolved safety review before any assisted-workflow claim.")
        return notes[:6]

    def _trial_preview(self, trial: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "trial_id": trial.get("trial_id"),
            "session_id": trial.get("session_id"),
            "title": trial.get("title"),
            "lane_id": trial.get("lane_id"),
            "goal": trial.get("goal"),
            "verdict": trial.get("verdict"),
            "value_score": trial.get("value_score"),
            "created_at": trial.get("created_at"),
            "assisted": {
                key: (trial.get("assisted") or {}).get(key)
                for key in ["capture_count", "measurement_count", "review_count", "outcome_count", "training_export_count", "time_saved_minutes", "value_recovered_usd"]
            },
            "failed_gates": [gate for gate in trial.get("evidence_gates", []) if not gate.get("passed")],
        }

    def _next_actions(self, trials: List[Dict[str, Any]], counts: Dict[str, int], measured_count: int) -> List[str]:
        actions = []
        if len(trials) < 30:
            actions.append("run 30 value trials on board-in-hand cases before claiming pilot readiness")
        if measured_count < 15:
            actions.append("record time saved or recovered value on at least 15 cases")
        if counts.get("plumbing_only", 0):
            actions.append("convert plumbing-only runs by adding measurements, reviews, outcomes, and training exports")
        if self._distinct_lanes(trials) < 3:
            actions.append("cover all three launch lanes with measured value trials")
        actions.append("compare Circuit-assisted time/confidence against manual search or ad-hoc repair attempts")
        return actions

    def _infer_goal(self, payload: Dict[str, Any], session: Dict[str, Any] | None) -> str:
        text = " ".join(
            [
                str(payload.get("title") or ""),
                str(payload.get("goal") or ""),
                str((session or {}).get("route") or ""),
                str((session or {}).get("description") or ""),
            ]
        ).lower()
        if any(term in text for term in ["sell", "arbitrage", "resale"]):
            return "resale_arbitrage"
        if any(term in text for term in ["salvage", "reuse", "build"]):
            return "salvage_to_build"
        return "repair_or_diagnosis"

    def _resolution_ratio(self, session: Dict[str, Any] | None) -> float:
        if not session:
            return 0.0
        tasks = session.get("evidence_tasks") or []
        if not tasks:
            return 0.0
        resolved = len([task for task in tasks if task.get("status") == "resolved"])
        return resolved / max(len(tasks), 1)

    def _trial_artifact_count(self, trials: List[Dict[str, Any]]) -> int:
        return sum(
            1
            for trial in trials
            if int(((trial.get("assisted") or {}).get("review_count")) or 0) > 0
            or int(((trial.get("assisted") or {}).get("training_export_count")) or 0) > 0
        )

    def _distinct_lanes(self, trials: List[Dict[str, Any]]) -> int:
        return len({str(trial.get("lane_id") or "") for trial in trials if str(trial.get("lane_id") or "").strip()})

    def _load(self) -> None:
        if not self.store_path.exists():
            self.trials = []
            return
        try:
            payload = json.loads(self.store_path.read_text(encoding="utf-8"))
            self.trials = payload.get("trials", []) if isinstance(payload, dict) else []
        except Exception:
            self.trials = []

    def _save(self) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.store_path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"trials": self._json_safe(self.trials)}, indent=2), encoding="utf-8")
        tmp.replace(self.store_path)

    @staticmethod
    def _counts(values: Any) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for value in values:
            key = str(value or "unknown")
            counts[key] = counts.get(key, 0) + 1
        return counts

    @staticmethod
    def _float(value: Any, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(1.0, value))

    @staticmethod
    def _listify(value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            return [item.strip() for item in value.replace(";", "\n").splitlines() if item.strip()]
        return [str(value).strip()] if str(value).strip() else []

    @staticmethod
    def _json_safe(value: Any) -> Any:
        try:
            json.dumps(value)
            return value
        except TypeError:
            if isinstance(value, dict):
                return {str(key): RepairValueTrialStore._json_safe(item) for key, item in value.items()}
            if isinstance(value, list):
                return [RepairValueTrialStore._json_safe(item) for item in value]
            return str(value)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
