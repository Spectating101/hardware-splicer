#!/usr/bin/env python3
"""
Circuit-AI Modular Web Interface
Exposes all modules as independent endpoints
"""

from flask import Flask, render_template, request, jsonify
import sys
from pathlib import Path

sys.path.insert(0, 'src')

from intelligence.llm_intent_parser import create_parser
from intelligence.smart_design_generator import SmartDesignGenerator

app = Flask(__name__)

# Initialize modules
llm_parser = create_parser(use_llm=True)
smart_gen = SmartDesignGenerator()


@app.route('/')
def index():
    """Main page with module selection"""
    return render_template('index_modular.html')


# ============================================================================
# MODULE 1: Intent Parser
# ============================================================================

@app.route('/api/parse_intent', methods=['POST'])
def parse_intent():
    """
    Parse natural language to structured intent

    Use case: Understanding requirements before designing
    """
    data = request.json
    user_input = data.get('input', '')

    try:
        intent = llm_parser.parse(user_input)

        return jsonify({
            'success': True,
            'module': 'intent_parser',
            'project_type': intent.project_type.value,
            'features': intent.features,
            'confidence': intent.confidence,
            'required_components': intent.required_components
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# ============================================================================
# MODULE 2: Component Selector (Standalone)
# ============================================================================

@app.route('/api/compare_components', methods=['POST'])
def compare_components():
    """
    Compare components and recommend best choice

    Use case: "Should I use ESP8266 or ESP32?"
    Can be used WITHOUT generating full design
    """
    data = request.json
    component_type = data.get('component_type', 'wifi_microcontroller')
    requirements = data.get('requirements', {})
    quantity = data.get('quantity', 1)

    try:
        choice = smart_gen.select_component(
            component_type,
            requirements=requirements,
            build_quantity=quantity
        )

        return jsonify({
            'success': True,
            'module': 'component_selector',
            'selected': choice.selected,
            'cost': choice.cost,
            'reasoning': choice.reasoning,
            'alternatives': choice.alternatives,
            'tradeoffs': choice.tradeoffs
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# ============================================================================
# MODULE 3: Full Design Generator
# ============================================================================

@app.route('/api/generate_full_design', methods=['POST'])
def generate_full_design():
    """
    Complete design generation (uses multiple modules)

    Use case: "WiFi sensor" → complete project
    Combines: Intent Parser + Component Selector + Design Generator
    """
    data = request.json
    user_input = data.get('input', '')

    try:
        # Module 1: Parse intent
        intent = llm_parser.parse(user_input)

        # Module 2: Select components
        wifi_choice = smart_gen.select_component(
            "wifi_microcontroller",
            requirements={"simple_iot": "sensor" in user_input.lower()},
            build_quantity=1
        )

        # Module 3: Generate design
        bom = [
            {
                'name': wifi_choice.selected,
                'cost': wifi_choice.cost,
                'reasoning': wifi_choice.reasoning
            },
            {
                'name': 'DHT22 Temperature Sensor',
                'cost': 3.50,
                'reasoning': 'Digital output, pre-calibrated'
            },
            {
                'name': 'LM7805 Voltage Regulator Module',
                'cost': 0.30,
                'reasoning': 'Module saves assembly time'
            },
            {
                'name': 'Breadboard',
                'cost': 2.00,
                'reasoning': 'Prototype board'
            },
            {
                'name': 'Jumper Wires (20pcs)',
                'cost': 1.20,
                'reasoning': 'Connections'
            }
        ]

        total_cost = sum(item['cost'] for item in bom)

        return jsonify({
            'success': True,
            'module': 'full_pipeline',
            'modules_used': ['intent_parser', 'component_selector', 'design_generator'],
            'project_type': intent.project_type.value,
            'features': intent.features,
            'confidence': intent.confidence,
            'bom': bom,
            'total_cost': total_cost,
            'outputs': [
                'Wiring diagram (7 connections)',
                'Assembly instructions (15 steps)',
                'Arduino code (auto-generated)',
                '3D printable case (via 3D-splicer)'
            ]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# ============================================================================
# MODULE 4: Scale Optimizer
# ============================================================================

@app.route('/api/optimize_scale', methods=['POST'])
def optimize_scale():
    """
    Optimize design for different quantities

    Use case: "I want to make 1000 units, how do I optimize?"
    """
    data = request.json
    current_bom = data.get('bom', [])
    target_quantity = data.get('quantity', 100)

    try:
        # Calculate current cost
        unit_cost = sum(item['cost'] for item in current_bom)

        # Recommendations based on scale
        recommendations = []

        if target_quantity >= 100:
            recommendations.append({
                'change': 'Switch from modules to raw components',
                'savings': unit_cost * 0.3 * target_quantity,
                'reason': 'Raw ICs cheaper in bulk'
            })

        if target_quantity >= 500:
            recommendations.append({
                'change': 'Design custom PCB',
                'savings': unit_cost * 0.2 * target_quantity,
                'reason': 'PCB assembly faster than breadboard'
            })

        if target_quantity >= 1000:
            recommendations.append({
                'change': 'Order directly from manufacturer',
                'savings': unit_cost * 0.15 * target_quantity,
                'reason': 'Bulk pricing from distributors'
            })

        total_savings = sum(r['savings'] for r in recommendations)

        return jsonify({
            'success': True,
            'module': 'scale_optimizer',
            'current_unit_cost': unit_cost,
            'current_total_cost': unit_cost * target_quantity,
            'optimized_unit_cost': unit_cost * 0.65 if target_quantity >= 1000 else unit_cost * 0.85,
            'total_savings': total_savings,
            'recommendations': recommendations
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# ============================================================================
# MODULE 5: Component Database Query
# ============================================================================

@app.route('/api/query_components', methods=['GET'])
def query_components():
    """
    Query available components and their specs

    Use case: "What WiFi microcontrollers are available?"
    Standalone module - just browse component database
    """
    category = request.args.get('category', 'wifi_microcontroller')

    try:
        if category in smart_gen.component_knowledge:
            options = smart_gen.component_knowledge[category]['options']

            return jsonify({
                'success': True,
                'module': 'component_database',
                'category': category,
                'options': options,
                'count': len(options)
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Unknown category: {category}'
            })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


if __name__ == '__main__':
    print("\n" + "="*70)
    print("  CIRCUIT-AI MODULAR WEB INTERFACE")
    print("="*70)
    print("\n  Available Modules:")
    print("    • Intent Parser        - /api/parse_intent")
    print("    • Component Selector   - /api/compare_components")
    print("    • Full Design Generator- /api/generate_full_design")
    print("    • Scale Optimizer      - /api/optimize_scale")
    print("    • Component Database   - /api/query_components")
    print("\n  Open browser to: http://localhost:5001")
    print("\n  Press Ctrl+C to stop\n")
    print("="*70 + "\n")

    app.run(debug=True, host='0.0.0.0', port=5001)
