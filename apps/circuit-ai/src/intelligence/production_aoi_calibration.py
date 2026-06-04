"""Outcome-backed calibration report for production AOI gates."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

from src.intelligence.production_aoi_certainty import ProductionAOICertaintyGate


class ProductionAOICalibrator:
    """Measure whether AOI release decisions match reviewed real outcomes."""

    PASS_STATUSES = {
        "pass",
        "passed",
        "good",
        "known_good",
        "accepted",
        "release_ok",
        "released_ok",
        "conforming",
        "no_defect",
        "no_defects",
    }
    FAIL_STATUSES = {
        "fail",
        "failed",
        "bad",
        "defect",
        "defective",
        "rework",
        "scrap",
        "unsafe",
        "escape",
        "field_return",
        "returned",
        "not_conforming",
        "nonconforming",
        "non_conforming",
    }
    RELEASE_DECISIONS = {"released", "accepted", "passed", "shipped", "release_ok"}
    FAIL_DECISIONS = {"rework", "scrap", "unsafe", "failed", "field_return", "returned", "not_conforming"}

    def build_report(self, sessions: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
        cases = [case for session in sessions for case in self._cases_from_session(session)]
        labeled = [case for case in cases if case.get("actual_release_ok") is not None]
        summary = self._summary(cases, labeled)
        gate_report = self._gate_report(cases, labeled)
        threshold_sweep = self._threshold_sweep(labeled)
        profile_patch = self._profile_patch(summary, gate_report)

        return {
            "mode": "production_aoi_outcome_calibration",
            "summary": summary,
            "gate_report": gate_report,
            "threshold_sweep": threshold_sweep,
            "recommended_profile_patch": profile_patch,
            "next_actions": self._next_actions(summary, gate_report),
            "cases": cases[:100],
            "claim_boundary": (
                "This report calibrates AOI release behavior only for sessions with production_aoi "
                "analysis and operator-recorded AOI truth. It is not a substitute for a line qualification "
                "study, GR&R, or destructive/functional validation."
            ),
        }

    def _cases_from_session(self, session: Dict[str, Any]) -> List[Dict[str, Any]]:
        analysis = self._latest_analysis(session)
        production_aoi = analysis.get("production_aoi") if isinstance(analysis.get("production_aoi"), dict) else {}
        if not production_aoi:
            return []
        outcomes = session.get("outcomes") if isinstance(session.get("outcomes"), list) else []
        truth = self._truth_from_outcomes(outcomes, str(session.get("route") or ""))
        gates = production_aoi.get("gates") if isinstance(production_aoi.get("gates"), list) else []
        release_authorized = bool(production_aoi.get("release_authorized"))
        actual_ok = truth.get("actual_release_ok")
        result_class = "unlabeled"
        if actual_ok is True and release_authorized:
            result_class = "true_release"
        elif actual_ok is False and release_authorized:
            result_class = "false_accept"
        elif actual_ok is True and not release_authorized:
            result_class = "false_reject"
        elif actual_ok is False and not release_authorized:
            result_class = "true_hold"

        return [
            {
                "session_id": session.get("session_id"),
                "title": session.get("title"),
                "route": session.get("route"),
                "disposition": production_aoi.get("disposition"),
                "release_authorized": release_authorized,
                "certainty_score": self._float(production_aoi.get("certainty_score"), 0.0),
                "certainty_level": production_aoi.get("certainty_level"),
                "blockers": production_aoi.get("blockers") or [],
                "gate_statuses": {
                    str(gate.get("gate_id")): str(gate.get("status"))
                    for gate in gates
                    if isinstance(gate, dict)
                },
                "failing_gates": [
                    str(gate.get("gate_id"))
                    for gate in gates
                    if isinstance(gate, dict) and str(gate.get("status")) in {"fail", "missing", "review"}
                ],
                "actual_status": truth.get("actual_status"),
                "actual_release_ok": actual_ok,
                "truth_source": truth.get("truth_source"),
                "result_class": result_class,
            }
        ]

    def _summary(self, cases: List[Dict[str, Any]], labeled: List[Dict[str, Any]]) -> Dict[str, Any]:
        predicted_release = [case for case in labeled if case.get("release_authorized")]
        actual_pass = [case for case in labeled if case.get("actual_release_ok") is True]
        false_accept = [case for case in labeled if case.get("result_class") == "false_accept"]
        false_reject = [case for case in labeled if case.get("result_class") == "false_reject"]
        true_release = [case for case in labeled if case.get("result_class") == "true_release"]
        true_hold = [case for case in labeled if case.get("result_class") == "true_hold"]
        precision = len(true_release) / max(len(predicted_release), 1)
        recall = len(true_release) / max(len(actual_pass), 1)
        false_accept_rate = len(false_accept) / max(len(predicted_release), 1)
        false_reject_rate = len(false_reject) / max(len(actual_pass), 1)
        readiness = self._readiness(len(labeled), len(false_accept), false_accept_rate, false_reject_rate)
        return {
            "candidate_case_count": len(cases),
            "labeled_case_count": len(labeled),
            "unlabeled_case_count": len(cases) - len(labeled),
            "predicted_release_count": len(predicted_release),
            "actual_pass_count": len(actual_pass),
            "true_release_count": len(true_release),
            "true_hold_count": len(true_hold),
            "false_accept_count": len(false_accept),
            "false_reject_count": len(false_reject),
            "release_precision": round(precision, 3),
            "release_recall": round(recall, 3),
            "false_accept_rate": round(false_accept_rate, 3),
            "false_reject_rate": round(false_reject_rate, 3),
            "readiness": readiness,
        }

    def _gate_report(self, cases: List[Dict[str, Any]], labeled: List[Dict[str, Any]]) -> Dict[str, Any]:
        status_counts: Dict[str, Dict[str, int]] = {}
        false_accept_gates: Dict[str, int] = {}
        false_reject_gates: Dict[str, int] = {}
        for case in cases:
            for gate_id, status in (case.get("gate_statuses") or {}).items():
                status_counts.setdefault(gate_id, {})
                status_counts[gate_id][status] = status_counts[gate_id].get(status, 0) + 1
        for case in labeled:
            target = None
            if case.get("result_class") == "false_accept":
                target = false_accept_gates
            elif case.get("result_class") == "false_reject":
                target = false_reject_gates
            if target is not None:
                for gate_id in case.get("failing_gates") or ["release_score"]:
                    target[gate_id] = target.get(gate_id, 0) + 1
        return {
            "gate_status_counts": status_counts,
            "false_accept_gate_counts": false_accept_gates,
            "false_reject_gate_counts": false_reject_gates,
            "recurring_blockers": self._top_counts(
                blocker
                for case in cases
                for blocker in (case.get("blockers") or [])
            ),
        }

    def _threshold_sweep(self, labeled: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        rows = []
        for value in range(70, 96, 5):
            threshold = value / 100.0
            predicted_release = [
                case
                for case in labeled
                if self._float(case.get("certainty_score"), 0.0) >= threshold
                and not case.get("failing_gates")
            ]
            true_release = [case for case in predicted_release if case.get("actual_release_ok") is True]
            false_accept = [case for case in predicted_release if case.get("actual_release_ok") is False]
            actual_pass = [case for case in labeled if case.get("actual_release_ok") is True]
            rows.append(
                {
                    "min_release_score": round(threshold, 2),
                    "predicted_release_count": len(predicted_release),
                    "false_accept_count": len(false_accept),
                    "false_accept_rate": round(len(false_accept) / max(len(predicted_release), 1), 3),
                    "release_recall": round(len(true_release) / max(len(actual_pass), 1), 3),
                }
            )
        return rows

    def _profile_patch(self, summary: Dict[str, Any], gate_report: Dict[str, Any]) -> Dict[str, Any]:
        defaults = ProductionAOICertaintyGate.DEFAULT_PROFILE
        patch: Dict[str, Any] = {
            "min_release_score": defaults["min_release_score"],
            "min_sampling_score": defaults["min_sampling_score"],
            "require_component_reference": True,
            "require_golden_reference": True,
            "require_topology_reference": True,
            "require_calibration": True,
        }
        notes = []
        if summary["labeled_case_count"] < 10:
            notes.append("collect at least 10 labeled AOI outcomes before relaxing any production gate")
        if summary["false_accept_count"] > 0:
            patch["min_release_score"] = min(0.95, round(float(defaults["min_release_score"]) + 0.04, 2))
            patch["min_sampling_score"] = min(0.9, round(float(defaults["min_sampling_score"]) + 0.04, 2))
            notes.append("false accept observed; tighten release/sampling thresholds and inspect escape case evidence")
        elif summary["labeled_case_count"] >= 20 and summary["false_reject_rate"] > 0.35:
            notes.append("false rejects are high with no false accepts; review recurring blockers before considering threshold changes")
        if gate_report.get("false_accept_gate_counts"):
            notes.append("audit gates involved in false accepts before authorizing automatic release")
        patch["review_notes"] = notes
        return patch

    def _next_actions(self, summary: Dict[str, Any], gate_report: Dict[str, Any]) -> List[str]:
        actions = []
        if summary["candidate_case_count"] == 0:
            actions.append("save AOI scan results as board sessions so production decisions can be calibrated")
        if summary["labeled_case_count"] < 10:
            actions.append("record AOI actual status on at least 10 inspected boards")
        if summary["false_accept_count"] > 0:
            actions.append("freeze automatic release for the affected line until false accept cases are reviewed")
        if summary["unlabeled_case_count"] > 0:
            actions.append("backfill actual pass/fail outcomes for unlabeled AOI sessions")
        if gate_report.get("recurring_blockers"):
            actions.append("work the top recurring AOI blockers first: " + ", ".join(item["item"] for item in gate_report["recurring_blockers"][:3]))
        if not actions:
            actions.append("continue collecting outcomes and rerun calibration before lowering capture or reference requirements")
        return actions

    def _readiness(self, labeled_count: int, false_accept_count: int, false_accept_rate: float, false_reject_rate: float) -> str:
        if false_accept_count > 0 or false_accept_rate > 0.0:
            return "unsafe_to_relax_release"
        if labeled_count < 10:
            return "insufficient_outcome_evidence"
        if labeled_count >= 30 and false_reject_rate <= 0.2:
            return "pilot_calibrated"
        return "calibration_needed"

    def _truth_from_outcomes(self, outcomes: List[Dict[str, Any]], route: str) -> Dict[str, Any]:
        for outcome in reversed(outcomes):
            if not isinstance(outcome, dict):
                continue
            truth = outcome.get("aoi_truth") if isinstance(outcome.get("aoi_truth"), dict) else {}
            production = outcome.get("production_result") if isinstance(outcome.get("production_result"), dict) else {}
            status = (
                outcome.get("aoi_actual_status")
                or outcome.get("actual_status")
                or truth.get("actual_status")
                or production.get("actual_status")
            )
            release_ok = self._optional_bool(
                outcome.get("aoi_release_ok", truth.get("release_ok", production.get("release_ok")))
            )
            if release_ok is None and status is not None:
                release_ok = self._status_to_bool(str(status))
            if release_ok is None and route == "aoi":
                release_ok = self._decision_to_bool(str(outcome.get("decision") or ""))
                status = status or outcome.get("decision")
            if release_ok is not None:
                return {
                    "actual_release_ok": release_ok,
                    "actual_status": str(status or ("pass" if release_ok else "fail")),
                    "truth_source": outcome.get("outcome_id"),
                }
        return {"actual_release_ok": None, "actual_status": None, "truth_source": None}

    def _latest_analysis(self, session: Dict[str, Any]) -> Dict[str, Any]:
        analyses = session.get("analyses") if isinstance(session.get("analyses"), list) else []
        if not analyses:
            return {}
        latest = analyses[-1] if isinstance(analyses[-1], dict) else {}
        return latest.get("results") if isinstance(latest.get("results"), dict) else {}

    def _status_to_bool(self, value: str) -> bool | None:
        key = value.strip().lower().replace(" ", "_").replace("-", "_")
        if key in self.PASS_STATUSES:
            return True
        if key in self.FAIL_STATUSES:
            return False
        return None

    def _decision_to_bool(self, value: str) -> bool | None:
        key = value.strip().lower().replace(" ", "_").replace("-", "_")
        if key in self.RELEASE_DECISIONS:
            return True
        if key in self.FAIL_DECISIONS:
            return False
        return None

    @staticmethod
    def _optional_bool(value: Any) -> bool | None:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            key = value.strip().lower()
            if key in {"true", "1", "yes", "y", "pass", "passed", "ok"}:
                return True
            if key in {"false", "0", "no", "n", "fail", "failed", "bad"}:
                return False
        return None

    @staticmethod
    def _top_counts(items: Iterable[Any]) -> List[Dict[str, Any]]:
        counts: Dict[str, int] = {}
        for item in items:
            text = str(item or "").strip()
            if not text:
                continue
            counts[text] = counts.get(text, 0) + 1
        return [
            {"item": item, "count": count}
            for item, count in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))[:10]
        ]

    @staticmethod
    def _float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
