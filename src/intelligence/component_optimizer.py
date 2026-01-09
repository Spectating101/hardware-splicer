"""
Component Optimizer - Intelligent Component Selection

Makes smart decisions about:
- Module vs raw components (cost-benefit analysis)
- Module A vs Module B (feature comparison)
- Tradeoff analysis (cost vs features vs time)
- Recommendations with reasoning

Example:
    "ESP32 module ($8) vs ESP8266 module ($4)"
    → Recommends ESP32 because: dual-core, Bluetooth, 4MB vs 1MB, worth $4 extra
"""

import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ComponentType(Enum):
    """Component form factor types"""
    MODULE = "module"  # Pre-assembled breakout board
    RAW_IC = "raw_ic"  # Bare integrated circuit
    DISCRETE = "discrete"  # Individual passive (resistor, cap, etc.)
    ASSEMBLED = "assembled"  # Pre-built assembly (servo, sensor, etc.)


class SelectionReason(Enum):
    """Why this component was selected"""
    COST_EFFECTIVE = "cost_effective"  # Best price
    FEATURE_SUPERIOR = "feature_superior"  # Better specs
    TIME_SAVING = "time_saving"  # Easier/faster to use
    RELIABILITY = "reliability"  # More reliable
    AVAILABILITY = "availability"  # Easier to source
    PRODUCTION_SCALE = "production_scale"  # Better for production
    PROTOTYPE_FRIENDLY = "prototype_friendly"  # Better for prototyping


@dataclass
class ComponentOption:
    """A component choice with full details"""
    name: str
    component_type: ComponentType
    cost_usd: float
    features: Dict[str, any]
    assembly_time_minutes: float = 0.0
    difficulty_level: int = 1  # 1=easy, 5=expert
    availability_score: float = 1.0  # 0-1, higher is easier to source
    reliability_score: float = 1.0  # 0-1, higher is more reliable
    notes: str = ""

    # Specs (example for ESP32)
    specs: Dict[str, any] = field(default_factory=dict)
    # {
    #     "cpu_cores": 2,
    #     "clock_mhz": 240,
    #     "ram_kb": 520,
    #     "flash_mb": 4,
    #     "wifi": "802.11 b/g/n",
    #     "bluetooth": "BLE 4.2",
    #     "gpio_pins": 34
    # }


@dataclass
class ComponentComparison:
    """Comparison between multiple component options"""
    component_category: str  # e.g., "WiFi Microcontroller"
    options: List[ComponentOption]
    recommended: ComponentOption
    reasoning: str
    cost_difference: float
    feature_differences: Dict[str, any]
    selection_reason: SelectionReason
    tradeoff_analysis: str


class ComponentOptimizer:
    """
    Intelligent component selection engine

    Compares options and recommends best choice based on:
    - Cost
    - Features
    - Assembly time
    - Build quantity
    - User skill level
    """

    def __init__(self):
        self.component_database = self._load_component_database()

    def _load_component_database(self) -> Dict[str, List[ComponentOption]]:
        """
        Load component database with detailed specs

        TODO: Load from actual database/API
        For now, hardcoded examples
        """

        database = {
            "wifi_microcontroller": [
                ComponentOption(
                    name="ESP32 DevKit Module",
                    component_type=ComponentType.MODULE,
                    cost_usd=8.00,
                    features={"wifi": True, "bluetooth": True, "dual_core": True},
                    assembly_time_minutes=5.0,  # Just plug in
                    difficulty_level=1,
                    availability_score=1.0,  # Everywhere
                    reliability_score=0.95,
                    specs={
                        "cpu_cores": 2,
                        "clock_mhz": 240,
                        "ram_kb": 520,
                        "flash_mb": 4,
                        "wifi": "802.11 b/g/n",
                        "bluetooth": "BLE 4.2",
                        "gpio_pins": 34,
                        "form_factor": "DIP breadboard-friendly"
                    },
                    notes="Pre-assembled module with USB, voltage regulator, auto-reset circuit"
                ),
                ComponentOption(
                    name="ESP8266 NodeMCU Module",
                    component_type=ComponentType.MODULE,
                    cost_usd=4.00,
                    assembly_time_minutes=5.0,
                    difficulty_level=1,
                    availability_score=1.0,
                    reliability_score=0.90,
                    specs={
                        "cpu_cores": 1,
                        "clock_mhz": 80,
                        "ram_kb": 80,
                        "flash_mb": 4,
                        "wifi": "802.11 b/g/n",
                        "bluetooth": None,
                        "gpio_pins": 17,
                        "form_factor": "DIP breadboard-friendly"
                    },
                    notes="Cheaper, single-core, no Bluetooth"
                ),
                ComponentOption(
                    name="ESP32-WROOM-32 (Raw Module)",
                    component_type=ComponentType.RAW_IC,
                    cost_usd=2.50,
                    assembly_time_minutes=120.0,  # SMD soldering + support circuit
                    difficulty_level=4,
                    availability_score=0.8,
                    reliability_score=0.98,  # Higher if done right
                    specs={
                        "cpu_cores": 2,
                        "clock_mhz": 240,
                        "ram_kb": 520,
                        "flash_mb": 4,
                        "wifi": "802.11 b/g/n",
                        "bluetooth": "BLE 4.2",
                        "gpio_pins": 34,
                        "form_factor": "SMD castellated pads"
                    },
                    notes="Raw module - requires custom PCB, passives, voltage regulation, USB circuit"
                ),
                ComponentOption(
                    name="ESP32-C3 Module",
                    component_type=ComponentType.MODULE,
                    cost_usd=6.00,
                    assembly_time_minutes=5.0,
                    difficulty_level=1,
                    availability_score=0.9,
                    reliability_score=0.93,
                    specs={
                        "cpu_cores": 1,
                        "clock_mhz": 160,
                        "ram_kb": 400,
                        "flash_mb": 4,
                        "wifi": "802.11 b/g/n",
                        "bluetooth": "BLE 5.0",
                        "gpio_pins": 22,
                        "form_factor": "DIP breadboard-friendly"
                    },
                    notes="RISC-V architecture, BLE 5.0, lower power"
                )
            ],

            "servo_driver": [
                ComponentOption(
                    name="PCA9685 Breakout Board",
                    component_type=ComponentType.MODULE,
                    cost_usd=4.00,
                    assembly_time_minutes=2.0,
                    difficulty_level=1,
                    specs={
                        "channels": 16,
                        "pwm_resolution": "12-bit",
                        "i2c_interface": True,
                        "external_power": True,
                        "voltage_range": "3.3V-5V logic, 6V servo power"
                    },
                    notes="Industry standard, I2C controlled, 16 servos"
                ),
                ComponentOption(
                    name="Direct GPIO PWM (No Driver)",
                    component_type=ComponentType.DISCRETE,
                    cost_usd=0.00,  # Just software
                    assembly_time_minutes=0.0,
                    difficulty_level=2,
                    specs={
                        "channels": 4,  # Limited by MCU PWM pins
                        "pwm_resolution": "8-bit",
                        "i2c_interface": False,
                        "external_power": False,
                        "voltage_range": "3.3V logic only"
                    },
                    notes="Free but limited to 4 servos, lower resolution, shares power with MCU"
                )
            ],

            "voltage_regulator": [
                ComponentOption(
                    name="LM7805 Module (Assembled)",
                    component_type=ComponentType.MODULE,
                    cost_usd=0.30,
                    assembly_time_minutes=1.0,
                    difficulty_level=1,
                    specs={
                        "output_voltage": 5.0,
                        "max_current_ma": 1000,
                        "dropout_voltage": 2.0,
                        "efficiency_percent": 60,
                        "heatsink_required": True
                    },
                    notes="Linear regulator, simple, gets hot"
                ),
                ComponentOption(
                    name="LM7805 Raw IC + Passives",
                    component_type=ComponentType.RAW_IC,
                    cost_usd=0.15,  # IC + caps
                    assembly_time_minutes=10.0,  # Soldering
                    difficulty_level=2,
                    specs={
                        "output_voltage": 5.0,
                        "max_current_ma": 1000,
                        "dropout_voltage": 2.0,
                        "efficiency_percent": 60,
                        "heatsink_required": True
                    },
                    notes="Need 2 capacitors (100nF, 10µF), soldering required"
                ),
                ComponentOption(
                    name="Buck Converter Module (LM2596)",
                    component_type=ComponentType.MODULE,
                    cost_usd=1.50,
                    assembly_time_minutes=1.0,
                    difficulty_level=1,
                    specs={
                        "output_voltage": "adjustable 1.25-37V",
                        "max_current_ma": 3000,
                        "dropout_voltage": 0.5,
                        "efficiency_percent": 92,
                        "heatsink_required": False
                    },
                    notes="Switching regulator, 92% efficient, no heat, adjustable"
                )
            ],

            "rectifier": [
                ComponentOption(
                    name="Bridge Rectifier Module (W10)",
                    component_type=ComponentType.ASSEMBLED,
                    cost_usd=0.20,
                    assembly_time_minutes=1.0,
                    difficulty_level=1,
                    specs={
                        "max_current_a": 1.5,
                        "voltage_drop": 1.0,
                        "max_reverse_voltage": 1000
                    }
                ),
                ComponentOption(
                    name="4× 1N4007 Diodes (Discrete)",
                    component_type=ComponentType.DISCRETE,
                    cost_usd=0.08,  # 4 diodes @ $0.02 each
                    assembly_time_minutes=15.0,  # Wire 4 diodes in bridge config
                    difficulty_level=3,
                    specs={
                        "max_current_a": 1.0,
                        "voltage_drop": 0.7,
                        "max_reverse_voltage": 1000
                    },
                    notes="Need to wire 4 diodes correctly - error-prone"
                )
            ]
        }

        return database

    def compare_options(
        self,
        component_category: str,
        build_quantity: int = 1,
        user_skill_level: int = 1,  # 1=beginner, 5=expert
        optimize_for: str = "cost_and_time"  # or "cost", "features", "production"
    ) -> ComponentComparison:
        """
        Compare component options and recommend best choice

        Args:
            component_category: What component type (e.g., "wifi_microcontroller")
            build_quantity: How many units being built (affects recommendation)
            user_skill_level: 1-5, affects difficulty weighting
            optimize_for: What to prioritize

        Returns:
            ComponentComparison with recommendation and reasoning
        """

        if component_category not in self.component_database:
            raise ValueError(f"Unknown component category: {component_category}")

        options = self.component_database[component_category]

        # Score each option
        scored_options = []
        for option in options:
            score = self._score_option(
                option,
                build_quantity=build_quantity,
                user_skill_level=user_skill_level,
                optimize_for=optimize_for
            )
            scored_options.append((score, option))

        # Sort by score (highest first)
        scored_options.sort(reverse=True, key=lambda x: x[0])

        best_score, recommended = scored_options[0]

        # Generate reasoning
        reasoning, selection_reason = self._generate_reasoning(
            recommended=recommended,
            alternatives=[(s, o) for s, o in scored_options[1:]],
            build_quantity=build_quantity,
            user_skill_level=user_skill_level,
            optimize_for=optimize_for
        )

        # Compare features
        feature_diff = self._compare_features(options)

        # Calculate cost difference
        costs = [o.cost_usd for o in options]
        cost_diff = max(costs) - min(costs)

        # Tradeoff analysis
        tradeoff = self._analyze_tradeoffs(recommended, options, build_quantity)

        return ComponentComparison(
            component_category=component_category,
            options=options,
            recommended=recommended,
            reasoning=reasoning,
            cost_difference=cost_diff,
            feature_differences=feature_diff,
            selection_reason=selection_reason,
            tradeoff_analysis=tradeoff
        )

    def _score_option(
        self,
        option: ComponentOption,
        build_quantity: int,
        user_skill_level: int,
        optimize_for: str
    ) -> float:
        """
        Score a component option based on criteria

        Returns score 0-100 (higher is better)
        """

        score = 0.0

        # Cost scoring (accounting for quantity and assembly time)
        total_cost_per_unit = option.cost_usd

        # Assembly time cost ($20/hour labor rate)
        labor_cost = (option.assembly_time_minutes / 60.0) * 20.0

        if build_quantity == 1:
            # For single build, assembly time matters a lot
            total_cost = total_cost_per_unit + labor_cost
        else:
            # For production, amortize setup time
            setup_time_cost = labor_cost  # One-time
            per_unit_time_cost = (option.assembly_time_minutes / 60.0) * 2.0  # Scaled down for production
            total_cost = total_cost_per_unit + (setup_time_cost / build_quantity) + per_unit_time_cost

        # Cost score (inverse - lower cost = higher score)
        # Normalize to typical range $0.10 - $10
        cost_score = max(0, 100 - (total_cost / 0.10) * 10)

        # Feature score (based on specs richness)
        feature_score = len(option.specs) * 5  # More specs = better

        # Difficulty score (easier = better, unless user is expert)
        if user_skill_level >= option.difficulty_level:
            difficulty_score = 100  # User can handle it
        else:
            # Penalize if too difficult for user
            difficulty_score = max(0, 100 - (option.difficulty_level - user_skill_level) * 50)

        # Availability score
        availability_score = option.availability_score * 100

        # Reliability score
        reliability_score = option.reliability_score * 100

        # Weighted combination based on optimize_for
        if optimize_for == "cost":
            score = (
                cost_score * 0.7 +
                feature_score * 0.1 +
                difficulty_score * 0.1 +
                availability_score * 0.05 +
                reliability_score * 0.05
            )
        elif optimize_for == "features":
            score = (
                cost_score * 0.2 +
                feature_score * 0.5 +
                difficulty_score * 0.1 +
                availability_score * 0.1 +
                reliability_score * 0.1
            )
        elif optimize_for == "production":
            score = (
                cost_score * 0.5 +
                feature_score * 0.1 +
                difficulty_score * 0.0 +  # Doesn't matter for production
                availability_score * 0.2 +
                reliability_score * 0.2
            )
        else:  # "cost_and_time"
            score = (
                cost_score * 0.4 +
                feature_score * 0.2 +
                difficulty_score * 0.2 +
                availability_score * 0.1 +
                reliability_score * 0.1
            )

        return score

    def _generate_reasoning(
        self,
        recommended: ComponentOption,
        alternatives: List[Tuple[float, ComponentOption]],
        build_quantity: int,
        user_skill_level: int,
        optimize_for: str
    ) -> Tuple[str, SelectionReason]:
        """Generate human-readable reasoning for selection"""

        reasons = []
        selection_reason = SelectionReason.COST_EFFECTIVE

        # Cost comparison
        if alternatives:
            cheapest_alt = min(alternatives, key=lambda x: x[1].cost_usd)
            if recommended.cost_usd <= cheapest_alt[1].cost_usd:
                reasons.append(f"Lowest cost: ${recommended.cost_usd:.2f}")
                selection_reason = SelectionReason.COST_EFFECTIVE
            elif recommended.cost_usd > cheapest_alt[1].cost_usd:
                diff = recommended.cost_usd - cheapest_alt[1].cost_usd
                # Explain why worth the extra cost
                feature_advantages = self._get_feature_advantages(recommended, cheapest_alt[1])
                if feature_advantages:
                    reasons.append(
                        f"Worth ${diff:.2f} extra for: {', '.join(feature_advantages)}"
                    )
                    selection_reason = SelectionReason.FEATURE_SUPERIOR

        # Assembly time
        if recommended.assembly_time_minutes < 10:
            reasons.append(f"Quick assembly: {recommended.assembly_time_minutes:.0f} minutes")
            if selection_reason != SelectionReason.FEATURE_SUPERIOR:
                selection_reason = SelectionReason.TIME_SAVING
        elif recommended.assembly_time_minutes > 60:
            time_saved_vs_raw = sum(o.assembly_time_minutes for _, o in alternatives) / len(alternatives) - recommended.assembly_time_minutes
            if time_saved_vs_raw < -30:  # If this takes 30+ min longer
                reasons.append(f"⚠️ Complex assembly: {recommended.assembly_time_minutes:.0f} minutes")

        # Difficulty
        if recommended.difficulty_level <= user_skill_level:
            if recommended.difficulty_level == 1:
                reasons.append("Beginner-friendly")
        else:
            reasons.append(f"⚠️ Requires skill level {recommended.difficulty_level}")

        # Build quantity considerations
        if build_quantity == 1:
            reasons.append("Optimized for single prototype")
            if selection_reason not in [SelectionReason.FEATURE_SUPERIOR, SelectionReason.TIME_SAVING]:
                selection_reason = SelectionReason.PROTOTYPE_FRIENDLY
        elif build_quantity >= 100:
            total_savings = (
                max(o.cost_usd for _, o in alternatives) - recommended.cost_usd
            ) * build_quantity
            if total_savings > 50:
                reasons.append(f"Saves ${total_savings:.0f} at {build_quantity} units")
                selection_reason = SelectionReason.PRODUCTION_SCALE

        # Reliability
        if recommended.reliability_score >= 0.95:
            reasons.append(f"High reliability ({recommended.reliability_score:.0%})")

        # Availability
        if recommended.availability_score >= 0.9:
            reasons.append("Widely available")

        # Combine into reasoning text
        reasoning_text = "; ".join(reasons)

        return reasoning_text, selection_reason

    def _get_feature_advantages(
        self,
        option_a: ComponentOption,
        option_b: ComponentOption
    ) -> List[str]:
        """Get list of features where A is better than B"""

        advantages = []

        # Compare specs
        for key in option_a.specs:
            if key not in option_b.specs:
                if option_a.specs[key]:  # Has this feature, B doesn't
                    advantages.append(f"{key.replace('_', ' ')}")
            elif isinstance(option_a.specs[key], (int, float)) and isinstance(option_b.specs[key], (int, float)):
                if option_a.specs[key] > option_b.specs[key]:
                    improvement = ((option_a.specs[key] / option_b.specs[key]) - 1) * 100
                    if improvement > 20:  # >20% better
                        advantages.append(f"{key.replace('_', ' ')} {improvement:.0f}% better")

        return advantages[:3]  # Top 3 advantages

    def _compare_features(self, options: List[ComponentOption]) -> Dict[str, any]:
        """Create feature comparison matrix"""

        comparison = {}

        # Collect all unique spec keys
        all_keys = set()
        for option in options:
            all_keys.update(option.specs.keys())

        # Build comparison table
        for key in all_keys:
            comparison[key] = {
                option.name: option.specs.get(key, "N/A")
                for option in options
            }

        return comparison

    def _analyze_tradeoffs(
        self,
        recommended: ComponentOption,
        all_options: List[ComponentOption],
        build_quantity: int
    ) -> str:
        """Analyze tradeoffs of this selection"""

        tradeoffs = []

        # Cost tradeoff
        cheapest = min(all_options, key=lambda o: o.cost_usd)
        if recommended.cost_usd > cheapest.cost_usd:
            diff = recommended.cost_usd - cheapest.cost_usd
            total_diff = diff * build_quantity
            tradeoffs.append(
                f"Costs ${diff:.2f} more than cheapest option "
                f"(${total_diff:.2f} total for {build_quantity} units)"
            )

        # Time tradeoff
        fastest = min(all_options, key=lambda o: o.assembly_time_minutes)
        if recommended.assembly_time_minutes > fastest.assembly_time_minutes:
            extra_time = recommended.assembly_time_minutes - fastest.assembly_time_minutes
            tradeoffs.append(
                f"Takes {extra_time:.0f} minutes longer to assemble than fastest option"
            )

        # Feature tradeoff
        most_features = max(all_options, key=lambda o: len(o.specs))
        if len(recommended.specs) < len(most_features.specs):
            missing = len(most_features.specs) - len(recommended.specs)
            tradeoffs.append(
                f"Has {missing} fewer features than most capable option"
            )

        if not tradeoffs:
            return "No significant tradeoffs - best overall choice"

        return "; ".join(tradeoffs)


# Example usage
if __name__ == "__main__":
    optimizer = ComponentOptimizer()

    # Example 1: WiFi microcontroller for single prototype
    print("=" * 70)
    print("Example 1: WiFi Microcontroller (Single Prototype)")
    print("=" * 70)

    comparison = optimizer.compare_options(
        component_category="wifi_microcontroller",
        build_quantity=1,
        user_skill_level=1,  # Beginner
        optimize_for="cost_and_time"
    )

    print(f"\nRecommended: {comparison.recommended.name}")
    print(f"Cost: ${comparison.recommended.cost_usd:.2f}")
    print(f"Reasoning: {comparison.reasoning}")
    print(f"\nTradeoff Analysis: {comparison.tradeoff_analysis}")

    print("\nAlternative Options:")
    for opt in comparison.options:
        if opt.name != comparison.recommended.name:
            print(f"  • {opt.name}: ${opt.cost_usd:.2f}")

    # Example 2: Same component for production (100 units)
    print("\n" + "=" * 70)
    print("Example 2: WiFi Microcontroller (Production, 100 units)")
    print("=" * 70)

    comparison_prod = optimizer.compare_options(
        component_category="wifi_microcontroller",
        build_quantity=100,
        user_skill_level=4,  # Expert (can handle SMD)
        optimize_for="production"
    )

    print(f"\nRecommended: {comparison_prod.recommended.name}")
    print(f"Cost per unit: ${comparison_prod.recommended.cost_usd:.2f}")
    print(f"Total cost (100 units): ${comparison_prod.recommended.cost_usd * 100:.2f}")
    print(f"Reasoning: {comparison_prod.reasoning}")
    print(f"\nTradeoff Analysis: {comparison_prod.tradeoff_analysis}")

    # Example 3: Voltage regulator comparison
    print("\n" + "=" * 70)
    print("Example 3: Voltage Regulator Comparison")
    print("=" * 70)

    comparison_vreg = optimizer.compare_options(
        component_category="voltage_regulator",
        build_quantity=1,
        user_skill_level=2,
        optimize_for="cost_and_time"
    )

    print(f"\nRecommended: {comparison_vreg.recommended.name}")
    print(f"Cost: ${comparison_vreg.recommended.cost_usd:.2f}")
    print(f"Reasoning: {comparison_vreg.reasoning}")
    print(f"\nKey Specs:")
    for key, value in comparison_vreg.recommended.specs.items():
        print(f"  • {key.replace('_', ' ')}: {value}")

    print("\n" + "=" * 70)
