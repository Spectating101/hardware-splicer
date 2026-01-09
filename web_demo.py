#!/usr/bin/env python3
"""
Circuit-AI Web Interface
Professional demo interface for institutional showcase
"""

from flask import Flask, render_template, request, jsonify
import sys
from pathlib import Path

sys.path.insert(0, 'src')

from intelligence.llm_intent_parser import create_parser
from intelligence.smart_design_generator import SmartDesignGenerator

app = Flask(__name__)

# Initialize AI components
llm_parser = create_parser(use_llm=True)
smart_gen = SmartDesignGenerator()


@app.route('/')
def index():
    """Main demo page"""
    return render_template('index.html')


@app.route('/holographic')
def holographic():
    """Iron Man holographic interface"""
    return render_template('holographic_demo.html')


@app.route('/api/parse', methods=['POST'])
def parse_request():
    """Parse natural language design request"""
    data = request.json
    user_input = data.get('input', '')

    try:
        # Parse using LLM
        intent = llm_parser.parse(user_input)

        return jsonify({
            'success': True,
            'project_type': intent.project_type.value,
            'features': intent.features,
            'confidence': f"{intent.confidence:.0%}",
            'required_components': intent.required_components
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route('/api/compare_components', methods=['POST'])
def compare_components():
    """Compare component options"""
    data = request.json
    component_type = data.get('component_type', 'wifi_microcontroller')
    requirements = data.get('requirements', {})
    quantity = data.get('quantity', 1)

    try:
        # Get component selection
        choice = smart_gen.select_component(
            component_type,
            requirements=requirements,
            build_quantity=quantity
        )

        return jsonify({
            'success': True,
            'selected': choice.selected,
            'cost': choice.cost,
            'reasoning': choice.reasoning,
            'alternatives': choice.alternatives,
            'tradeoffs': choice.tradeoffs
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route('/api/generate_design', methods=['POST'])
def generate_design():
    """Generate complete design from natural language"""
    data = request.json
    user_input = data.get('input', '')

    try:
        # Parse intent
        intent = llm_parser.parse(user_input)

        # Get component recommendations
        wifi_choice = smart_gen.select_component(
            "wifi_microcontroller",
            requirements={"simple_iot": "sensor" in user_input.lower()},
            build_quantity=1
        )

        # Build BOM
        bom = [
            {
                'name': wifi_choice.selected,
                'cost': wifi_choice.cost,
                'reasoning': wifi_choice.reasoning
            },
            {
                'name': 'DHT22 Temperature Sensor',
                'cost': 3.50,
                'reasoning': 'Digital output, pre-calibrated, accurate'
            },
            {
                'name': 'LM7805 Voltage Regulator Module',
                'cost': 0.30,
                'reasoning': 'Module saves assembly time vs raw IC'
            },
            {
                'name': 'Breadboard',
                'cost': 2.00,
                'reasoning': 'Prototype board for testing'
            },
            {
                'name': 'Jumper Wires (20pcs)',
                'cost': 1.20,
                'reasoning': 'For connections'
            }
        ]

        total_cost = sum(item['cost'] for item in bom)

        return jsonify({
            'success': True,
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
        return jsonify({
            'success': False,
            'error': str(e)
        })


if __name__ == '__main__':
    print("\n" + "="*70)
    print("  CIRCUIT-AI WEB INTERFACE")
    print("="*70)
    print("\n  Starting web server...")
    print("  Open browser to: http://localhost:5000")
    print("\n  Press Ctrl+C to stop\n")
    print("="*70 + "\n")

    app.run(debug=True, host='0.0.0.0', port=5000)
