#!/usr/bin/env python3
import json
from src.llm.llm_integration import CircuitLLMIntegration

TEST_COMPONENTS = [
    {
        "type": "ic_chip",
        "detection_confidence": 0.92,
        "capabilities": ["arduino_projects", "iot_devices"],
        "market_value": 0.5,
        "educational_value": "high",
    },
    {
        "type": "capacitor",
        "detection_confidence": 0.88,
        "capabilities": ["power_filtering", "voltage_regulation"],
        "market_value": 0.25,
        "educational_value": "medium",
    },
]


def main():
    llm = CircuitLLMIntegration()
    results = []
    for comp in TEST_COMPONENTS:
        analysis = llm.analyze_component_advanced(comp)
        results.append({"input": comp, "analysis": analysis})
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()

