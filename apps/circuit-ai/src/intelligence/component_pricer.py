"""
Component Pricing Lookup

Uses cite-agent's web search to find real-time component prices
from major electronics suppliers.

Suppliers searched:
- Digi-Key
- Mouser
- AliExpress
- Amazon
- eBay

Author: Dum-E Intelligence System
Version: 1.0.0
"""

import logging
import asyncio
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
import sys

logger = logging.getLogger(__name__)


@dataclass
class PriceResult:
    """Single price result from a supplier."""
    supplier: str
    price_usd: float
    url: str
    in_stock: bool = True
    quantity: int = 1
    shipping_estimate_usd: float = 0.0

    @property
    def total_usd(self) -> float:
        """Total cost including shipping."""
        return self.price_usd + self.shipping_estimate_usd


@dataclass
class ComponentPricing:
    """Complete pricing information for a component."""
    component_name: str
    prices: List[PriceResult]
    best_price: Optional[PriceResult] = None
    average_price: float = 0.0
    price_range: Tuple[float, float] = (0.0, 0.0)
    timestamp: str = ""

    def __post_init__(self):
        """Calculate best price and statistics."""
        if self.prices:
            self.prices.sort(key=lambda p: p.total_usd)
            self.best_price = self.prices[0]

            price_list = [p.price_usd for p in self.prices]
            self.average_price = sum(price_list) / len(price_list)
            self.price_range = (min(price_list), max(price_list))


class ComponentPricer:
    """
    Find component prices using web search.

    Integrates with cite-agent's web search capabilities.
    """

    # Known component patterns
    COMPONENT_PATTERNS = {
        "ESP32": ["ESP32-WROOM", "ESP32-DevKit", "ESP-WROOM-32"],
        "ESP8266": ["ESP8266", "NodeMCU", "ESP-12E"],
        "Arduino Nano": ["Arduino Nano", "ATmega328P Nano"],
        "Arduino Uno": ["Arduino Uno R3", "ATmega328P Uno"],
        "DHT22": ["DHT22", "AM2302"],
        "DHT11": ["DHT11"],
        "BME280": ["BME280", "BMP280"],
        "LED": ["LED 5mm", "LED 3mm"],
        "resistor": ["resistor"],
    }

    # Price extraction patterns
    PRICE_PATTERNS = [
        r'\$(\d+\.?\d*)',  # $10.50
        r'USD?\s*(\d+\.?\d*)',  # USD 10.50
        r'(\d+\.?\d*)\s*USD',  # 10.50 USD
        r'Price:\s*\$?(\d+\.?\d*)',  # Price: $10.50
    ]

    def __init__(self):
        """Initialize component pricer."""
        self.web_search = None
        self._initialized = False

        logger.info("ComponentPricer initialized")

    async def _ensure_initialized(self):
        """Lazy load cite-agent web search."""
        if not self._initialized:
            try:
                # Try to import from cite-agent
                cite_path = Path(__file__).parent.parent.parent.parent / "Cite-Agent"
                if cite_path.exists():
                    sys.path.insert(0, str(cite_path))

                from cite_agent.web_search import WebSearchIntegration
                self.web_search = WebSearchIntegration()
                self._initialized = True
                logger.info("Cite-agent web search loaded")

            except Exception as e:
                logger.warning(f"Could not load cite-agent web search: {e}")
                logger.info("Pricing will use fallback estimates")
                self._initialized = False

    async def lookup_price(
        self,
        component_name: str,
        quantity: int = 1
    ) -> ComponentPricing:
        """
        Lookup real-time pricing for a component.

        Args:
            component_name: Component name (e.g., "ESP32", "DHT22")
            quantity: Quantity to price

        Returns:
            ComponentPricing with results from multiple suppliers
        """
        await self._ensure_initialized()

        prices = []

        # If web search available, search suppliers
        if self.web_search:
            prices = await self._search_suppliers(component_name, quantity)

        # If no prices found, use fallback estimates
        if not prices:
            prices = self._get_fallback_prices(component_name, quantity)

        return ComponentPricing(
            component_name=component_name,
            prices=prices
        )

    async def _search_suppliers(
        self,
        component_name: str,
        quantity: int
    ) -> List[PriceResult]:
        """Search multiple suppliers for pricing."""
        prices = []

        # Expand component name to include variations
        search_terms = self._expand_component_name(component_name)

        # Search each major supplier
        suppliers = [
            ("Digi-Key", f"{search_terms[0]} site:digikey.com"),
            ("Mouser", f"{search_terms[0]} site:mouser.com"),
            ("AliExpress", f"{search_terms[0]} site:aliexpress.com"),
            ("Amazon", f"{search_terms[0]} electronics site:amazon.com"),
        ]

        for supplier_name, query in suppliers:
            try:
                result = await self.web_search.search_web(query, num_results=3)

                if result.get("success") and result.get("results"):
                    # Extract price from first result
                    for search_result in result["results"]:
                        price = self._extract_price_from_snippet(
                            search_result.get("snippet", "")
                        )

                        if price:
                            prices.append(PriceResult(
                                supplier=supplier_name,
                                price_usd=price * quantity,
                                url=search_result.get("url", ""),
                                in_stock=True,
                                quantity=quantity,
                                shipping_estimate_usd=self._estimate_shipping(supplier_name)
                            ))
                            break  # Take first valid price per supplier

            except Exception as e:
                logger.debug(f"Search failed for {supplier_name}: {e}")
                continue

        return prices

    def _expand_component_name(self, component_name: str) -> List[str]:
        """Expand component name to include common variations."""
        # Check if we have known patterns
        for pattern_name, variations in self.COMPONENT_PATTERNS.items():
            if pattern_name.lower() in component_name.lower():
                return variations

        # Return original name
        return [component_name]

    def _extract_price_from_snippet(self, text: str) -> Optional[float]:
        """Extract price from search result snippet."""
        for pattern in self.PRICE_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    price = float(match.group(1))
                    # Sanity check (components usually $0.10 - $500)
                    if 0.10 <= price <= 500.0:
                        return price
                except ValueError:
                    continue

        return None

    def _estimate_shipping(self, supplier: str) -> float:
        """Estimate shipping cost by supplier."""
        shipping_estimates = {
            "Digi-Key": 4.99,
            "Mouser": 4.99,
            "AliExpress": 0.0,  # Often free
            "Amazon": 0.0,  # Often free with Prime
            "eBay": 2.99,
        }

        return shipping_estimates.get(supplier, 3.99)

    def _get_fallback_prices(
        self,
        component_name: str,
        quantity: int
    ) -> List[PriceResult]:
        """
        Fallback pricing estimates (used when web search unavailable).

        Based on typical market prices as of 2024.
        """
        # Known component price estimates (USD, single unit)
        estimates = {
            "ESP32": 8.00,
            "ESP8266": 4.00,
            "Arduino Nano": 5.00,
            "Arduino Uno": 7.00,
            "DHT22": 3.50,
            "DHT11": 1.50,
            "BME280": 4.00,
            "LED": 0.10,
            "resistor": 0.05,
            "capacitor": 0.10,
            "wire": 0.20,
            "pcb": 2.00,
            "power_supply": 5.00,
            "motor": 8.00,
            "servo": 6.00,
            "motor_driver": 4.00,
            "lcd": 10.00,
            "oled": 8.00,
        }

        # Find best match
        base_price = 2.00  # Default unknown component

        for key, price in estimates.items():
            if key.lower() in component_name.lower():
                base_price = price
                break

        # Create estimated prices from typical suppliers
        return [
            PriceResult(
                supplier="Digi-Key (estimate)",
                price_usd=base_price * quantity * 1.0,  # Reference price
                url="https://www.digikey.com",
                in_stock=True,
                quantity=quantity,
                shipping_estimate_usd=4.99
            ),
            PriceResult(
                supplier="AliExpress (estimate)",
                price_usd=base_price * quantity * 0.6,  # Usually cheaper
                url="https://www.aliexpress.com",
                in_stock=True,
                quantity=quantity,
                shipping_estimate_usd=0.0
            ),
            PriceResult(
                supplier="Amazon (estimate)",
                price_usd=base_price * quantity * 1.2,  # Usually more expensive
                url="https://www.amazon.com",
                in_stock=True,
                quantity=quantity,
                shipping_estimate_usd=0.0
            ),
        ]

    async def lookup_bom_pricing(
        self,
        bom: List[Dict]
    ) -> Dict[str, ComponentPricing]:
        """
        Lookup pricing for entire Bill of Materials.

        Args:
            bom: List of components [{component: "ESP32", quantity: 1}, ...]

        Returns:
            Dict mapping component name to pricing info
        """
        pricing = {}

        for item in bom:
            component_name = item.get("component", "")
            quantity = item.get("quantity", 1)

            if component_name:
                pricing[component_name] = await self.lookup_price(
                    component_name,
                    quantity
                )

        return pricing

    def generate_pricing_report(self, pricing: Dict[str, ComponentPricing]) -> str:
        """Generate readable pricing report."""
        lines = []

        lines.append("=" * 70)
        lines.append("COMPONENT PRICING REPORT")
        lines.append("=" * 70)
        lines.append("")

        total_best = 0.0
        total_average = 0.0

        for component_name, comp_pricing in pricing.items():
            lines.append(f"{component_name}:")

            if comp_pricing.best_price:
                lines.append(f"  Best: ${comp_pricing.best_price.total_usd:.2f} ({comp_pricing.best_price.supplier})")
                lines.append(f"       {comp_pricing.best_price.url}")
                total_best += comp_pricing.best_price.total_usd

            lines.append(f"  Average: ${comp_pricing.average_price:.2f}")
            lines.append(f"  Range: ${comp_pricing.price_range[0]:.2f} - ${comp_pricing.price_range[1]:.2f}")

            total_average += comp_pricing.average_price

            lines.append("")

        lines.append("=" * 70)
        lines.append(f"TOTAL (best prices): ${total_best:.2f}")
        lines.append(f"TOTAL (average): ${total_average:.2f}")
        lines.append("=" * 70)

        return "\n".join(lines)


# Synchronous wrapper for convenience
def lookup_component_price(component_name: str, quantity: int = 1) -> ComponentPricing:
    """
    Synchronous wrapper for price lookup.

    Args:
        component_name: Component to price
        quantity: Quantity needed

    Returns:
        ComponentPricing with results
    """
    pricer = ComponentPricer()
    return asyncio.run(pricer.lookup_price(component_name, quantity))


if __name__ == "__main__":
    # Test pricing lookup
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    print("\n" + "=" * 70)
    print("COMPONENT PRICING LOOKUP TEST")
    print("=" * 70)
    print()

    # Test individual component
    test_components = ["ESP32", "DHT22", "Arduino Nano"]

    async def test_pricing():
        pricer = ComponentPricer()

        for component in test_components:
            print(f"Looking up pricing for: {component}")
            pricing = await pricer.lookup_price(component, quantity=1)

            print(f"  Found {len(pricing.prices)} price(s)")

            if pricing.best_price:
                print(f"  Best: ${pricing.best_price.total_usd:.2f} from {pricing.best_price.supplier}")

            print(f"  Average: ${pricing.average_price:.2f}")
            print()

    asyncio.run(test_pricing())

    print("=" * 70)
    print("Pricing lookup test complete!")
    print("=" * 70)
