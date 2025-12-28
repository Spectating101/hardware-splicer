"""
Defect Severity Scoring and Quality Assessment

Analyzes detected defects and produces overall board quality score with actionable recommendations.

Author: Dum-E Intelligence System
Version: 1.0.0
"""

import logging
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class SeverityLevel(Enum):
    """Defect severity classification"""
    CRITICAL = 1.0  # Immediate failure risk (shorts, opens)
    HIGH = 0.75  # Component damage, likely to fail
    MEDIUM = 0.5  # Solder quality issues, may degrade
    LOW = 0.25  # Cosmetic, unlikely to affect function


@dataclass
class QualityAssessment:
    """Overall board quality assessment"""
    overall_score: float  # 0.0-1.0 (0=catastrophic, 1=perfect)
    pass_fail: bool
    defect_count: int
    critical_defects: int
    high_defects: int
    medium_defects: int
    low_defects: int
    actionable_repairs: List[str] = field(default_factory=list)
    detailed_report: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class DefectScorer:
    """
    Scores PCB quality based on detected defects.

    Produces:
    - Overall quality score (0-1)
    - Pass/fail decision
    - Prioritized repair actions
    - Detailed quality report
    """

    # Defect severity thresholds
    CRITICAL_THRESHOLD = 0.85
    HIGH_THRESHOLD = 0.65
    MEDIUM_THRESHOLD = 0.40

    # Quality score thresholds
    PASSING_SCORE = 0.70  # Below this = fail
    EXCELLENT_SCORE = 0.90  # Above this = excellent

    def __init__(self, passing_threshold: float = 0.70):
        """
        Initialize defect scorer.

        Args:
            passing_threshold: Minimum score to pass quality check (default: 0.70)
        """
        self.passing_threshold = passing_threshold

    def score(self, defects: List[Any]) -> QualityAssessment:
        """
        Score board quality based on defects.

        Args:
            defects: List of DefectDetection objects

        Returns:
            QualityAssessment with overall score and recommendations
        """
        if not defects:
            return QualityAssessment(
                overall_score=1.0,
                pass_fail=True,
                defect_count=0,
                critical_defects=0,
                high_defects=0,
                medium_defects=0,
                low_defects=0,
                detailed_report="No defects detected. Board appears pristine."
            )

        # Categorize defects by severity
        critical, high, medium, low = self._categorize_defects(defects)

        # Calculate overall score
        overall_score = self._calculate_score(critical, high, medium, low)

        # Generate repair recommendations
        repairs = self._prioritize_repairs(defects, critical, high, medium)

        # Generate detailed report
        report = self._generate_report(defects, critical, high, medium, low, overall_score)

        # Pass/fail decision
        pass_fail = overall_score >= self.passing_threshold and len(critical) == 0

        assessment = QualityAssessment(
            overall_score=overall_score,
            pass_fail=pass_fail,
            defect_count=len(defects),
            critical_defects=len(critical),
            high_defects=len(high),
            medium_defects=len(medium),
            low_defects=len(low),
            actionable_repairs=repairs,
            detailed_report=report,
            metadata={
                "passing_threshold": self.passing_threshold,
                "defect_breakdown": {
                    "critical": [d.defect_type for d in critical],
                    "high": [d.defect_type for d in high],
                    "medium": [d.defect_type for d in medium],
                    "low": [d.defect_type for d in low]
                }
            }
        )

        logger.info(f"Quality score: {overall_score:.2f} | Pass: {pass_fail} | Defects: {len(defects)}")
        return assessment

    def _categorize_defects(self, defects: List[Any]) -> Tuple[List, List, List, List]:
        """Categorize defects by severity level"""
        critical = []
        high = []
        medium = []
        low = []

        for defect in defects:
            severity = defect.severity

            if severity >= self.CRITICAL_THRESHOLD:
                critical.append(defect)
            elif severity >= self.HIGH_THRESHOLD:
                high.append(defect)
            elif severity >= self.MEDIUM_THRESHOLD:
                medium.append(defect)
            else:
                low.append(defect)

        return critical, high, medium, low

    def _calculate_score(
        self,
        critical: List,
        high: List,
        medium: List,
        low: List
    ) -> float:
        """
        Calculate overall quality score.

        Scoring formula:
        - Start at 1.0 (perfect)
        - Each critical defect: -0.30
        - Each high defect: -0.15
        - Each medium defect: -0.05
        - Each low defect: -0.01
        - Floor at 0.0
        """
        score = 1.0

        score -= len(critical) * 0.30
        score -= len(high) * 0.15
        score -= len(medium) * 0.05
        score -= len(low) * 0.01

        return max(0.0, score)

    def _prioritize_repairs(
        self,
        all_defects: List[Any],
        critical: List,
        high: List,
        medium: List
    ) -> List[str]:
        """
        Generate prioritized repair action list.

        Returns:
            List of repair actions ordered by priority
        """
        repairs = []

        # Critical defects first (must fix immediately)
        if critical:
            repairs.append("=" * 60)
            repairs.append("CRITICAL DEFECTS (FIX IMMEDIATELY):")
            repairs.append("=" * 60)
            for i, defect in enumerate(critical, 1):
                repairs.append(f"{i}. [{defect.defect_type.upper()}] @ {defect.bbox[:2]}")
                repairs.append(f"   Action: {defect.repair_action}")
                repairs.append(f"   Risk: Board may not function properly")
                repairs.append("")

        # High severity defects
        if high:
            repairs.append("=" * 60)
            repairs.append("HIGH SEVERITY DEFECTS (FIX SOON):")
            repairs.append("=" * 60)
            for i, defect in enumerate(high, 1):
                repairs.append(f"{i}. [{defect.defect_type}] @ {defect.bbox[:2]}")
                repairs.append(f"   Action: {defect.repair_action}")
                repairs.append("")

        # Medium severity defects
        if medium:
            repairs.append("=" * 60)
            repairs.append("MEDIUM SEVERITY DEFECTS (RECOMMENDED):")
            repairs.append("=" * 60)
            for i, defect in enumerate(medium[:5], 1):  # Limit to top 5
                repairs.append(f"{i}. [{defect.defect_type}] @ {defect.bbox[:2]}")
                repairs.append(f"   Action: {defect.repair_action}")

            if len(medium) > 5:
                repairs.append(f"   ... and {len(medium) - 5} more medium-severity defects")
            repairs.append("")

        return repairs

    def _generate_report(
        self,
        defects: List[Any],
        critical: List,
        high: List,
        medium: List,
        low: List,
        score: float
    ) -> str:
        """Generate human-readable quality report"""
        lines = []

        lines.append("=" * 70)
        lines.append("PCB QUALITY ASSESSMENT REPORT")
        lines.append("=" * 70)
        lines.append("")

        # Overall score
        lines.append(f"Overall Score: {score:.2f}/1.00")

        if score >= self.EXCELLENT_SCORE:
            grade = "EXCELLENT"
        elif score >= self.passing_threshold:
            grade = "PASS"
        elif score >= 0.5:
            grade = "MARGINAL"
        else:
            grade = "FAIL"

        lines.append(f"Grade: {grade}")
        lines.append("")

        # Defect summary
        lines.append("Defect Summary:")
        lines.append(f"  Total Defects: {len(defects)}")
        lines.append(f"  Critical: {len(critical)}")
        lines.append(f"  High: {len(high)}")
        lines.append(f"  Medium: {len(medium)}")
        lines.append(f"  Low: {len(low)}")
        lines.append("")

        # Decision
        if len(critical) > 0:
            lines.append("DECISION: REJECT - Critical defects present")
            lines.append("  Board requires immediate repair before use.")
        elif score < self.passing_threshold:
            lines.append("DECISION: REJECT - Quality below threshold")
            lines.append(f"  Score {score:.2f} < {self.passing_threshold:.2f}")
        else:
            lines.append("DECISION: ACCEPT - Quality meets requirements")
            if len(high) > 0 or len(medium) > 0:
                lines.append("  Note: Some defects present but non-critical.")

        lines.append("")

        # Defect type breakdown
        if defects:
            defect_types = {}
            for d in defects:
                defect_types[d.defect_type] = defect_types.get(d.defect_type, 0) + 1

            lines.append("Defect Type Breakdown:")
            for dtype, count in sorted(defect_types.items(), key=lambda x: -x[1]):
                lines.append(f"  {dtype}: {count}")

        lines.append("")
        lines.append("=" * 70)

        return "\n".join(lines)

    def get_severity_level(self, severity_score: float) -> SeverityLevel:
        """Convert numerical severity to enum"""
        if severity_score >= self.CRITICAL_THRESHOLD:
            return SeverityLevel.CRITICAL
        elif severity_score >= self.HIGH_THRESHOLD:
            return SeverityLevel.HIGH
        elif severity_score >= self.MEDIUM_THRESHOLD:
            return SeverityLevel.MEDIUM
        else:
            return SeverityLevel.LOW

    def export_to_dict(self, assessment: QualityAssessment) -> Dict[str, Any]:
        """Export assessment to dictionary for JSON serialization"""
        return {
            "overall_score": assessment.overall_score,
            "pass_fail": assessment.pass_fail,
            "grade": "EXCELLENT" if assessment.overall_score >= self.EXCELLENT_SCORE
                else "PASS" if assessment.pass_fail
                else "FAIL",
            "defect_summary": {
                "total": assessment.defect_count,
                "critical": assessment.critical_defects,
                "high": assessment.high_defects,
                "medium": assessment.medium_defects,
                "low": assessment.low_defects
            },
            "actionable_repairs": assessment.actionable_repairs,
            "detailed_report": assessment.detailed_report,
            "metadata": assessment.metadata
        }


if __name__ == "__main__":
    # Example usage
    from vision.defect_detector import DefectDetection

    # Create sample defects
    defects = [
        DefectDetection(
            defect_type="solder_bridge",
            bbox=[100, 200, 120, 210],
            confidence=0.92,
            severity=0.90,
            repair_action="Remove excess solder with wick"
        ),
        DefectDetection(
            defect_type="cold_joint",
            bbox=[300, 400, 310, 410],
            confidence=0.75,
            severity=0.60,
            repair_action="Reheat with fresh flux"
        ),
        DefectDetection(
            defect_type="corrosion",
            bbox=[500, 600, 520, 620],
            confidence=0.65,
            severity=0.50,
            repair_action="Clean with IPA"
        )
    ]

    scorer = DefectScorer()
    assessment = scorer.score(defects)

    print(assessment.detailed_report)
    print("\nRepair Actions:")
    for action in assessment.actionable_repairs:
        print(action)
