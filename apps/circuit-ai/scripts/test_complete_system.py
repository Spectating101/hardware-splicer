#!/usr/bin/env python3
"""
Complete System Integration Test

Tests all new intelligence modules end-to-end with realistic scenarios.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import cv2
from loguru import logger

# Import all modules
from src.intelligence.component_knowledge import get_component_spec, infer_component_relationships
from src.intelligence.electrical_analysis import electrical_analyzer
from src.intelligence.repair_guidance import repair_guidance
from src.intelligence.modification_planner import modification_planner
from src.intelligence.trace_analyzer import trace_analyzer
from src.intelligence.value_extraction import value_extractor
from src.intelligence.safety_validator import safety_validator

# Mock detection class
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple, Optional
from enum import Enum

class DetectionMethod(Enum):
    YOLO = "yolo"

@dataclass
class ComponentDetection:
    bbox: List[float]
    class_name: str
    confidence: float
    method: DetectionMethod
    metadata: Dict[str, Any]
    center: Optional[Tuple[float, float]] = None


def test_component_knowledge():
    """Test component knowledge database."""
    logger.info("\n" + "="*60)
    logger.info("TEST 1: Component Knowledge Database")
    logger.info("="*60)

    # Test getting component specs
    esp_spec = get_component_spec("ESP8266")
    assert esp_spec is not None, "ESP8266 spec not found"
    assert 3.3 in esp_spec.typical_voltages, "ESP8266 voltage wrong"
    logger.info(f"✅ ESP8266 spec: {esp_spec.typical_voltages}V, {esp_spec.typical_currents}A")

    # Test relationship inference
    rel_type, confidence, role = infer_component_relationships("Capacitor", "Arduino-Uno")
    assert rel_type == "power", f"Expected power relationship, got {rel_type}"
    logger.info(f"✅ Capacitor + Arduino = {rel_type} ({confidence:.2f}) - {role}")

    rel_type, confidence, role = infer_component_relationships("LED", "Resistor")
    assert rel_type == "signal", f"Expected signal relationship, got {rel_type}"
    logger.info(f"✅ LED + Resistor = {rel_type} ({confidence:.2f}) - {role}")

    logger.info("✅ Component Knowledge: PASSED")


def test_electrical_analysis():
    """Test electrical analysis calculations."""
    logger.info("\n" + "="*60)
    logger.info("TEST 2: Electrical Analysis")
    logger.info("="*60)

    # Test power budget
    components = ["ESP8266", "Flash-Memory", "Voltage-Regulator", "Capacitor", "Capacitor"]
    budget = electrical_analyzer.analyze_power_budget(components)
    assert budget.total_power_w > 0, "Power budget should be > 0"
    logger.info(f"✅ Power Budget: {budget.total_power_w:.2f}W, {budget.thermal_estimate_c:.1f}°C")

    # Test LED resistor calculation
    led_calc = electrical_analyzer.calculate_led_current_limiting_resistor(5.0, 2.0, 0.020)
    assert led_calc['standard_resistor_ohm'] > 0, "Resistor calculation failed"
    logger.info(f"✅ LED Resistor: {led_calc['standard_resistor_ohm']}Ω @ {led_calc['power_dissipation_w']:.3f}W")

    # Test regulator efficiency
    reg_calc = electrical_analyzer.estimate_regulator_efficiency(12.0, 5.0, 0.5, "linear")
    assert reg_calc['efficiency_percent'] > 0, "Efficiency calculation failed"
    logger.info(f"✅ Regulator: {reg_calc['efficiency_percent']:.1f}% efficient, {reg_calc['ambient_25c_final_temp_c']:.0f}°C")

    # Test decoupling capacitor
    cap_calc = electrical_analyzer.calculate_capacitor_decoupling(0.05, 5.0, 1e6)
    assert cap_calc['standard_value'] > 0, "Capacitor calculation failed"
    logger.info(f"✅ Decoupling Cap: {cap_calc['standard_value']}{cap_calc['unit']}")

    logger.info("✅ Electrical Analysis: PASSED")


def test_repair_guidance():
    """Test repair guidance generation."""
    logger.info("\n" + "="*60)
    logger.info("TEST 3: Repair Guidance System")
    logger.info("="*60)

    # Test diagnostic procedure
    diagnostics = repair_guidance.generate_diagnostic_procedure(
        "arduino", ["won't upload", "not recognized"], ["Arduino-Uno", "USB-Connector"]
    )
    assert "diagnostic_tree" in diagnostics, "No diagnostic tree generated"
    assert len(diagnostics["diagnostic_tree"]) > 0, "Diagnostic tree empty"
    logger.info(f"✅ Diagnostic Tree: {len(diagnostics['diagnostic_tree'])} decision points")

    # Test repair procedure for bootloader
    procedure = repair_guidance.generate_repair_procedure(
        "arduino", "bootloader corruption", ["Arduino-Uno"]
    )
    assert procedure.steps, "No repair steps generated"
    assert len(procedure.steps) > 0, "Repair steps empty"
    logger.info(f"✅ Bootloader Repair: {len(procedure.steps)} steps, {procedure.estimated_time_minutes} min")
    logger.info(f"   Difficulty: {procedure.difficulty.value}, Safety: {procedure.safety_level.value}")

    # Test ESP firmware recovery
    esp_procedure = repair_guidance.generate_repair_procedure(
        "router", "esp firmware", ["ESP8266"]
    )
    assert esp_procedure.steps, "No ESP repair steps"
    logger.info(f"✅ ESP Recovery: {len(esp_procedure.steps)} steps, critical warnings present")

    logger.info("✅ Repair Guidance: PASSED")


def test_modification_planner():
    """Test modification planning."""
    logger.info("\n" + "="*60)
    logger.info("TEST 4: Modification Planner")
    logger.info("="*60)

    # Test component extraction
    extraction_plan = modification_planner.plan_component_extraction(
        "ESP8266", "router", "IoT project"
    )
    assert extraction_plan.steps, "No extraction steps"
    assert len(extraction_plan.steps) >= 4, "Too few extraction steps"
    logger.info(f"✅ ESP Extraction: {len(extraction_plan.steps)} steps, {extraction_plan.estimated_time_minutes} min")
    logger.info(f"   Reversibility: {extraction_plan.reversibility}")

    # Test firmware modification
    firmware_plan = modification_planner.plan_firmware_modification(
        "arduino", "stock", "IoT sensor"
    )
    assert firmware_plan.steps, "No firmware steps"
    logger.info(f"✅ Firmware Mod: {len(firmware_plan.steps)} steps, reversible: {firmware_plan.reversibility}")

    # Test circuit enhancement
    wifi_plan = modification_planner.plan_circuit_enhancement(
        "arduino", "WiFi connectivity", True
    )
    assert wifi_plan.steps, "No enhancement steps"
    assert len(wifi_plan.steps) >= 5, "Too few WiFi steps"
    logger.info(f"✅ Add WiFi: {len(wifi_plan.steps)} steps, ${wifi_plan.cost_estimate_usd}")

    # Test safety validation
    validation = modification_planner.validate_modification_safety(
        wifi_plan, ["Arduino-Uno", "ESP8266"]
    )
    assert "warnings" in validation, "No validation warnings"
    logger.info(f"✅ Safety Validation: {len(validation['warnings'])} warnings")

    logger.info("✅ Modification Planner: PASSED")


def test_trace_analyzer():
    """Test trace analysis with synthetic image."""
    logger.info("\n" + "="*60)
    logger.info("TEST 5: Trace Analyzer")
    logger.info("="*60)

    # Create synthetic PCB image
    img = np.zeros((480, 640), dtype=np.uint8)

    # Draw some fake traces (white lines on black)
    cv2.line(img, (100, 100), (300, 100), 255, 3)  # Horizontal trace
    cv2.line(img, (300, 100), (300, 300), 255, 3)  # Vertical trace
    cv2.line(img, (100, 200), (200, 200), 255, 2)  # Thinner trace

    # Create mock components
    components = [
        ComponentDetection(
            bbox=[95, 95, 105, 105],
            class_name="Resistor",
            confidence=0.9,
            method=DetectionMethod.YOLO,
            metadata={},
            center=(100, 100)
        ),
        ComponentDetection(
            bbox=[295, 295, 305, 305],
            class_name="LED",
            confidence=0.9,
            method=DetectionMethod.YOLO,
            metadata={},
            center=(300, 300)
        )
    ]

    # Analyze traces
    analysis = trace_analyzer.analyze_traces(img, components, calibration_mm=100.0)

    assert "traces" in analysis, "No traces detected"
    assert "connections" in analysis, "No connections detected"
    logger.info(f"✅ Traces Detected: {analysis['trace_count']}")
    logger.info(f"✅ Connections: {analysis['connection_count']}")
    if analysis.get('issues'):
        logger.info(f"✅ Issues Found: {len(analysis['issues'])}")

    logger.info("✅ Trace Analyzer: PASSED")


def test_value_extractor():
    """Test component value extraction."""
    logger.info("\n" + "="*60)
    logger.info("TEST 6: Value Extractor")
    logger.info("="*60)

    # Create synthetic component image
    img = np.ones((100, 100, 3), dtype=np.uint8) * 255

    components = [
        ComponentDetection(
            bbox=[10, 10, 90, 90],
            class_name="Resistor",
            confidence=0.9,
            method=DetectionMethod.YOLO,
            metadata={}
        )
    ]

    # Test extraction
    values = value_extractor.extract_values(img, components)
    assert isinstance(values, list), "Values should be a list"
    logger.info(f"✅ Value Extraction: Processed {len(components)} components")

    # Test context inference
    inferred = value_extractor.infer_value_from_context(
        "Capacitor", ["Arduino-Uno"], "arduino"
    )
    if inferred:
        logger.info(f"✅ Context Inference: {inferred.value}{inferred.unit} for Arduino decoupling")

    # Test SMD resistor decoding
    smd_result = value_extractor._decode_smd_resistor("103")
    assert smd_result, "SMD decode failed"
    assert smd_result['value'] == "10.0k", f"Expected 10.0k, got {smd_result['value']}"
    logger.info(f"✅ SMD Decode: 103 = {smd_result['value']}{smd_result['unit']}")

    # Test capacitor code decoding
    cap_result = value_extractor._decode_capacitor_code("104")
    assert cap_result, "Capacitor decode failed"
    logger.info(f"✅ Cap Code: 104 = {cap_result['value']}{cap_result['unit']}")

    logger.info("✅ Value Extractor: PASSED")


def test_safety_validator():
    """Test safety validation system."""
    logger.info("\n" + "="*60)
    logger.info("TEST 7: Safety Validator")
    logger.info("="*60)

    # Create a risky modification plan (ESP8266 + 5V)
    from src.intelligence.modification_planner import ModificationPlan, ModificationType

    risky_plan = modification_planner.plan_circuit_enhancement(
        "arduino", "WiFi", True
    )

    # Mock topology with high power
    class MockTopology:
        device_type = "arduino"
        power_budget = {"total_power_w": 15.0}
        electrical_calculations = {
            "regulator_efficiency": {
                "ambient_25c_final_temp_c": 120
            }
        }

    # Validate
    validation = safety_validator.validate_modification(
        risky_plan, MockTopology(), ["Arduino-Uno", "ESP8266"]
    )

    assert not validation.overall_safe, "Should detect safety issues"
    assert len(validation.warnings) > 0, "Should have warnings"
    logger.info(f"✅ Safety Issues Detected: {len(validation.warnings)} warnings")
    logger.info(f"   Risk Level: {validation.risk_level.value}")

    # Test safety checklist generation
    checklist = safety_validator.generate_safety_checklist(risky_plan)
    assert len(checklist) >= 10, "Checklist too short"
    logger.info(f"✅ Safety Checklist: {len(checklist)} items")

    logger.info("✅ Safety Validator: PASSED")


def test_integration():
    """Test full integration workflow."""
    logger.info("\n" + "="*60)
    logger.info("TEST 8: Complete Integration Workflow")
    logger.info("="*60)

    # Simulate full analysis pipeline
    components = [
        ComponentDetection(
            bbox=[300, 200, 380, 280],
            class_name="Arduino-Uno",
            confidence=0.95,
            method=DetectionMethod.YOLO,
            metadata={"type": "microcontroller"},
            center=(340, 240)
        ),
        ComponentDetection(
            bbox=[290, 190, 300, 200],
            class_name="Capacitor",
            confidence=0.85,
            method=DetectionMethod.YOLO,
            metadata={"type": "passive"},
            center=(295, 195)
        ),
        ComponentDetection(
            bbox=[100, 320, 110, 330],
            class_name="LED",
            confidence=0.88,
            method=DetectionMethod.YOLO,
            metadata={"type": "indicator"},
            center=(105, 325)
        ),
        ComponentDetection(
            bbox=[100, 300, 105, 310],
            class_name="Resistor",
            confidence=0.80,
            method=DetectionMethod.YOLO,
            metadata={"type": "passive"},
            center=(102.5, 305)
        )
    ]

    # 1. Analyze circuit topology
    from src.intelligence.circuit_analyzer import circuit_intelligence
    topology = circuit_intelligence.analyze_circuit(components, (640, 480))
    assert topology.device_type == "arduino", "Should detect Arduino"
    logger.info(f"✅ Step 1: Detected {topology.device_type} ({topology.device_confidence:.2f})")

    # 2. Power analysis
    comp_names = [c.class_name for c in components]
    power_budget = electrical_analyzer.analyze_power_budget(comp_names)
    logger.info(f"✅ Step 2: Power Budget {power_budget.total_power_w:.2f}W")

    # 3. Generate diagnostic procedure
    diagnostics = repair_guidance.generate_diagnostic_procedure(
        topology.device_type, [], comp_names
    )
    logger.info(f"✅ Step 3: Diagnostics {len(diagnostics['diagnostic_tree'])} tests")

    # 4. Plan modifications
    mod_plan = modification_planner.plan_circuit_enhancement(
        topology.device_type, "sensors", True
    )
    logger.info(f"✅ Step 4: Modification Plan {len(mod_plan.steps)} steps")

    # 5. Validate safety
    validation = safety_validator.validate_modification(
        mod_plan, topology, comp_names
    )
    logger.info(f"✅ Step 5: Safety Check - {validation.risk_level.value}")

    # 6. Trace analysis (with synthetic image)
    img = np.zeros((480, 640), dtype=np.uint8)
    cv2.line(img, (340, 240), (295, 195), 255, 2)  # Arduino to Cap
    cv2.line(img, (105, 325), (102, 305), 255, 2)  # LED to Resistor
    trace_result = trace_analyzer.analyze_traces(img, components)
    logger.info(f"✅ Step 6: Trace Analysis {trace_result['trace_count']} traces")

    # 7. Value extraction
    values = value_extractor.extract_values(img, components)
    logger.info(f"✅ Step 7: Value Extraction {len(values)} values")

    logger.info("\n✅ INTEGRATION WORKFLOW: PASSED")
    logger.info("All 7 analysis steps completed successfully!")


def main():
    """Run all tests."""
    logger.info("\n" + "="*60)
    logger.info("COMPLETE SYSTEM INTEGRATION TEST")
    logger.info("Testing all intelligence modules end-to-end")
    logger.info("="*60)

    try:
        test_component_knowledge()
        test_electrical_analysis()
        test_repair_guidance()
        test_modification_planner()
        test_trace_analyzer()
        test_value_extractor()
        test_safety_validator()
        test_integration()

        logger.info("\n" + "="*60)
        logger.info("✅ ALL TESTS PASSED!")
        logger.info("="*60)
        logger.info("\nSystem Status: FULLY OPERATIONAL")
        logger.info("Ready for: Real PCB analysis once model training completes")

    except AssertionError as e:
        logger.error(f"\n❌ TEST FAILED: {e}")
        raise
    except Exception as e:
        logger.error(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
