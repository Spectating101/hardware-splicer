"""
Resource & Inventory Management System

Tracks available components, scraps, and materials.
Enables resource-aware design and adaptive substitution.

Features:
- Inventory tracking (what do we have?)
- Scrap analysis (harvest components from broken boards)
- Component equivalence (ESP32 ≈ Arduino + WiFi module)
- Resource optimization (design with what's available)
- Real-time pricing lookup (web search for best prices)
- Sourcing recommendations (where to buy)

Author: Dum-E Intelligence System
Version: 1.1.0
"""

import logging
import json
import asyncio
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)


class ComponentCondition(Enum):
    """Component condition states."""
    NEW = "new"
    USED = "used"
    SCRAP = "scrap"  # From broken boards
    UNKNOWN = "unknown"


@dataclass
class Component:
    """Component in inventory."""
    name: str
    component_type: str
    quantity: int
    condition: ComponentCondition = ComponentCondition.UNKNOWN

    # Specifications
    specs: Dict = field(default_factory=dict)

    # Location/source
    location: str = "storage"
    source: str = ""  # "purchased", "scavenged", "recycled"

    # Metadata
    cost_usd: float = 0.0
    notes: str = ""

    def to_dict(self) -> Dict:
        """Export to dictionary."""
        return {
            "name": self.name,
            "component_type": self.component_type,
            "quantity": self.quantity,
            "condition": self.condition.value,
            "specs": self.specs,
            "location": self.location,
            "source": self.source,
            "cost_usd": self.cost_usd,
            "notes": self.notes
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Component':
        """Load from dictionary."""
        return cls(
            name=data["name"],
            component_type=data["component_type"],
            quantity=data["quantity"],
            condition=ComponentCondition(data.get("condition", "unknown")),
            specs=data.get("specs", {}),
            location=data.get("location", "storage"),
            source=data.get("source", ""),
            cost_usd=data.get("cost_usd", 0.0),
            notes=data.get("notes", "")
        )


class ResourceManager:
    """
    Manages component inventory and resource optimization.

    Enables:
    - "What do we have?" → Inventory query
    - "Can we build X?" → Feasibility check
    - "What can we substitute?" → Component equivalents
    - "Use scraps" → Scavenged component utilization
    """

    # Component equivalence database
    EQUIVALENTS = {
        "ESP32": {
            "substitutes": ["ESP8266", "Arduino Nano + ESP8266"],
            "capabilities": ["microcontroller", "wifi", "bluetooth"],
            "pins": 30
        },
        "Arduino Nano": {
            "substitutes": ["Arduino Uno", "ATmega328"],
            "capabilities": ["microcontroller"],
            "pins": 22
        },
        "DHT22": {
            "substitutes": ["DHT11", "BME280"],
            "capabilities": ["temperature", "humidity"],
            "accuracy": "high"
        },
        "DHT11": {
            "substitutes": ["DHT22"],
            "capabilities": ["temperature", "humidity"],
            "accuracy": "low"
        },
    }

    def __init__(self, inventory_path: Optional[Path] = None):
        """
        Initialize resource manager.

        Args:
            inventory_path: Path to inventory database (JSON)
        """
        self.inventory_path = inventory_path or Path("component_inventory.json")
        self.inventory: Dict[str, Component] = {}

        self._load_inventory()

        logger.info(f"ResourceManager initialized ({len(self.inventory)} components)")

    def add_component(self, component: Component):
        """Add component to inventory."""
        key = f"{component.name}_{component.condition.value}"

        if key in self.inventory:
            # Update quantity
            self.inventory[key].quantity += component.quantity
        else:
            self.inventory[key] = component

        self._save_inventory()
        logger.info(f"Added: {component.name} ×{component.quantity} ({component.condition.value})")

    def remove_component(self, name: str, quantity: int = 1) -> bool:
        """
        Remove component from inventory.

        Returns:
            True if successful, False if not enough in stock
        """
        # Find matching component
        for key, comp in self.inventory.items():
            if comp.name == name and comp.quantity >= quantity:
                comp.quantity -= quantity

                if comp.quantity == 0:
                    del self.inventory[key]

                self._save_inventory()
                logger.info(f"Used: {name} ×{quantity}")
                return True

        logger.warning(f"Not enough in stock: {name} (need {quantity})")
        return False

    def check_availability(self, required_components: List[str]) -> Dict:
        """
        Check if required components are available.

        Args:
            required_components: List of component names

        Returns:
            {
                "available": [...],
                "missing": [...],
                "substitutable": {component: [alternatives, ...]},
                "feasible": bool
            }
        """
        result = {
            "available": [],
            "missing": [],
            "substitutable": {},
            "feasible": False
        }

        for comp_name in required_components:
            # Check if we have it
            if self._has_component(comp_name):
                result["available"].append(comp_name)
            else:
                # Check for substitutes
                substitutes = self._find_substitutes(comp_name)

                if substitutes:
                    result["substitutable"][comp_name] = substitutes
                    result["available"].append(comp_name)  # Count as available (via substitute)
                else:
                    result["missing"].append(comp_name)

        # Feasible if all components available (directly or via substitutes)
        result["feasible"] = len(result["missing"]) == 0

        return result

    def suggest_design_from_scraps(self, scrap_components: List[str]) -> List[Dict]:
        """
        Suggest projects that can be built from scrap components.

        Args:
            scrap_components: List of components available from scraps

        Returns:
            List of project suggestions
        """
        suggestions = []

        # Check what we can build
        component_set = set(scrap_components)

        # Temperature sensor project
        if any(temp in component_set for temp in ["DHT22", "DHT11", "DS18B20", "BME280"]):
            if "ESP32" in component_set or "Arduino" in str(component_set):
                suggestions.append({
                    "project": "WiFi Temperature Sensor",
                    "components_used": ["temperature_sensor", "microcontroller"],
                    "difficulty": "easy"
                })

        # LED controller
        if "LED" in str(component_set) or any("led" in c.lower() for c in component_set):
            if "ESP32" in component_set or "Arduino" in str(component_set):
                suggestions.append({
                    "project": "Smart LED Controller",
                    "components_used": ["led", "microcontroller"],
                    "difficulty": "easy"
                })

        # Motor controller
        if any("motor" in c.lower() for c in component_set):
            if any(mcu in component_set for mcu in ["ESP32", "Arduino"]):
                suggestions.append({
                    "project": "Motor Controller",
                    "components_used": ["motor", "microcontroller", "motor_driver"],
                    "difficulty": "medium"
                })

        return suggestions

    def analyze_scrap_board(self, detection_result: Dict) -> List[Component]:
        """
        Analyze detected components on scrap board.

        Args:
            detection_result: Output from enhanced_detector

        Returns:
            List of usable components
        """
        usable_components = []

        for comp_detection in detection_result.get("components", []):
            component_type = comp_detection.get("label", "unknown")
            confidence = comp_detection.get("confidence", 0.0)

            # Only harvest if high confidence and no defects nearby
            if confidence > 0.8:
                # Check for defects near this component
                # (simplified - in reality would check bbox proximity)
                has_nearby_defect = False

                if not has_nearby_defect:
                    component = Component(
                        name=component_type,
                        component_type=component_type,
                        quantity=1,
                        condition=ComponentCondition.SCRAP,
                        source="scavenged",
                        notes=f"Harvested from scrap board (conf: {confidence:.2f})"
                    )
                    usable_components.append(component)

        logger.info(f"Analyzed scrap board: {len(usable_components)} usable components found")

        return usable_components

    def optimize_for_available_resources(
        self,
        design_spec: Dict,
        prefer_scraps: bool = True
    ) -> Dict:
        """
        Optimize design to use available resources.

        Args:
            design_spec: Required components for design
            prefer_scraps: Prefer scrap components over new ones

        Returns:
            Optimized design with resource allocation
        """
        optimized = {
            "components": [],
            "cost_usd": 0.0,
            "using_scraps": 0,
            "using_new": 0,
            "substitutions": []
        }

        required = design_spec.get("required_components", [])

        for comp_name in required:
            # Find best match
            allocation = self._allocate_component(comp_name, prefer_scraps)

            if allocation:
                optimized["components"].append(allocation)
                optimized["cost_usd"] += allocation.get("cost", 0.0)

                if allocation.get("condition") == "scrap":
                    optimized["using_scraps"] += 1
                else:
                    optimized["using_new"] += 1

                if allocation.get("is_substitute"):
                    optimized["substitutions"].append({
                        "original": comp_name,
                        "substitute": allocation["component"]
                    })

        return optimized

    def _has_component(self, name: str) -> bool:
        """Check if component is in inventory."""
        for comp in self.inventory.values():
            if comp.name == name and comp.quantity > 0:
                return True
        return False

    def _find_substitutes(self, component_name: str) -> List[str]:
        """Find substitute components."""
        if component_name in self.EQUIVALENTS:
            substitutes = self.EQUIVALENTS[component_name]["substitutes"]

            # Filter to only available substitutes
            available = [sub for sub in substitutes if self._has_component(sub)]

            return available

        return []

    def _allocate_component(self, name: str, prefer_scraps: bool) -> Optional[Dict]:
        """Allocate a component from inventory."""
        # Look for matching component
        candidates = [
            comp for comp in self.inventory.values()
            if comp.name == name and comp.quantity > 0
        ]

        if not candidates:
            # Try substitutes
            substitutes = self._find_substitutes(name)
            if substitutes:
                return {
                    "component": substitutes[0],
                    "condition": "substitute",
                    "is_substitute": True,
                    "cost": 0.0
                }
            return None

        # Prefer scraps if requested
        if prefer_scraps:
            scrap_candidates = [c for c in candidates if c.condition == ComponentCondition.SCRAP]
            if scrap_candidates:
                return {
                    "component": scrap_candidates[0].name,
                    "condition": "scrap",
                    "is_substitute": False,
                    "cost": 0.0  # Scraps are free!
                }

        # Use first available
        comp = candidates[0]
        return {
            "component": comp.name,
            "condition": comp.condition.value,
            "is_substitute": False,
            "cost": comp.cost_usd
        }

    def _save_inventory(self):
        """Save inventory to file."""
        try:
            data = {
                name: comp.to_dict()
                for name, comp in self.inventory.items()
            }

            with open(self.inventory_path, 'w') as f:
                json.dump(data, f, indent=2)

            logger.debug(f"Saved inventory to {self.inventory_path}")

        except Exception as e:
            logger.error(f"Failed to save inventory: {e}")

    def _load_inventory(self):
        """Load inventory from file."""
        if not self.inventory_path.exists():
            logger.info("No existing inventory found, starting fresh")
            return

        try:
            with open(self.inventory_path, 'r') as f:
                data = json.load(f)

            self.inventory = {
                name: Component.from_dict(comp_data)
                for name, comp_data in data.items()
            }

            logger.info(f"Loaded {len(self.inventory)} components from inventory")

        except Exception as e:
            logger.error(f"Failed to load inventory: {e}")
            self.inventory = {}

    async def lookup_missing_component_prices(
        self,
        missing_components: List[str]
    ) -> Dict:
        """
        Lookup real-time prices for missing components.

        Args:
            missing_components: List of component names to price

        Returns:
            Dict with pricing info and purchase recommendations
        """
        try:
            from .component_pricer import ComponentPricer

            pricer = ComponentPricer()
            pricing = await pricer.lookup_bom_pricing([
                {"component": comp, "quantity": 1}
                for comp in missing_components
            ])

            # Generate purchase recommendations
            recommendations = []
            total_cost_best = 0.0

            for comp_name, comp_pricing in pricing.items():
                if comp_pricing.best_price:
                    recommendations.append({
                        "component": comp_name,
                        "supplier": comp_pricing.best_price.supplier,
                        "price_usd": comp_pricing.best_price.total_usd,
                        "url": comp_pricing.best_price.url
                    })
                    total_cost_best += comp_pricing.best_price.total_usd

            return {
                "pricing": pricing,
                "recommendations": recommendations,
                "total_cost_usd": total_cost_best
            }

        except Exception as e:
            logger.error(f"Price lookup failed: {e}")
            return {
                "pricing": {},
                "recommendations": [],
                "total_cost_usd": 0.0,
                "error": str(e)
            }

    def generate_shopping_list(
        self,
        required_components: List[str],
        output_path: Optional[Path] = None
    ) -> str:
        """
        Generate shopping list for missing components.

        Args:
            required_components: Components needed for project
            output_path: Optional path to save shopping list

        Returns:
            Formatted shopping list as string
        """
        availability = self.check_availability(required_components)

        if not availability["missing"]:
            return "All components available in inventory! No shopping needed."

        # Lookup prices (sync wrapper)
        try:
            pricing_info = asyncio.run(
                self.lookup_missing_component_prices(availability["missing"])
            )
        except Exception as e:
            logger.error(f"Could not lookup prices: {e}")
            pricing_info = {"recommendations": [], "total_cost_usd": 0.0}

        # Generate shopping list
        lines = []
        lines.append("=" * 70)
        lines.append("SHOPPING LIST")
        lines.append("=" * 70)
        lines.append("")
        lines.append(f"Missing Components: {len(availability['missing'])}")
        lines.append("")

        if pricing_info.get("recommendations"):
            lines.append("RECOMMENDED PURCHASES:")
            lines.append("")

            for i, rec in enumerate(pricing_info["recommendations"], 1):
                lines.append(f"{i}. {rec['component']}")
                lines.append(f"   Supplier: {rec['supplier']}")
                lines.append(f"   Price: ${rec['price_usd']:.2f}")
                lines.append(f"   URL: {rec['url']}")
                lines.append("")

            lines.append("=" * 70)
            lines.append(f"ESTIMATED TOTAL: ${pricing_info['total_cost_usd']:.2f}")
            lines.append("=" * 70)

        else:
            # Fallback list without pricing
            lines.append("COMPONENTS NEEDED:")
            for comp in availability["missing"]:
                lines.append(f"  - {comp}")
            lines.append("")
            lines.append("(Run with web access for pricing and purchase links)")

        shopping_list = "\n".join(lines)

        # Save if path provided
        if output_path:
            output_path.write_text(shopping_list)
            logger.info(f"Shopping list saved to {output_path}")

        return shopping_list

    def generate_report(self) -> str:
        """Generate inventory report."""
        lines = []

        lines.append("=" * 70)
        lines.append("COMPONENT INVENTORY")
        lines.append("=" * 70)
        lines.append("")

        if not self.inventory:
            lines.append("Inventory is empty.")
            lines.append("")
        else:
            # Group by condition
            by_condition = {}
            for comp in self.inventory.values():
                cond = comp.condition.value
                if cond not in by_condition:
                    by_condition[cond] = []
                by_condition[cond].append(comp)

            for condition, components in sorted(by_condition.items()):
                lines.append(f"{condition.upper()}:")
                for comp in components:
                    lines.append(f"  - {comp.name} ×{comp.quantity}")
                    if comp.notes:
                        lines.append(f"      {comp.notes}")
                lines.append("")

        lines.append("=" * 70)

        return "\n".join(lines)


if __name__ == "__main__":
    # Test resource manager
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    manager = ResourceManager()

    # Add some components
    manager.add_component(Component(
        name="ESP32",
        component_type="microcontroller",
        quantity=2,
        condition=ComponentCondition.NEW,
        cost_usd=8.00
    ))

    manager.add_component(Component(
        name="DHT22",
        component_type="sensor",
        quantity=1,
        condition=ComponentCondition.SCRAP,
        source="scavenged",
        notes="Harvested from broken weather station"
    ))

    print(manager.generate_report())

    # Check availability
    required = ["ESP32", "DHT22", "LED", "BME280"]
    availability = manager.check_availability(required)

    print("Availability Check:")
    print(f"  Available: {availability['available']}")
    print(f"  Missing: {availability['missing']}")
    print(f"  Feasible: {availability['feasible']}")
