"""Functional evaluation for real repair/salvage cases."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Sequence

from src.intelligence.board_session_store import BoardSessionStore
from src.intelligence.repair_encyclopedia import RepairEncyclopedia
from src.intelligence.repair_market_coverage import RepairMarketCoverage
from src.intelligence.repair_video_playbook import RepairVideoPlaybookBuilder


@dataclass
class RepairCase:
    case_id: str
    title: str
    device_hint: str
    symptoms: List[str]
    source_url: str
    source_kind: str = "repair_reference"
    observed_actions: List[str] = field(default_factory=list)
    notes: str = ""
    expected_lane: str = ""


class RepairCaseEvaluator:
    """Run sourced cases through market coverage, repair guide, playbook, and session loop."""

    def __init__(
        self,
        *,
        encyclopedia: RepairEncyclopedia | None = None,
        coverage: RepairMarketCoverage | None = None,
        playbook_builder: RepairVideoPlaybookBuilder | None = None,
        session_store: BoardSessionStore | None = None,
    ):
        self.encyclopedia = encyclopedia or RepairEncyclopedia()
        self.coverage = coverage or RepairMarketCoverage()
        self.playbook_builder = playbook_builder or RepairVideoPlaybookBuilder(self.encyclopedia)
        self.session_store = session_store or BoardSessionStore("data/repair_case_eval/sessions.json")

    def evaluate_cases(
        self,
        cases: Sequence[RepairCase | Dict[str, Any]],
        *,
        commit_sessions: bool = False,
    ) -> Dict[str, Any]:
        rows = [self.evaluate_case(case, commit_session=commit_sessions) for case in cases]
        solved = [row for row in rows if row["verdict"] == "solvable_now"]
        assistive = [row for row in rows if row["verdict"] == "assistive_only"]
        not_ready = [row for row in rows if row["verdict"] == "not_ready"]
        avg = round(sum(float(row["workflow_score"]) for row in rows) / max(len(rows), 1), 3)
        return {
            "mode": "real_repair_case_functional_eval",
            "summary": {
                "case_count": len(rows),
                "solvable_now": len(solved),
                "assistive_only": len(assistive),
                "not_ready": len(not_ready),
                "average_workflow_score": avg,
                "strongest_cases": [row["case_id"] for row in sorted(rows, key=lambda item: item["workflow_score"], reverse=True)[:3]],
                "weakest_cases": [row["case_id"] for row in sorted(rows, key=lambda item: item["workflow_score"])[:3]],
            },
            "cases": rows,
            "portfolio_after_cases": self.coverage.portfolio()["summary"],
            "next_builds": self._portfolio_next_builds(rows),
        }

    def evaluate_case(
        self,
        case: RepairCase | Dict[str, Any],
        *,
        commit_session: bool = False,
    ) -> Dict[str, Any]:
        record = self._coerce_case(case)
        query = " ".join([record.title, record.device_hint, *record.symptoms, record.notes])
        coverage = self.coverage.evaluate_text(query)
        guide = self.encyclopedia.generate(
            analysis={},
            symptoms=record.symptoms,
            device_hint=record.device_hint or record.title,
        )
        playbook = self.playbook_builder.build(
            video_reference={
                "title": record.title,
                "url": record.source_url,
                "notes": record.notes,
                "observed_actions": record.observed_actions,
            },
            analysis={},
            symptoms=record.symptoms,
            device_hint=record.device_hint,
        )
        route = "safety" if (guide.get("safety_profile") or {}).get("risk_level") == "high" else "repair"
        session = self.session_store.create_session(
            {
                "session_id": f"eval_{record.case_id}",
                "title": record.title,
                "description": record.notes or record.title,
                "device_hint": record.device_hint,
                "symptoms": record.symptoms,
                "route": route,
                "repair_guide": guide,
                "coverage": coverage,
                "source": "real_repair_case_eval",
            },
            user_id="case-evaluator",
            commit=commit_session,
        )
        score = self._workflow_score(coverage, guide, playbook, session)
        blockers = self._blockers(record, coverage, guide, playbook, session)
        verdict = self._verdict(score, blockers)
        top_match = (coverage.get("top_matches") or [{}])[0]
        top_fault = (guide.get("fault_candidates") or [{}])[0]
        return {
            "case_id": record.case_id,
            "title": record.title,
            "source_url": record.source_url,
            "expected_lane": record.expected_lane,
            "coverage": {
                "matched": coverage.get("matched"),
                "top_item": top_match.get("item_id"),
                "top_label": top_match.get("label"),
                "coverage_level": top_match.get("coverage_level"),
                "coverage": top_match.get("coverage"),
                "strategic_score": top_match.get("strategic_score"),
            },
            "repair_guide": {
                "family": (guide.get("device_family") or {}).get("id"),
                "family_label": (guide.get("device_family") or {}).get("label"),
                "confidence": guide.get("confidence"),
                "safety_risk": (guide.get("safety_profile") or {}).get("risk_level"),
                "top_fault": top_fault.get("fault_id"),
                "top_fault_name": top_fault.get("name"),
                "top_fault_likelihood": top_fault.get("likelihood"),
                "diagnostic_step_count": len(guide.get("diagnostic_flow") or []),
                "evidence_next_count": len(guide.get("evidence_to_collect_next") or []),
            },
            "playbook": {
                "pattern": (playbook.get("video_pattern") or {}).get("id"),
                "pattern_label": (playbook.get("video_pattern") or {}).get("label"),
                "can_follow_score": playbook.get("can_follow_score"),
                "capture_checklist_count": len(playbook.get("operator_capture_checklist") or []),
                "quality_gate_count": len(playbook.get("quality_gates") or []),
            },
            "board_session": {
                "session_id": session.get("session_id"),
                "route": session.get("route"),
                "task_count": (session.get("metrics") or {}).get("task_count"),
                "capture_burden": (session.get("metrics") or {}).get("capture_burden"),
                "measurement_count_required": (session.get("metrics") or {}).get("measurement_count_required"),
                "first_tasks": [
                    {"type": task.get("type"), "prompt": task.get("prompt")}
                    for task in (session.get("evidence_tasks") or [])[:5]
                ],
            },
            "workflow_score": score,
            "verdict": verdict,
            "blockers": blockers,
            "recommended_next_builds": self._case_next_builds(record, coverage, guide, blockers),
        }

    def render_markdown(self, report: Dict[str, Any]) -> str:
        summary = report.get("summary") or {}
        lines = [
            "# Real Repair Case Functional Evaluation",
            "",
            f"- Cases: {summary.get('case_count', 0)}",
            f"- Solvable now: {summary.get('solvable_now', 0)}",
            f"- Assistive only: {summary.get('assistive_only', 0)}",
            f"- Not ready: {summary.get('not_ready', 0)}",
            f"- Average workflow score: {summary.get('average_workflow_score', 0)}",
            "",
            "## Cases",
        ]
        for row in report.get("cases") or []:
            guide = row.get("repair_guide") or {}
            session = row.get("board_session") or {}
            lines.extend(
                [
                    "",
                    f"### {row.get('title')}",
                    "",
                    f"- Source: {row.get('source_url')}",
                    f"- Verdict: `{row.get('verdict')}` score `{row.get('workflow_score')}`",
                    f"- Lane: `{guide.get('family')}` / top fault `{guide.get('top_fault')}`",
                    f"- Coverage: `{(row.get('coverage') or {}).get('coverage_level')}`",
                    f"- Safety: `{guide.get('safety_risk')}`",
                    f"- Session tasks: `{session.get('task_count')}`, captures `{session.get('capture_burden')}`, measurements `{session.get('measurement_count_required')}`",
                    f"- Blockers: {', '.join(row.get('blockers') or []) or 'none'}",
                ]
            )
            for task in (session.get("first_tasks") or [])[:3]:
                lines.append(f"- First task: [{task.get('type')}] {task.get('prompt')}")
        lines.extend(["", "## Next Builds"])
        for item in report.get("next_builds") or []:
            lines.append(f"- {item}")
        lines.append("")
        return "\n".join(lines)

    def _workflow_score(
        self,
        coverage: Dict[str, Any],
        guide: Dict[str, Any],
        playbook: Dict[str, Any],
        session: Dict[str, Any],
    ) -> float:
        top_match = (coverage.get("top_matches") or [{}])[0]
        top_fault = (guide.get("fault_candidates") or [{}])[0]
        coverage_score = float(top_match.get("coverage", 0.0) or 0.0)
        guide_score = float(guide.get("confidence", 0.0) or 0.0)
        fault_score = float(top_fault.get("likelihood", 0.0) or 0.0)
        playbook_score = float(playbook.get("can_follow_score", 0.0) or 0.0)
        metrics = session.get("metrics") or {}
        task_count = float(metrics.get("task_count", 0) or 0)
        capture_burden = float(metrics.get("capture_burden", 0) or 0)
        task_score = min(task_count / 6.0, 1.0) * (1.0 if capture_burden <= 6 else 0.75)
        safety = guide.get("safety_profile") or {}
        safety_score = 1.0
        if safety.get("risk_level") == "high":
            rules = " ".join(safety.get("rules") or [])
            safety_score = 0.8 if ("discharge" in rules or "mains" in rules or "high-voltage" in rules) else 0.45
        return round(
            0.22 * coverage_score
            + 0.22 * guide_score
            + 0.20 * fault_score
            + 0.16 * playbook_score
            + 0.12 * task_score
            + 0.08 * safety_score,
            3,
        )

    def _verdict(self, score: float, blockers: List[str]) -> str:
        hard_blockers = [blocker for blocker in blockers if blocker.startswith("hard:")]
        assistive_caps = [
            "trained safety workflow required",
            "boardview/schematic and model-specific teardown",
            "model-specific knowledge required",
        ]
        if any(any(marker in blocker for marker in assistive_caps) for blocker in blockers):
            return "assistive_only" if score >= 0.45 and not hard_blockers else "not_ready"
        if score >= 0.68 and not hard_blockers:
            return "solvable_now"
        if score >= 0.45:
            return "assistive_only"
        return "not_ready"

    def _blockers(
        self,
        case: RepairCase,
        coverage: Dict[str, Any],
        guide: Dict[str, Any],
        playbook: Dict[str, Any],
        session: Dict[str, Any],
    ) -> List[str]:
        blockers: List[str] = []
        top_match = (coverage.get("top_matches") or [{}])[0]
        coverage_score = float(top_match.get("coverage", 0.0) or 0.0)
        if coverage_score < 0.35:
            blockers.append("hard: item class is weakly covered")
        elif coverage_score < 0.55:
            blockers.append("model-specific knowledge required before customer-facing claim")
        if not (guide.get("fault_candidates") or []):
            blockers.append("hard: no fault candidate generated")
        if float(guide.get("confidence", 0.0) or 0.0) < 0.45:
            blockers.append("low guide confidence without board photos or measurements")
        safety = guide.get("safety_profile") or {}
        if safety.get("risk_level") == "high":
            blockers.append("trained safety workflow required for high-voltage or mains portions")
        if (session.get("metrics") or {}).get("task_count", 0) == 0:
            blockers.append("hard: no board-session evidence tasks generated")
        if float(playbook.get("can_follow_score", 0.0) or 0.0) < 0.5:
            blockers.append("video-to-playbook support is weak without more observed actions")
        if "laptop" in f"{case.title} {case.device_hint}".lower():
            blockers.append("boardview/schematic and model-specific teardown needed for deeper board repair")
        return list(dict.fromkeys(blockers))

    def _case_next_builds(
        self,
        case: RepairCase,
        coverage: Dict[str, Any],
        guide: Dict[str, Any],
        blockers: List[str],
    ) -> List[str]:
        text = f"{case.title} {case.device_hint} {' '.join(case.symptoms)}".lower()
        builds = []
        if "stick" in text or "controller" in text:
            builds.append("controller calibration and stick-module compatibility database")
        if "battery" in text or "charging" in text or "charge" in text:
            builds.append("battery chemistry, pack safety, and replacement compatibility workflow")
        if "coffee" in text or "heating" in text:
            builds.append("mains heater appliance safety pack with thermal fuse/element rating tables")
        if "tv" in text or "backlight" in text:
            builds.append("TV model rail/backlight LED-strip reference library")
        if "laptop" in text or "macbook" in text:
            builds.append("laptop boardview/schematic connector for power-path diagnosis")
        if blockers:
            builds.append("collect board photos, measurements, and outcome data for this lane")
        if not builds:
            builds.append("add more sourced cases and outcome measurements for this item class")
        return list(dict.fromkeys(builds))

    def _portfolio_next_builds(self, rows: List[Dict[str, Any]]) -> List[str]:
        counts: Dict[str, int] = {}
        for row in rows:
            for item in row.get("recommended_next_builds") or []:
                counts[item] = counts.get(item, 0) + 1
        return [
            item
            for item, _ in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
        ][:8]

    def _coerce_case(self, case: RepairCase | Dict[str, Any]) -> RepairCase:
        if isinstance(case, RepairCase):
            return case
        payload = dict(case)
        return RepairCase(
            case_id=str(payload.get("case_id") or payload.get("id") or "case"),
            title=str(payload.get("title") or "Untitled case"),
            device_hint=str(payload.get("device_hint") or ""),
            symptoms=[str(item) for item in payload.get("symptoms", []) or []],
            source_url=str(payload.get("source_url") or payload.get("url") or ""),
            source_kind=str(payload.get("source_kind") or "repair_reference"),
            observed_actions=[str(item) for item in payload.get("observed_actions", []) or []],
            notes=str(payload.get("notes") or ""),
            expected_lane=str(payload.get("expected_lane") or ""),
        )

    @staticmethod
    def serialize_cases(cases: Sequence[RepairCase]) -> List[Dict[str, Any]]:
        return [asdict(case) for case in cases]
