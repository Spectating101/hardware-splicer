#!/usr/bin/env python3
"""
Generate demo/mock data for testing without trained model.
Useful for frontend development and API testing.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import random
from datetime import datetime
from loguru import logger

def generate_mock_detection():
    """Generate realistic mock component detections."""

    components = [
        'Arduino-Uno', 'Resistor', 'Capacitor-10mf', 'LED-Light',
        'ESP32', 'Relay-Module', 'Servo-Motor', 'LCD-Display',
        'BJT-Transistor', 'Diode', 'OLED-Display', 'Motor-Driver'
    ]

    detections = []
    num_components = random.randint(3, 8)

    for i in range(num_components):
        component = random.choice(components)
        detections.append({
            'id': i,
            'name': component,
            'confidence': round(random.uniform(0.75, 0.98), 2),
            'bbox': {
                'x1': random.randint(50, 400),
                'y1': random.randint(50, 400),
                'x2': random.randint(450, 600),
                'y2': random.randint(450, 600)
            },
            'category': random.choice(['Microcontroller', 'Passive', 'Display', 'Actuator', 'Semiconductor']),
            'educational_value': round(random.uniform(7.0, 10.0), 1),
            'market_value': round(random.uniform(0.5, 15.0), 2)
        })

    return detections

def generate_mock_projects():
    """Generate mock project recommendations."""

    projects = [
        {
            'id': 1,
            'title': 'Smart Home Temperature Monitor',
            'description': 'Build a WiFi-enabled temperature monitoring system with real-time alerts.',
            'difficulty': 'Beginner',
            'estimated_time': '2-3 hours',
            'required_components': ['Arduino-Uno', 'Temperature-Sensor', 'LCD-Display', 'WiFi-Module'],
            'skills_learned': ['Arduino programming', 'Sensor integration', 'WiFi connectivity'],
            'educational_value': 9.2
        },
        {
            'id': 2,
            'title': 'LED Matrix Display',
            'description': 'Create an 8x8 LED matrix display to show scrolling text and animations.',
            'difficulty': 'Intermediate',
            'estimated_time': '3-4 hours',
            'required_components': ['Arduino-Nano', 'LED-Light', 'Resistor', 'Shift-Register'],
            'skills_learned': ['Multiplexing', 'Timing control', 'Pattern generation'],
            'educational_value': 8.5
        },
        {
            'id': 3,
            'title': 'Servo-Controlled Robot Arm',
            'description': 'Build a 3-axis robot arm controlled via smartphone app.',
            'difficulty': 'Advanced',
            'estimated_time': '6-8 hours',
            'required_components': ['Arduino-Mega', 'Servo-Motor', 'Motor-Driver', 'Bluetooth-Module'],
            'skills_learned': ['Inverse kinematics', 'Bluetooth control', 'Motor coordination'],
            'educational_value': 9.8
        },
        {
            'id': 4,
            'title': 'Solar-Powered Weather Station',
            'description': 'Complete weather station with solar power and data logging.',
            'difficulty': 'Intermediate',
            'estimated_time': '4-5 hours',
            'required_components': ['ESP32', 'Temperature-Sensor', 'Humidity-Sensor', 'OLED-Display'],
            'skills_learned': ['Power management', 'Data logging', 'IoT connectivity'],
            'educational_value': 9.0
        }
    ]

    return random.sample(projects, random.randint(2, 4))

def generate_mock_analysis_result():
    """Generate complete mock analysis result."""

    detections = generate_mock_detection()
    projects = generate_mock_projects()

    result = {
        'analysis_id': f'demo_{datetime.now().strftime("%Y%m%d_%H%M%S")}',
        'status': 'completed',
        'timestamp': datetime.now().isoformat(),
        'processing_time': round(random.uniform(2.5, 5.5), 2),
        'num_components': len(detections),
        'components': detections,
        'functionality': {
            'computing_capability': random.choice(['Basic', 'Moderate', 'Advanced']),
            'power_requirements': f'{random.randint(5, 24)}V DC',
            'complexity_level': random.choice(['Beginner-friendly', 'Intermediate', 'Advanced']),
            'primary_applications': ['IoT', 'Robotics', 'Home Automation', 'Learning']
        },
        'projects': projects,
        'educational_content': {
            'total_value': round(sum(d['educational_value'] for d in detections), 1),
            'learning_topics': [
                'Microcontroller programming',
                'Circuit design basics',
                'Sensor integration',
                'Power management'
            ],
            'recommended_tutorials': [
                'Arduino Getting Started Guide',
                'ESP32 WiFi Projects',
                'Sensor Interfacing Basics'
            ]
        },
        'market_analysis': {
            'total_value': round(sum(d['market_value'] for d in detections), 2),
            'salvage_potential': random.choice(['High', 'Moderate', 'Low']),
            'reusability_score': round(random.uniform(7.0, 9.5), 1)
        }
    }

    return result

def save_demo_data():
    """Save demo data to files for testing."""

    logger.info("🎨 Generating Demo Data")
    logger.info("=" * 60)

    demo_dir = Path("data/demo")
    demo_dir.mkdir(parents=True, exist_ok=True)

    # Generate multiple analysis results
    for i in range(5):
        result = generate_mock_analysis_result()
        output_file = demo_dir / f"analysis_demo_{i+1}.json"

        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)

        logger.info(f"✅ Generated: {output_file.name}")
        logger.info(f"   Components: {result['num_components']}")
        logger.info(f"   Projects: {len(result['projects'])}")

    # Generate summary
    summary = {
        'generated_at': datetime.now().isoformat(),
        'total_analyses': 5,
        'purpose': 'Frontend development and API testing',
        'note': 'This is mock data for development. Real analysis requires trained model.'
    }

    with open(demo_dir / 'README.json', 'w') as f:
        json.dump(summary, f, indent=2)

    logger.info(f"\n✅ Demo data saved to: {demo_dir}")
    logger.info("\n💡 Usage:")
    logger.info("   - Use for frontend development")
    logger.info("   - Test API endpoints without model")
    logger.info("   - Verify UI components render correctly")

if __name__ == "__main__":
    save_demo_data()

    # Print example
    logger.info("\n📋 Example Analysis Result:")
    example = generate_mock_analysis_result()
    logger.info(f"   Components detected: {example['num_components']}")
    logger.info(f"   Top component: {example['components'][0]['name']}")
    logger.info(f"   Confidence: {example['components'][0]['confidence']}")
    logger.info(f"   Project recommendations: {len(example['projects'])}")
    logger.info(f"   Total educational value: {example['educational_content']['total_value']}")
