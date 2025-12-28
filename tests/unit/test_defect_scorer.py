"""
Unit tests for defect scoring and quality assessment module.

Tests quality score calculation, severity categorization, and repair prioritization.
"""

import pytest
from dataclasses import dataclass

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from intelligence.defect_scorer import DefectScorer, QualityAssessment, SeverityLevel
from vision.defect_detector import DefectDetection


@pytest.fixture
def scorer():
    """Create scorer instance with default threshold."""
    return DefectScorer(passing_threshold=0.70)


@pytest.fixture
def critical_defect():
    """Create a critical severity defect."""
    return DefectDetection(
        defect_type="short_circuit",
        bbox=[100, 200, 120, 210],
        confidence=0.95,
        severity=0.90,
        repair_action="Isolate and remove short"
    )


@pytest.fixture
def high_defect():
    """Create a high severity defect."""
    return DefectDetection(
        defect_type="solder_bridge",
        bbox=[200, 300, 220, 310],
        confidence=0.85,
        severity=0.75,
        repair_action="Remove excess solder with wick"
    )


@pytest.fixture
def medium_defect():
    """Create a medium severity defect."""
    return DefectDetection(
        defect_type="cold_joint",
        bbox=[300, 400, 310, 410],
        confidence=0.70,
        severity=0.50,
        repair_action="Reheat with fresh flux"
    )


@pytest.fixture
def low_defect():
    """Create a low severity defect."""
    return DefectDetection(
        defect_type="corrosion",
        bbox=[400, 500, 420, 520],
        confidence=0.60,
        severity=0.20,
        repair_action="Clean with IPA"
    )


class TestScorerInit:
    """Test scorer initialization."""

    def test_init_default_threshold(self):
        """Test initialization with default passing threshold."""
        scorer = DefectScorer()
        assert scorer.passing_threshold == 0.70

    def test_init_custom_threshold(self):
        """Test initialization with custom passing threshold."""
        scorer = DefectScorer(passing_threshold=0.85)
        assert scorer.passing_threshold == 0.85

    def test_severity_thresholds_are_valid(self):
        """Test that severity thresholds are in correct order."""
        scorer = DefectScorer()
        assert scorer.CRITICAL_THRESHOLD > scorer.HIGH_THRESHOLD
        assert scorer.HIGH_THRESHOLD > scorer.MEDIUM_THRESHOLD
        assert scorer.MEDIUM_THRESHOLD > 0.0


class TestQualityScoring:
    """Test quality score calculation."""

    def test_score_perfect_board(self, scorer):
        """Test scoring with no defects."""
        assessment = scorer.score([])

        assert assessment.overall_score == 1.0
        assert assessment.pass_fail is True
        assert assessment.defect_count == 0
        assert assessment.critical_defects == 0
        assert "pristine" in assessment.detailed_report.lower()

    def test_score_with_one_critical_defect(self, scorer, critical_defect):
        """Test scoring with one critical defect."""
        assessment = scorer.score([critical_defect])

        # One critical defect: 1.0 - 0.30 = 0.70
        assert assessment.overall_score == 0.70
        assert assessment.pass_fail is False  # Critical defects always fail
        assert assessment.critical_defects == 1
        assert assessment.defect_count == 1

    def test_score_with_one_high_defect(self, scorer, high_defect):
        """Test scoring with one high severity defect."""
        assessment = scorer.score([high_defect])

        # One high defect: 1.0 - 0.15 = 0.85
        assert assessment.overall_score == 0.85
        assert assessment.pass_fail is True  # No critical defects and score > 0.70
        assert assessment.high_defects == 1

    def test_score_with_multiple_defects(self, scorer, critical_defect, high_defect, medium_defect, low_defect):
        """Test scoring with multiple defects of varying severity."""
        defects = [critical_defect, high_defect, medium_defect, low_defect]
        assessment = scorer.score(defects)

        # Expected: 1.0 - 0.30 - 0.15 - 0.05 - 0.01 = 0.49
        assert abs(assessment.overall_score - 0.49) < 0.01
        assert assessment.pass_fail is False  # Has critical defect
        assert assessment.defect_count == 4
        assert assessment.critical_defects == 1
        assert assessment.high_defects == 1
        assert assessment.medium_defects == 1
        assert assessment.low_defects == 1

    def test_score_with_many_medium_defects(self, scorer, medium_defect):
        """Test scoring with many medium severity defects."""
        defects = [medium_defect] * 10  # 10 medium defects

        assessment = scorer.score(defects)

        # Expected: 1.0 - (10 * 0.05) = 0.50
        assert abs(assessment.overall_score - 0.50) < 0.01
        assert assessment.pass_fail is False  # Below 0.70 threshold
        assert assessment.medium_defects == 10

    def test_score_floors_at_zero(self, scorer, critical_defect):
        """Test that score doesn't go below 0.0."""
        defects = [critical_defect] * 10  # Many critical defects

        assessment = scorer.score(defects)

        # Should floor at 0.0
        assert assessment.overall_score >= 0.0
        assert assessment.overall_score <= 1.0
        assert assessment.pass_fail is False


class TestDefectCategorization:
    """Test defect categorization by severity."""

    def test_categorize_critical_defect(self, scorer, critical_defect):
        """Test that critical defects are categorized correctly."""
        critical, high, medium, low = scorer._categorize_defects([critical_defect])

        assert len(critical) == 1
        assert len(high) == 0
        assert len(medium) == 0
        assert len(low) == 0

    def test_categorize_high_defect(self, scorer, high_defect):
        """Test that high defects are categorized correctly."""
        critical, high, medium, low = scorer._categorize_defects([high_defect])

        assert len(critical) == 0
        assert len(high) == 1
        assert len(medium) == 0
        assert len(low) == 0

    def test_categorize_medium_defect(self, scorer, medium_defect):
        """Test that medium defects are categorized correctly."""
        critical, high, medium, low = scorer._categorize_defects([medium_defect])

        assert len(critical) == 0
        assert len(high) == 0
        assert len(medium) == 1
        assert len(low) == 0

    def test_categorize_low_defect(self, scorer, low_defect):
        """Test that low defects are categorized correctly."""
        critical, high, medium, low = scorer._categorize_defects([low_defect])

        assert len(critical) == 0
        assert len(high) == 0
        assert len(medium) == 0
        assert len(low) == 1

    def test_categorize_mixed_defects(self, scorer, critical_defect, high_defect, medium_defect, low_defect):
        """Test categorization of mixed severity defects."""
        defects = [critical_defect, high_defect, medium_defect, low_defect]
        critical, high, medium, low = scorer._categorize_defects(defects)

        assert len(critical) == 1
        assert len(high) == 1
        assert len(medium) == 1
        assert len(low) == 1


class TestRepairPrioritization:
    """Test repair action prioritization."""

    def test_prioritize_critical_first(self, scorer, critical_defect, medium_defect):
        """Test that critical defects are prioritized first."""
        defects = [medium_defect, critical_defect]  # Order shouldn't matter
        critical, high, medium, low = scorer._categorize_defects(defects)

        repairs = scorer._prioritize_repairs(defects, critical, high, medium)

        # Critical should appear before medium in repair list
        repairs_text = "\n".join(repairs)
        critical_index = repairs_text.find("CRITICAL")
        medium_index = repairs_text.find("MEDIUM")

        assert critical_index < medium_index
        assert "FIX IMMEDIATELY" in repairs_text

    def test_repair_actions_include_defect_info(self, scorer, high_defect):
        """Test that repair actions include defect details."""
        critical, high, medium, low = scorer._categorize_defects([high_defect])
        repairs = scorer._prioritize_repairs([high_defect], critical, high, medium)

        repairs_text = "\n".join(repairs)

        assert "solder_bridge" in repairs_text
        assert "Remove excess solder with wick" in repairs_text

    def test_medium_defects_limited_to_five(self, scorer, medium_defect):
        """Test that medium defects are limited to top 5 in repair list."""
        defects = [medium_defect] * 10
        critical, high, medium, low = scorer._categorize_defects(defects)

        repairs = scorer._prioritize_repairs(defects, critical, high, medium)
        repairs_text = "\n".join(repairs)

        # Should mention "5 more" or similar
        assert "5 more" in repairs_text or "and 5 more" in repairs_text


class TestQualityReport:
    """Test quality report generation."""

    def test_report_shows_overall_score(self, scorer, high_defect):
        """Test that report includes overall score."""
        assessment = scorer.score([high_defect])

        assert f"{assessment.overall_score:.2f}" in assessment.detailed_report
        assert "Overall Score" in assessment.detailed_report

    def test_report_shows_grade(self, scorer, high_defect):
        """Test that report includes grade."""
        assessment = scorer.score([high_defect])

        # Score is 0.85, should be PASS
        assert "PASS" in assessment.detailed_report

    def test_report_shows_defect_breakdown(self, scorer, critical_defect, medium_defect):
        """Test that report includes defect breakdown."""
        defects = [critical_defect, medium_defect]
        assessment = scorer.score(defects)

        assert "Critical: 1" in assessment.detailed_report
        assert "Medium: 1" in assessment.detailed_report
        assert "Total Defects: 2" in assessment.detailed_report

    def test_report_shows_decision(self, scorer, critical_defect):
        """Test that report includes pass/fail decision."""
        assessment = scorer.score([critical_defect])

        assert "DECISION" in assessment.detailed_report
        assert "REJECT" in assessment.detailed_report

    def test_report_grade_excellent(self, scorer):
        """Test that excellent boards get EXCELLENT grade."""
        # Create very minor defect
        minor_defect = DefectDetection("corrosion", [100, 100, 110, 110], 0.5, 0.10, "Clean")
        assessment = scorer.score([minor_defect])

        # Score should be 0.99 (1.0 - 0.01)
        assert assessment.overall_score >= 0.90
        assert "EXCELLENT" in assessment.detailed_report

    def test_report_grade_fail(self, scorer, critical_defect):
        """Test that failing boards get FAIL grade."""
        defects = [critical_defect] * 3  # Multiple critical defects
        assessment = scorer.score(defects)

        assert assessment.overall_score < 0.70
        assert assessment.pass_fail is False


class TestSeverityLevelEnum:
    """Test SeverityLevel enum."""

    def test_get_severity_level_critical(self, scorer):
        """Test mapping to CRITICAL severity level."""
        level = scorer.get_severity_level(0.90)
        assert level == SeverityLevel.CRITICAL

    def test_get_severity_level_high(self, scorer):
        """Test mapping to HIGH severity level."""
        level = scorer.get_severity_level(0.70)
        assert level == SeverityLevel.HIGH

    def test_get_severity_level_medium(self, scorer):
        """Test mapping to MEDIUM severity level."""
        level = scorer.get_severity_level(0.50)
        assert level == SeverityLevel.MEDIUM

    def test_get_severity_level_low(self, scorer):
        """Test mapping to LOW severity level."""
        level = scorer.get_severity_level(0.20)
        assert level == SeverityLevel.LOW


class TestExportToDict:
    """Test exporting assessment to dictionary."""

    def test_export_includes_all_fields(self, scorer, high_defect):
        """Test that export includes all required fields."""
        assessment = scorer.score([high_defect])
        export = scorer.export_to_dict(assessment)

        assert "overall_score" in export
        assert "pass_fail" in export
        assert "grade" in export
        assert "defect_summary" in export
        assert "actionable_repairs" in export
        assert "detailed_report" in export
        assert "metadata" in export

    def test_export_defect_summary_structure(self, scorer, critical_defect, medium_defect):
        """Test that defect summary has proper structure."""
        defects = [critical_defect, medium_defect]
        assessment = scorer.score(defects)
        export = scorer.export_to_dict(assessment)

        summary = export["defect_summary"]
        assert summary["total"] == 2
        assert summary["critical"] == 1
        assert summary["medium"] == 1

    def test_export_grade_mapping(self, scorer, high_defect):
        """Test that grade is correctly mapped in export."""
        assessment = scorer.score([high_defect])
        export = scorer.export_to_dict(assessment)

        # Score is 0.85, should be PASS
        assert export["grade"] == "PASS"


class TestPassFailLogic:
    """Test pass/fail decision logic."""

    def test_fail_with_critical_defect_even_if_high_score(self, scorer):
        """Test that critical defects always cause failure."""
        # Create defect that's just barely critical (0.85)
        barely_critical = DefectDetection(
            "short_circuit", [100, 100, 110, 110], 0.9, 0.85, "Fix short"
        )
        assessment = scorer.score([barely_critical])

        # Score is 0.70 (at threshold) but should still fail due to critical defect
        assert assessment.pass_fail is False

    def test_pass_with_score_at_threshold(self, scorer, medium_defect):
        """Test pass when score exactly at threshold."""
        # Need score of exactly 0.70
        # 1.0 - 0.30 = 0.70, so we need 1 critical OR 2 high OR 6 medium
        defects = [medium_defect] * 6
        assessment = scorer.score(defects)

        # Score is 0.70, no critical defects
        assert abs(assessment.overall_score - 0.70) < 0.01
        assert assessment.pass_fail is True  # Exactly at threshold

    def test_fail_just_below_threshold(self, scorer, medium_defect):
        """Test fail when score just below threshold."""
        defects = [medium_defect] * 7  # Score: 1.0 - 0.35 = 0.65
        assessment = scorer.score(defects)

        assert assessment.overall_score < 0.70
        assert assessment.pass_fail is False


class TestQualityAssessmentDataclass:
    """Test QualityAssessment dataclass."""

    def test_quality_assessment_creation(self):
        """Test creating QualityAssessment object."""
        assessment = QualityAssessment(
            overall_score=0.85,
            pass_fail=True,
            defect_count=2,
            critical_defects=0,
            high_defects=1,
            medium_defects=1,
            low_defects=0,
            actionable_repairs=["Fix solder bridge"],
            detailed_report="Quality report here"
        )

        assert assessment.overall_score == 0.85
        assert assessment.pass_fail is True
        assert assessment.defect_count == 2
        assert len(assessment.actionable_repairs) == 1

    def test_quality_assessment_default_fields(self):
        """Test QualityAssessment with default fields."""
        assessment = QualityAssessment(
            overall_score=1.0,
            pass_fail=True,
            defect_count=0,
            critical_defects=0,
            high_defects=0,
            medium_defects=0,
            low_defects=0
        )

        # Default fields should be empty
        assert assessment.actionable_repairs == []
        assert assessment.detailed_report == ""
        assert assessment.metadata == {}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
