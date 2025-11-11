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

from src.intelligence.circuit_analyzer import (
    CircuitIntelligenceAnalyzer,
    CircuitTopology,
    FunctionalBlock,
    ComponentRelationship,
    circuit_intelligence
)

from src.intelligence.repair_guidance import repair_guidance
from src.intelligence.modification_planner import modification_planner
from src.intelligence.trace_analyzer import trace_analyzer
from src.intelligence.value_extraction import value_extractor
from src.intelligence.safety_validator import safety_validator
from src.intelligence.pinout_database import pinout_database
from src.intelligence.pin_detector import pin_detector
from src.intelligence.connection_mapper import connection_mapper
from src.intelligence.visual_overlay import visual_overlay_renderer
from src.intelligence.interactive_repair_chatbot import interactive_repair_chatbot
from src.intelligence.advanced_trace_follower import advanced_trace_follower
from src.intelligence.resistor_color_decoder import resistor_color_decoder
from src.intelligence.capacitor_value_reader import capacitor_value_reader

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
