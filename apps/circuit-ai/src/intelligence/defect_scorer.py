#!/usr/bin/env python3
"""
Defect Scoring Engine
Scores and prioritizes detected defects for repair guidance
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum


class DefectSeverity(Enum):
    """Defect severity levels."""
    CRITICAL = "critical"      # Board won't work, immediate fix needed
    HIGH = "high"              # Major functionality impaired
    MEDIUM = "medium"          # Reduced performance/reliability
    LOW = "low"                # Cosmetic or minor issues
    INFORMATIONAL = "info"     # Not a defect, just information


class DefectCategory(Enum):
    """Categories of PCB defects."""
    SOLDER = "solder"                    # Solder joint issues
    COMPONENT = "component"              # Component placement/orientation
    TRACE = "trace"                      # PCB trace damage
    BURN = "burn"                        # Thermal damage
    CORROSION = "corrosion"              # Chemical/moisture damage
    MECHANICAL = "mechanical"            # Physical damage
    CONTAMINATION = "contamination"      # Flux residue, dirt, etc.


@dataclass
class DefectScore:
    """Scored defect with repair priority."""
    defect_type: str
    severity: DefectSeverity
    category: DefectCategory
    confidence: float
    location: Dict[str, float]  # {x, y, width, height}
    repair_priority: int        # 1-10, 10 being most urgent
    repair_difficulty: str      # easy, medium, hard, expert
    estimated_time: str         # e.g., "5-10 minutes"
    repair_notes: str
    tools_needed: List[str]


class DefectScorer:
    """Scores and prioritizes PCB defects for repair guidance."""

    def __init__(self):
        """Initialize defect scorer."""
        self.severity_weights = {
            DefectSeverity.CRITICAL: 10,
            DefectSeverity.HIGH: 7,
            DefectSeverity.MEDIUM: 4,
            DefectSeverity.LOW: 2,
            DefectSeverity.INFORMATIONAL: 0
        }

        self.category_difficulty = {
            DefectCategory.SOLDER: "easy",
            DefectCategory.COMPONENT: "medium",
            DefectCategory.TRACE: "hard",
            DefectCategory.BURN: "expert",
            DefectCategory.CORROSION: "medium",
            DefectCategory.MECHANICAL: "hard",
            DefectCategory.CONTAMINATION: "easy"
        }

    def score_defect(self, defect: Dict[str, Any]) -> DefectScore:
        """
        Score a single defect and determine repair priority.

        Args:
            defect: Raw defect detection result

        Returns:
            Scored defect with repair guidance
        """
        defect_type = defect.get('type', 'unknown')
        confidence = defect.get('confidence', 0.0)

        # Determine severity based on defect type
        severity = self._determine_severity(defect_type)

        # Determine category
        category = self._categorize_defect(defect_type)

        # Calculate repair priority (1-10)
        priority = self._calculate_priority(severity, confidence, category)

        # Get repair difficulty
        difficulty = self.category_difficulty.get(category, "medium")

        # Get location
        location = defect.get('bbox', {})

        # Generate repair notes
        repair_notes = self._generate_repair_notes(defect_type, category)

        # Get tools needed
        tools = self._get_tools_for_repair(category)

        # Estimate time
        time_estimate = self._estimate_repair_time(category, difficulty)

        return DefectScore(
            defect_type=defect_type,
            severity=severity,
            category=category,
            confidence=confidence,
            location=location,
            repair_priority=priority,
            repair_difficulty=difficulty,
            estimated_time=time_estimate,
            repair_notes=repair_notes,
            tools_needed=tools
        )

    def score_defects(self, defects: List[Dict[str, Any]]) -> List[DefectScore]:
        """
        Score multiple defects and sort by priority.

        Args:
            defects: List of raw defect detections

        Returns:
            List of scored defects, sorted by repair priority (highest first)
        """
        scored = [self.score_defect(d) for d in defects]
        return sorted(scored, key=lambda x: x.repair_priority, reverse=True)

    def _determine_severity(self, defect_type: str) -> DefectSeverity:
        """Determine severity level based on defect type."""
        critical_defects = ['short_circuit', 'missing_component', 'reversed_polarity', 'burn_damage']
        high_defects = ['cold_solder', 'lifted_pad', 'broken_trace', 'component_damage']
        medium_defects = ['excess_solder', 'solder_bridge', 'flux_residue', 'oxidation']
        low_defects = ['cosmetic_damage', 'label_damage', 'minor_scratch']

        defect_lower = defect_type.lower()

        if any(d in defect_lower for d in critical_defects):
            return DefectSeverity.CRITICAL
        elif any(d in defect_lower for d in high_defects):
            return DefectSeverity.HIGH
        elif any(d in defect_lower for d in medium_defects):
            return DefectSeverity.MEDIUM
        elif any(d in defect_lower for d in low_defects):
            return DefectSeverity.LOW
        else:
            return DefectSeverity.MEDIUM  # Default

    def _categorize_defect(self, defect_type: str) -> DefectCategory:
        """Categorize defect type."""
        defect_lower = defect_type.lower()

        if 'solder' in defect_lower or 'bridge' in defect_lower:
            return DefectCategory.SOLDER
        elif 'component' in defect_lower or 'polarity' in defect_lower:
            return DefectCategory.COMPONENT
        elif 'trace' in defect_lower or 'pad' in defect_lower:
            return DefectCategory.TRACE
        elif 'burn' in defect_lower or 'thermal' in defect_lower:
            return DefectCategory.BURN
        elif 'corrosion' in defect_lower or 'oxidation' in defect_lower:
            return DefectCategory.CORROSION
        elif 'scratch' in defect_lower or 'crack' in defect_lower:
            return DefectCategory.MECHANICAL
        elif 'flux' in defect_lower or 'residue' in defect_lower:
            return DefectCategory.CONTAMINATION
        else:
            return DefectCategory.SOLDER  # Default

    def _calculate_priority(self, severity: DefectSeverity, confidence: float,
                           category: DefectCategory) -> int:
        """
        Calculate repair priority (1-10).

        Factors:
        - Severity weight (0-10)
        - Detection confidence (0-1) - with threshold handling
        - Category urgency

        Low confidence detections (< 0.5) are deprioritized but not ignored,
        as they may still need verification.
        """
        base_score = self.severity_weights[severity]

        # Adjust for confidence with threshold handling
        # Low confidence (<0.5) gets scaled down more aggressively
        # High confidence (>0.7) gets a slight boost
        if confidence < 0.5:
            # Low confidence: scale down but keep minimum visibility
            confidence_factor = 0.5 + (confidence * 0.5)  # Range: 0.5-0.75
        elif confidence > 0.7:
            # High confidence: slight boost
            confidence_factor = confidence + ((confidence - 0.7) * 0.3)  # Slight boost
            confidence_factor = min(1.0, confidence_factor)
        else:
            confidence_factor = confidence

        # Category urgency adjustments
        category_urgency = {
            DefectCategory.SOLDER: 1.0,
            DefectCategory.COMPONENT: 1.2,
            DefectCategory.TRACE: 1.3,
            DefectCategory.BURN: 1.5,
            DefectCategory.CORROSION: 1.1,
            DefectCategory.MECHANICAL: 1.2,
            DefectCategory.CONTAMINATION: 0.8
        }

        urgency = category_urgency.get(category, 1.0)

        priority = base_score * confidence_factor * urgency

        # Clamp to 1-10
        return max(1, min(10, int(priority)))

    def _generate_repair_notes(self, defect_type: str, category: DefectCategory) -> str:
        """Generate repair guidance notes."""
        notes = {
            DefectCategory.SOLDER: "Inspect solder joint. Reflow with proper temperature and flux.",
            DefectCategory.COMPONENT: "Check component orientation and placement. May need replacement.",
            DefectCategory.TRACE: "Inspect for continuity. May need trace repair or jumper wire.",
            DefectCategory.BURN: "Check for thermal damage. Component replacement likely needed.",
            DefectCategory.CORROSION: "Clean with isopropyl alcohol. Check for circuit damage.",
            DefectCategory.MECHANICAL: "Inspect for structural integrity. May affect functionality.",
            DefectCategory.CONTAMINATION: "Clean with appropriate solvent. Prevent future contamination."
        }
        return notes.get(category, "Inspect and repair as needed.")

    def _get_tools_for_repair(self, category: DefectCategory) -> List[str]:
        """Get required tools for repair category."""
        tools = {
            DefectCategory.SOLDER: ["Soldering iron", "Solder", "Flux", "Solder wick"],
            DefectCategory.COMPONENT: ["Soldering iron", "Tweezers", "Magnifying glass"],
            DefectCategory.TRACE: ["Multimeter", "Jumper wire", "Soldering iron"],
            DefectCategory.BURN: ["Heat gun", "Replacement components", "Soldering iron"],
            DefectCategory.CORROSION: ["Isopropyl alcohol", "Soft brush", "Lint-free cloth"],
            DefectCategory.MECHANICAL: ["Epoxy", "UV glue", "Inspection tools"],
            DefectCategory.CONTAMINATION: ["Isopropyl alcohol", "Flux remover", "Soft brush"]
        }
        return tools.get(category, ["Soldering iron", "Multimeter"])

    def _estimate_repair_time(self, category: DefectCategory, difficulty: str) -> str:
        """Estimate repair time based on category and difficulty."""
        time_matrix = {
            'easy': "5-10 minutes",
            'medium': "15-30 minutes",
            'hard': "30-60 minutes",
            'expert': "1-2 hours"
        }
        return time_matrix.get(difficulty, "15-30 minutes")


# Global singleton instance
defect_scorer = DefectScorer()
