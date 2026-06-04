#!/usr/bin/env python3
"""
JLCPCB Integration

Integrates with JLCPCB API for:
- Price quotes
- PCB ordering
- Order tracking

JLCPCB is one of the largest PCB manufacturers with:
- $2 for 5 PCBs (2-layer)
- 24-hour rapid manufacturing
- Global shipping
"""

from dataclasses import dataclass
from typing import List, Dict, Optional
import json


@dataclass
class JLCPCBQuote:
    """JLCPCB price quote"""
    quantity: int
    price_usd: float
    unit_price_usd: float
    lead_time_days: int
    shipping_options: List[Dict]
    board_thickness: str
    copper_weight: str
    surface_finish: str  # "HASL", "LeadFree HASL", "ENIG", etc.


@dataclass
class PCBSpecification:
    """PCB specifications for ordering"""
    width_mm: float
    height_mm: float
    layers: int  # 2, 4, 6
    thickness_mm: float  # 0.6, 0.8, 1.0, 1.2, 1.6, 2.0
    copper_weight_oz: float  # 1, 2
    surface_finish: str  # "HASL", "LeadFree HASL", "ENIG"
    silkscreen_color: str  # "White", "Black", "Red", "Yellow", "Green", "Blue"
    soldermask_color: str  # "Green", "Red", "Yellow", "Blue", "White", "Black"
    via_process: str  # "Tenting vias", "Plugged vias", "Vias not covered"
    min_track_spacing: float  # mm
    min_hole_size: float  # mm


class JLCPCBIntegration:
    """
    Integration with JLCPCB API

    Note: This is a simplified implementation. Real JLCPCB API requires:
    - API key authentication
    - OAuth flow
    - Proper error handling
    - Rate limiting

    For now, we'll provide direct links and cost estimates.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.base_url = "https://cart.jlcpcb.com/quote"

    def get_price_quote(self, spec: PCBSpecification, quantity: int = 5) -> JLCPCBQuote:
        """Get price quote from JLCPCB"""

        # Simplified pricing model (based on JLCPCB's typical prices)
        base_prices = {
            2: {  # 2-layer
                5: 2.00,
                10: 2.00,
                20: 5.00,
                50: 15.00,
                100: 25.00
            },
            4: {  # 4-layer
                5: 7.00,
                10: 8.00,
                20: 15.00,
                50: 50.00,
                100: 80.00
            },
            6: {  # 6-layer
                5: 25.00,
                10: 35.00,
                20: 60.00,
                50: 150.00,
                100: 250.00
            }
        }

        # Get base price
        price = base_prices.get(spec.layers, {}).get(quantity, quantity * 0.50)

        # Size multiplier (over 100x100mm)
        area_cm2 = (spec.width_mm / 10) * (spec.height_mm / 10)
        if area_cm2 > 100:
            price *= (area_cm2 / 100) * 1.2

        # Copper weight multiplier
        if spec.copper_weight_oz >= 2:
            price *= 1.5

        # Surface finish multiplier
        if spec.surface_finish == "ENIG":
            price *= 2.0
        elif spec.surface_finish == "LeadFree HASL":
            price *= 1.2

        # Calculate lead time
        if quantity <= 10:
            lead_time = 2  # 24-48 hours for small orders
        elif quantity <= 50:
            lead_time = 3
        else:
            lead_time = 5

        # Shipping options
        shipping_options = [
            {"method": "Standard", "price_usd": 5.0, "days": "7-15"},
            {"method": "Express", "price_usd": 15.0, "days": "3-5"},
            {"method": "DHL", "price_usd": 25.0, "days": "2-3"}
        ]

        return JLCPCBQuote(
            quantity=quantity,
            price_usd=round(price, 2),
            unit_price_usd=round(price / quantity, 2),
            lead_time_days=lead_time,
            shipping_options=shipping_options,
            board_thickness=f"{spec.thickness_mm}mm",
            copper_weight=f"{spec.copper_weight_oz}oz",
            surface_finish=spec.surface_finish
        )

    def generate_order_url(self, spec: PCBSpecification, gerber_file_path: str) -> str:
        """
        Generate JLCPCB order URL

        Note: Real implementation would upload Gerber file via API.
        For now, we return direct link with pre-filled specs.
        """

        # Build URL with specs
        params = {
            "boardWidth": spec.width_mm,
            "boardHeight": spec.height_mm,
            "boardLayers": spec.layers,
            "boardThickness": spec.thickness_mm,
            "copperWeight": spec.copper_weight_oz,
            "surfaceFinish": spec.surface_finish,
            "silkscreenColor": spec.silkscreen_color,
            "soldermaskColor": spec.soldermask_color
        }

        # Build query string
        query = "&".join([f"{k}={v}" for k, v in params.items()])
        url = f"{self.base_url}?{query}"

        return url

    def get_order_instructions(self, spec: PCBSpecification) -> Dict:
        """Get step-by-step ordering instructions"""

        return {
            "steps": [
                {
                    "step": 1,
                    "action": "Upload Gerber files",
                    "details": "Click 'Add gerber file' and upload your ZIP file",
                    "note": "JLCPCB will auto-detect your board specifications"
                },
                {
                    "step": 2,
                    "action": "Review specifications",
                    "details": f"Verify: {spec.layers}-layer, {spec.width_mm}x{spec.height_mm}mm",
                    "note": "Check board dimensions and layer count"
                },
                {
                    "step": 3,
                    "action": "Select options",
                    "details": f"Surface finish: {spec.surface_finish}, Soldermask: {spec.soldermask_color}",
                    "note": "Most projects work fine with default options"
                },
                {
                    "step": 4,
                    "action": "Choose quantity",
                    "details": "5 PCBs is the minimum (and often cheapest per board)",
                    "note": "Price per board drops significantly at higher quantities"
                },
                {
                    "step": 5,
                    "action": "Select shipping",
                    "details": "Standard (7-15 days) vs Express (3-5 days)",
                    "note": "Standard shipping is usually sufficient"
                },
                {
                    "step": 6,
                    "action": "Review and order",
                    "details": "Review total price and lead time",
                    "note": "Total cost = PCB price + shipping"
                }
            ],
            "tips": [
                "Create an account for faster checkout and order tracking",
                "Check for promo codes (JLCPCB often has discounts)",
                "Standard shipping is reliable despite longer time",
                "Save your specifications for re-ordering",
                "You can order PCB assembly (SMT) for additional cost"
            ],
            "warnings": [
                "Verify board dimensions before ordering",
                "Check that your Gerber files include all layers",
                "Confirm minimum trace/space meets JLCPCB capabilities",
                "Review drill sizes (minimum 0.3mm for standard process)"
            ]
        }

    def estimate_total_cost(self, spec: PCBSpecification, quantity: int = 5,
                           shipping: str = "Standard") -> Dict:
        """Estimate total order cost including shipping"""

        quote = self.get_price_quote(spec, quantity)

        # Get shipping cost
        shipping_cost = next(
            (s['price_usd'] for s in quote.shipping_options if s['method'] == shipping),
            5.0
        )

        total = quote.price_usd + shipping_cost

        return {
            'pcb_cost': quote.price_usd,
            'shipping_cost': shipping_cost,
            'total_cost': round(total, 2),
            'cost_per_board': round(total / quantity, 2),
            'currency': 'USD',
            'estimated_delivery_days': quote.lead_time_days + int(quote.shipping_options[0]['days'].split('-')[0]),
            'breakdown': {
                'pcb': f"${quote.price_usd} ({quantity} boards)",
                'shipping': f"${shipping_cost} ({shipping})",
                'total': f"${round(total, 2)}"
            }
        }


def demo():
    """Demo JLCPCB integration"""
    print("="*70)
    print("  JLCPCB INTEGRATION DEMO")
    print("="*70)
    print()

    integration = JLCPCBIntegration()

    # Sample PCB spec
    spec = PCBSpecification(
        width_mm=100,
        height_mm=80,
        layers=2,
        thickness_mm=1.6,
        copper_weight_oz=1.0,
        surface_finish="LeadFree HASL",
        silkscreen_color="White",
        soldermask_color="Green",
        via_process="Tenting vias",
        min_track_spacing=0.15,
        min_hole_size=0.3
    )

    print("PCB Specification:")
    print(f"  Dimensions: {spec.width_mm}mm x {spec.height_mm}mm")
    print(f"  Layers: {spec.layers}")
    print(f"  Thickness: {spec.thickness_mm}mm")
    print(f"  Copper Weight: {spec.copper_weight_oz}oz")
    print(f"  Surface Finish: {spec.surface_finish}")
    print(f"  Soldermask: {spec.soldermask_color}")
    print()

    # Get quotes for different quantities
    print("Price Quotes:")
    print("-" * 70)
    print(f"{'Quantity':>10} {'PCB Price':>12} {'Per Board':>12} {'Lead Time':>12}")
    print("-" * 70)

    for qty in [5, 10, 20, 50, 100]:
        quote = integration.get_price_quote(spec, qty)
        print(f"{qty:>10} ${quote.price_usd:>11.2f} ${quote.unit_price_usd:>11.2f} {quote.lead_time_days:>10} days")

    print()

    # Total cost estimate
    print("Total Cost Estimate (5 boards, Standard shipping):")
    print("-" * 70)
    cost = integration.estimate_total_cost(spec, quantity=5, shipping="Standard")
    print(f"  PCB Cost:      ${cost['pcb_cost']:.2f}")
    print(f"  Shipping:      ${cost['shipping_cost']:.2f}")
    print(f"  Total:         ${cost['total_cost']:.2f}")
    print(f"  Per Board:     ${cost['cost_per_board']:.2f}")
    print(f"  Delivery:      ~{cost['estimated_delivery_days']} days")
    print()

    # Order URL
    url = integration.generate_order_url(spec, "/tmp/gerbers.zip")
    print("Order URL:")
    print(f"  {url}")
    print()

    # Order instructions
    instructions = integration.get_order_instructions(spec)
    print("Ordering Instructions:")
    print("-" * 70)
    for step in instructions['steps']:
        print(f"{step['step']}. {step['action']}")
        print(f"   {step['details']}")
        print(f"   💡 {step['note']}")
        print()

    print("Tips:")
    for tip in instructions['tips']:
        print(f"  ✓ {tip}")
    print()

    print("Warnings:")
    for warning in instructions['warnings']:
        print(f"  ⚠️  {warning}")


if __name__ == '__main__':
    demo()
