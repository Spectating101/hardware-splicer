#!/usr/bin/env python3
"""
Test Circuit-AI Recipe Optimizer API
Demonstrates the "junk drawer to profit" feature
"""

import sys
import json
sys.path.insert(0, 'src')

from api_server import app


def test_recipe_api():
    """Test recipe optimizer endpoints"""
    print("="*70)
    print("  CIRCUIT-AI RECIPE OPTIMIZER API TEST")
    print("  Turn Your Junk Drawer Into Profit")
    print("="*70)
    print()

    client = app.test_client()

    # Example: User's junk drawer inventory
    inventory = [
        {'id': 'arduino_uno', 'condition': 'used', 'quantity': 1},
        {'id': 'esp32', 'condition': 'new', 'quantity': 1},
        {'id': 'bme280', 'condition': 'used', 'quantity': 1},
        {'id': 'oled_ssd1306', 'condition': 'new', 'quantity': 1},
        {'id': 'hc_sr04', 'condition': 'used', 'quantity': 2},
        {'id': 'led', 'condition': 'new', 'quantity': 10},
        {'id': 'resistor', 'condition': 'new', 'quantity': 20},
        {'id': 'servo_sg90', 'condition': 'used', 'quantity': 1},
    ]

    print("YOUR INVENTORY (from junk drawer):")
    print("-"*70)
    for item in inventory:
        print(f"  • {item['quantity']}x {item['id']} ({item['condition']})")
    print()

    # Test 1: Analyze inventory value
    print("TEST 1: Analyze Inventory Value")
    print("-"*70)
    response = client.post('/api/recipes/analyze-inventory',
                          data=json.dumps({'inventory': inventory}),
                          content_type='application/json')
    data = response.get_json()

    print(f"Status: {response.status_code}")
    print(f"Total Value: ${data['total_value']}")
    print(f"Component Count: {data['component_count']}")
    print(f"Categories: {data['categories']}")
    print()

    # Test 2: Generate project recipes
    print("TEST 2: Generate Project Recipes (sorted by ROI)")
    print("-"*70)
    response = client.post('/api/recipes/generate',
                          data=json.dumps({
                              'inventory': inventory,
                              'top_n': 5,
                              'validate': False
                          }),
                          content_type='application/json')
    data = response.get_json()

    print(f"Status: {response.status_code}")
    print(f"Found {data['count']} matching recipes")
    print()

    print("TOP 3 MOST PROFITABLE PROJECTS:")
    print("="*70)

    for i, recipe in enumerate(data['recipes'][:3], 1):
        print(f"\n{i}. {recipe['name']}")
        print(f"   Category: {recipe['category']} | Difficulty: {recipe['difficulty']}")
        print(f"   {recipe['description']}")
        print()

        econ = recipe['economics']
        inv = recipe['inventory']

        print(f"   💰 ECONOMICS:")
        print(f"      Parts Cost:      ${econ['parts_cost']}")
        print(f"      Market Price:    ${econ['market_price_low']}-${econ['market_price_high']}")
        print(f"      Profit Margin:   ${econ['profit_margin']}")
        print(f"      ROI:             {econ['roi_percent']}%")
        print(f"      Missing Parts:   ${econ['missing_parts_cost']}")
        print()

        print(f"   📦 INVENTORY:")
        print(f"      Match:           {inv['match_percent']}%")
        print(f"      Have:            {', '.join(inv['components_owned'][:3])}...")
        if inv['components_needed']:
            print(f"      Need to buy:     {', '.join(inv['components_needed'])}")
        else:
            print(f"      ✅ Have everything!")
        print()
        print("-"*70)

    # Test 3: Generate with validation
    print("\nTEST 3: Generate Recipes WITH Circuit Validation")
    print("-"*70)
    response = client.post('/api/recipes/generate',
                          data=json.dumps({
                              'inventory': inventory,
                              'top_n': 3,
                              'validate': True
                          }),
                          content_type='application/json')
    data = response.get_json()

    print(f"Status: {response.status_code}")
    print()

    for recipe in data['recipes']:
        validation_icon = "✅" if recipe['validated'] else "⚠️"
        print(f"{validation_icon} {recipe['name']}")
        print(f"   Validated: {recipe['validated']}")
        if recipe['validation_issues']:
            print(f"   Issues: {recipe['validation_issues']}")
        print()

    # Test 4: Get shopping list
    print("TEST 4: Get Shopping List for Specific Project")
    print("-"*70)

    # Use a recipe that needs some components
    recipe_name = data['recipes'][0]['name']

    response = client.post('/api/recipes/shopping-list',
                          data=json.dumps({
                              'inventory': inventory,
                              'recipe_name': recipe_name
                          }),
                          content_type='application/json')

    shopping = response.get_json()

    print(f"Status: {response.status_code}")
    print(f"Project: {recipe_name}")
    print()

    if shopping.get('count', 0) > 0:
        print(f"🛒 SHOPPING LIST ({shopping['count']} items):")
        print(f"   Total Cost: ${shopping['total_cost']}")
        print()
        for item in shopping['items']:
            print(f"   • {item['component']} - ${item['price']}")
            print(f"     Buy: {item['buy_url']}")
    else:
        print("✅ No shopping needed - you have everything!")
    print()

    # Summary
    print("="*70)
    print("  RECIPE OPTIMIZER SUMMARY")
    print("="*70)
    print()

    # Get first analysis results
    response = client.post('/api/recipes/analyze-inventory',
                          data=json.dumps({'inventory': inventory}),
                          content_type='application/json')
    analysis = response.get_json()

    # Get top 3 recipes
    response = client.post('/api/recipes/generate',
                          data=json.dumps({
                              'inventory': inventory,
                              'top_n': 3,
                              'validate': False
                          }),
                          content_type='application/json')
    recipes = response.get_json()['recipes']

    print(f"Your junk drawer value: ${analysis['total_value']}")
    print()
    print("Turn it into:")
    total_potential = sum(r['economics']['market_price_high'] for r in recipes)
    print(f"  • Build {len(recipes)} projects")
    print(f"  • Sell for ${total_potential} total")
    print(f"  • Profit: ${total_potential - analysis['total_value']}")
    print(f"  • ROI: {((total_potential / analysis['total_value']) - 1) * 100:.0f}%")
    print()

    print("Top recommendation:")
    top = recipes[0]
    print(f"  → Build: {top['name']}")
    print(f"  → Investment: ${top['economics']['parts_cost']}")
    print(f"  → Sell for: ${top['economics']['market_price_high']}")
    print(f"  → Profit: ${top['economics']['profit_margin']} ({top['economics']['roi_percent']}% ROI)")
    print()

    print("="*70)
    print("  VALUE PROPOSITION")
    print("="*70)
    print()
    print("What Circuit-AI Recipe Optimizer Does:")
    print("  1. Scans your inventory (or you input it)")
    print("  2. Calculates total value of parts you have")
    print("  3. Generates profitable project ideas using those parts")
    print("  4. Ranks by ROI (highest profit first)")
    print("  5. Validates circuits (catches mistakes)")
    print("  6. Creates shopping list for missing parts")
    print("  7. Shows market prices (eBay/Etsy comparable)")
    print()
    print("Perfect for:")
    print("  • Makers with random parts in drawers")
    print("  • Electronics hobbyists wanting to monetize")
    print("  • Teachers planning projects")
    print("  • Hackerspace inventory management")
    print()
    print("This is a KILLER feature for PRO tier!")
    print()


if __name__ == '__main__':
    test_recipe_api()
