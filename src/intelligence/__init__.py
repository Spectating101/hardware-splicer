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

from .circuit_analyzer import (
    CircuitIntelligenceAnalyzer,
    CircuitTopology,
    FunctionalBlock,
    ComponentRelationship,
    circuit_intelligence
)

from .repair_guidance import repair_guidance
from .modification_planner import modification_planner
from .trace_analyzer import trace_analyzer
from .value_extraction import value_extractor
from .safety_validator import safety_validator
from .pinout_database import pinout_database
from .pin_detector import pin_detector
from .connection_mapper import connection_mapper
from .visual_overlay import visual_overlay_renderer
from .interactive_repair_chatbot import interactive_repair_chatbot
from .advanced_trace_follower import advanced_trace_follower
from .resistor_color_decoder import resistor_color_decoder
from .capacitor_value_reader import capacitor_value_reader

__all__ = [
    'CircuitIntelligenceAnalyzer',
    'CircuitTopology',
    'FunctionalBlock',
    'ComponentRelationship',
    'circuit_intelligence',
    'repair_guidance',
    'modification_planner',
    'trace_analyzer',
    'value_extractor',
    'safety_validator',
    'pinout_database',
    'pin_detector',
    'connection_mapper',
    'visual_overlay_renderer',
    'interactive_repair_chatbot',
    'advanced_trace_follower',
    'resistor_color_decoder',
    'capacitor_value_reader'
]
