"""
Smart Design Generator - With Intelligent Component Selection

Integrates ComponentOptimizer to make smart component choices
"""

import logging
from pathlib import Path
from typing import Dict, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SmartComponentChoice:
    """A component choice with full reasoning"""
    selected: str
    cost: float
    reasoning: str
    alternatives: List[Dict]
    tradeoffs: str


class SmartDesignGenerator:
    """
    Design generator with intelligent component selection

    Makes smart choices about:
    - Module vs raw components
    - Feature comparison between similar modules
    - Cost-benefit analysis
    """

    def __init__(self):
        self.component_knowledge = self._load_component_knowledge()

    def _load_component_knowledge(self) -> Dict:
        """Load component database with full specs and pricing"""

        return {
            "wifi_microcontroller": {
                "options": [
                    {
                        "name": "ESP32 DevKit Module",
                        "cost": 8.00,
                        "type": "module",
                        "assembly_min": 5,
                        "specs": {
                            "cores": 2,
                            "mhz": 240,
                            "ram_kb": 520,
                            "wifi": "802.11n",
                            "bluetooth": "BLE 4.2",
                            "gpio": 34
                        },
                        "pros": ["Dual-core", "Bluetooth", "Lots of RAM"],
                        "cons": ["More expensive", "Overkill for simple tasks"]
                    },
                    {
                        "name": "ESP8266 NodeMCU Module",
                        "cost": 4.00,
                        "type": "module",
                        "assembly_min": 5,
                        "specs": {
                            "cores": 1,
                            "mhz": 80,
                            "ram_kb": 80,
                            "wifi": "802.11n",
                            "bluetooth": None,
                            "gpio": 17
                        },
                        "pros": ["Cheaper", "Simple", "WiFi works great"],
                        "cons": ["No Bluetooth", "Less RAM", "Single core"]
                    },
                    {
                        "name": "ESP32-C6 Module",
                        "cost": 8.10,
                        "type": "module",
                        "assembly_min": 5,
                        "specs": {
                            "cores": 1,
                            "mhz": 160,
                            "ram_kb": 400,
                            "wifi": "802.11ax (WiFi 6)",
                            "bluetooth": "BLE 5.3",
                            "gpio": 22
                        },
                        "pros": ["WiFi 6", "BLE 5.3", "Modern standards"],
                        "cons": ["Slightly more expensive", "Single core"]
                    }
                ],
                "selection_rules": {
                    "simple_iot": "ESP8266",  # Temp sensor, switch, etc.
                    "bluetooth_needed": "ESP32",
                    "future_proof": "ESP32-C6",
                    "dual_core_needed": "ESP32"
                }
            },

            "voltage_regulator": {
                "options": [
                    {
                        "name": "LM7805 Module",
                        "cost": 0.30,
                        "type": "module",
                        "assembly_min": 1,
                        "specs": {
                            "output_v": 5.0,
                            "max_current_ma": 1000,
                            "type": "linear",
                            "efficiency": 60
                        },
                        "pros": ["Ready to use", "Simple", "Reliable"],
                        "cons": ["Inefficient", "Gets hot"]
                    },
                    {
                        "name": "LM7805 Raw IC + Caps",
                        "cost": 0.15,
                        "type": "raw",
                        "assembly_min": 10,
                        "specs": {
                            "output_v": 5.0,
                            "max_current_ma": 1000,
                            "type": "linear",
                            "efficiency": 60
                        },
                        "pros": ["Cheaper component cost"],
                        "cons": ["Need capacitors", "Soldering required", "Takes time"]
                    },
                    {
                        "name": "Buck Converter Module (LM2596)",
                        "cost": 1.50,
                        "type": "module",
                        "assembly_min": 1,
                        "specs": {
                            "output_v": "1.25-37V adjustable",
                            "max_current_ma": 3000,
                            "type": "switching",
                            "efficiency": 92
                        },
                        "pros": ["Efficient", "No heat", "3A capacity", "Adjustable"],
                        "cons": ["More expensive", "More complex"]
                    }
                ],
                "selection_rules": {
                    "low_current": "LM7805 Module",  # <500mA
                    "high_current": "Buck Converter",  # >1A
                    "production": "LM7805 Raw IC"  # >100 units
                }
            },

            "servo_driver": {
                "options": [
                    {
                        "name": "PCA9685 Breakout Board",
                        "cost": 4.00,
                        "type": "module",
                        "assembly_min": 2,
                        "specs": {
                            "channels": 16,
                            "resolution": "12-bit",
                            "interface": "I2C"
                        },
                        "pros": ["16 servos", "12-bit precision", "I2C control"],
                        "cons": ["Costs $4"]
                    },
                    {
                        "name": "Direct GPIO PWM",
                        "cost": 0.00,
                        "type": "software",
                        "assembly_min": 0,
                        "specs": {
                            "channels": 4,
                            "resolution": "8-bit",
                            "interface": "GPIO"
                        },
                        "pros": ["Free", "Simple"],
                        "cons": ["Limited channels", "Lower resolution", "Jerky motion"]
                    }
                ],
                "selection_rules": {
                    "robot_arm": "PCA9685",  # Needs smooth motion
                    "simple_servo": "Direct GPIO"  # Single servo is fine
                }
            }
        }

    def select_component(
        self,
        component_type: str,
        requirements: Dict,
        build_quantity: int = 1
    ) -> SmartComponentChoice:
        """
        Intelligently select best component with reasoning

        Args:
            component_type: Type of component needed
            requirements: What the project needs (bluetooth, current, etc.)
            build_quantity: How many units being built

        Returns:
            SmartComponentChoice with selected component and reasoning
        """

        if component_type not in self.component_knowledge:
            # Fallback to simple selection
            return SmartComponentChoice(
                selected=f"{component_type}_generic",
                cost=1.00,
                reasoning="Generic component (database incomplete)",
                alternatives=[],
                tradeoffs="No optimization available"
            )

        knowledge = self.component_knowledge[component_type]
        options = knowledge["options"]
        rules = knowledge["selection_rules"]

        # Apply selection rules based on requirements
        selected_option = self._apply_rules(options, rules, requirements, build_quantity)

        # Generate reasoning
        reasoning = self._explain_choice(selected_option, options, requirements, build_quantity)

        # Find alternatives
        alternatives = [
            {
                "name": opt["name"],
                "cost": opt["cost"],
                "when_to_use": self._when_to_use(opt, requirements)
            }
            for opt in options if opt["name"] != selected_option["name"]
        ]

        # Analyze tradeoffs
        tradeoffs = self._analyze_tradeoffs(selected_option, options)

        return SmartComponentChoice(
            selected=selected_option["name"],
            cost=selected_option["cost"],
            reasoning=reasoning,
            alternatives=alternatives,
            tradeoffs=tradeoffs
        )

    def _apply_rules(self, options, rules, requirements, build_quantity):
        """Apply selection rules to pick best option"""

        # Check if specific rule applies
        for req_key, req_value in requirements.items():
            if req_key in rules and req_value:
                rule_result = rules[req_key]
                for opt in options:
                    if opt["name"].startswith(rule_result):
                        return opt

        # Production optimization
        if build_quantity >= 100:
            if "production" in rules:
                for opt in options:
                    if opt["name"].startswith(rules["production"]):
                        return opt

        # Default: Best value (balance cost and features)
        # Score = features / cost
        best_option = max(options, key=lambda o: len(o.get("specs", {})) / max(o["cost"], 0.1))
        return best_option

    def _explain_choice(self, selected, all_options, requirements, build_quantity):
        """Generate human-readable reasoning"""

        reasons = []

        # Cost comparison
        cheapest = min(all_options, key=lambda o: o["cost"])
        if selected["cost"] == cheapest["cost"]:
            reasons.append(f"Lowest cost (${selected['cost']:.2f})")
        elif selected["cost"] > cheapest["cost"]:
            diff = selected["cost"] - cheapest["cost"]
            # Explain why worth the extra cost
            extra_features = []
            for key in selected.get("specs", {}):
                if key not in cheapest.get("specs", {}) or selected["specs"][key] != cheapest["specs"][key]:
                    extra_features.append(key.replace("_", " "))
            if extra_features:
                reasons.append(
                    f"Worth ${diff:.2f} extra for: {', '.join(extra_features[:2])}"
                )

        # Assembly time
        if selected.get("assembly_min", 0) < 10:
            reasons.append("Quick assembly")

        # Build quantity
        if build_quantity == 1:
            reasons.append("Optimal for single prototype")
        elif build_quantity >= 100:
            total_savings = (
                max(o["cost"] for o in all_options) - selected["cost"]
            ) * build_quantity
            if total_savings > 50:
                reasons.append(f"Saves ${total_savings:.0f} at {build_quantity} units")

        # Requirements match
        for req, value in requirements.items():
            if value and req in selected.get("specs", {}):
                reasons.append(f"Meets {req.replace('_', ' ')} requirement")

        return "; ".join(reasons) if reasons else "Best overall choice"

    def _when_to_use(self, option, requirements):
        """Explain when to use this alternative"""

        unique_features = []

        # Find unique features
        specs = option.get("specs", {})
        for key, value in specs.items():
            if value and value not in [None, 0, False]:
                if key == "bluetooth" and value:
                    unique_features.append("need Bluetooth")
                elif key == "cores" and value > 1:
                    unique_features.append("need multi-core processing")
                elif "wifi" in key.lower() and "6" in str(value):
                    unique_features.append("want WiFi 6")

        if unique_features:
            return f"If you {unique_features[0]}"
        else:
            return "Budget-constrained projects"

    def _analyze_tradeoffs(self, selected, all_options):
        """What you give up with this choice"""

        tradeoffs = []

        # Cost tradeoff
        cheapest = min(all_options, key=lambda o: o["cost"])
        if selected["cost"] > cheapest["cost"]:
            diff = selected["cost"] - cheapest["cost"]
            tradeoffs.append(f"${diff:.2f} more than cheapest option")

        # Feature tradeoffs
        most_features = max(all_options, key=lambda o: len(o.get("specs", {})))
        if len(selected.get("specs", {})) < len(most_features.get("specs", {})):
            missing = set(most_features.get("specs", {}).keys()) - set(selected.get("specs", {}).keys())
            if missing:
                tradeoffs.append(f"No {list(missing)[0].replace('_', ' ')}")

        return "; ".join(tradeoffs) if tradeoffs else "No significant tradeoffs"


# Quick test
if __name__ == "__main__":
    gen = SmartDesignGenerator()

    print("=" * 70)
    print("SMART COMPONENT SELECTION - Live Demo")
    print("=" * 70)
    print()

    # Test 1: Simple WiFi sensor
    print("Test 1: WiFi Temperature Sensor")
    print("-" * 70)
    choice = gen.select_component(
        "wifi_microcontroller",
        requirements={"simple_iot": True, "bluetooth_needed": False},
        build_quantity=1
    )
    print(f"Selected: {choice.selected}")
    print(f"Cost: ${choice.cost:.2f}")
    print(f"Reasoning: {choice.reasoning}")
    print(f"Tradeoffs: {choice.tradeoffs}")
    print("\nAlternatives:")
    for alt in choice.alternatives:
        print(f"  • {alt['name']} (${alt['cost']:.2f}) - {alt['when_to_use']}")

    print("\n" + "=" * 70)

    # Test 2: Robot arm (needs Bluetooth)
    print("Test 2: Robot Arm with Bluetooth Control")
    print("-" * 70)
    choice2 = gen.select_component(
        "wifi_microcontroller",
        requirements={"bluetooth_needed": True, "dual_core_needed": True},
        build_quantity=1
    )
    print(f"Selected: {choice2.selected}")
    print(f"Cost: ${choice2.cost:.2f}")
    print(f"Reasoning: {choice2.reasoning}")

    print("\n" + "=" * 70)

    # Test 3: Voltage regulator comparison
    print("Test 3: Voltage Regulator for Low-Current Project")
    print("-" * 70)
    choice3 = gen.select_component(
        "voltage_regulator",
        requirements={"low_current": True},
        build_quantity=1
    )
    print(f"Selected: {choice3.selected}")
    print(f"Cost: ${choice3.cost:.2f}")
    print(f"Reasoning: {choice3.reasoning}")
    print(f"Tradeoffs: {choice3.tradeoffs}")

    print("\n" + "=" * 70)
