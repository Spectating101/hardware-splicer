"""
Circuit Intelligence Module

Provides deep circuit understanding beyond component detection:
- Spatial relationship analysis
- Functional block detection
- Device type identification
- Repair/repurpose guidance
- Trace analysis
- Component value extraction
- Modification planning
- Safety validation
"""

"""
Keep package import lightweight.

This repo has optional "heavy" submodules (numpy/scipy/sklearn/cv2, OCR, etc).
The web API (`api_server.py`) only needs specific submodules (e.g. `circuit_validator`)
and should not fail at import time when optional deps are missing.
"""

try:
    from .circuit_analyzer import (
        CircuitIntelligenceAnalyzer,
        CircuitTopology,
        FunctionalBlock,
        ComponentRelationship,
        circuit_intelligence,
    )
except Exception:
    CircuitIntelligenceAnalyzer = None
    CircuitTopology = None
    FunctionalBlock = None
    ComponentRelationship = None
    circuit_intelligence = None

# Conditional imports - only import if files exist
try:
    from .modification_planner import modification_planner
except ImportError:
    modification_planner = None

try:
    from .safety_validator import safety_validator
except ImportError:
    safety_validator = None

try:
    from .pin_detector import pin_detector
except ImportError:
    pin_detector = None

try:
    from .connection_mapper import connection_mapper
except ImportError:
    connection_mapper = None

try:
    from .interactive_repair_chatbot import interactive_repair_chatbot
except ImportError:
    interactive_repair_chatbot = None

try:
    from .advanced_trace_follower import advanced_trace_follower
except ImportError:
    advanced_trace_follower = None

try:
    from .capacitor_value_reader import capacitor_value_reader
except ImportError:
    capacitor_value_reader = None

__all__ = [
    "CircuitIntelligenceAnalyzer",
    "CircuitTopology",
    "FunctionalBlock",
    "ComponentRelationship",
    "circuit_intelligence",
    "modification_planner",
    "safety_validator",
    "pin_detector",
    "connection_mapper",
    "interactive_repair_chatbot",
    "advanced_trace_follower",
    "capacitor_value_reader",
]
