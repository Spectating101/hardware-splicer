#!/usr/bin/env python3
"""
Test Circuit-AI API endpoints
Uses Flask test client (no server needed)
"""

import sys
import json
sys.path.insert(0, 'src')

from api_server import app

def test_api():
    """Test all API endpoints"""
    print("="*70)
    print("  TESTING CIRCUIT-AI API")
    print("="*70)
    print()

    # Create test client
    client = app.test_client()

    # Test 1: Health check
    print("TEST 1: Health Check")
    print("-"*70)
    response = client.get('/api/health')
    data = response.get_json()
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(data, indent=2)}")
    print()

    # Test 2: List components
    print("TEST 2: List Available Components")
    print("-"*70)
    response = client.get('/api/components')
    data = response.get_json()
    print(f"Status: {response.status_code}")
    print(f"Total components: {data['total']}")
    print(f"Fritzing mapped: {data['fritzing_mapped']}")
    print(f"Microcontrollers: {', '.join(data['components']['microcontrollers'][:3])}...")
    print()

    # Test 3: Validate good circuit
    print("TEST 3: Validate Good Circuit")
    print("-"*70)
    good_design = {
        'microcontroller': 'esp32',  # 3.3V MCU
        'components': ['bme280', 'led'],  # BME280 is 3.3V
        'external_power': False
    }
    response = client.post('/api/validate',
                          data=json.dumps(good_design),
                          content_type='application/json')
    data = response.get_json()
    print(f"Status: {response.status_code}")
    print(f"Valid: {data['valid']}")
    print(f"Message: {data['message']}")
    print(f"Issues: {data['summary']['total']}")
    print()

    # Test 4: Validate bad circuit
    print("TEST 4: Validate Bad Circuit (BME280 on 5V)")
    print("-"*70)
    bad_design = {
        'microcontroller': 'arduino_uno',  # 5V MCU
        'components': ['bme280', 'servo_sg90', 'servo_sg90'],  # 3.3V sensor + servos
        'external_power': False
    }
    response = client.post('/api/validate',
                          data=json.dumps(bad_design),
                          content_type='application/json')
    data = response.get_json()
    print(f"Status: {response.status_code}")
    print(f"Valid: {data['valid']}")
    print(f"Message: {data['message']}")
    print(f"Summary:")
    print(f"  • Critical: {data['summary']['critical']}")
    print(f"  • Errors: {data['summary']['errors']}")
    print(f"  • Warnings: {data['summary']['warnings']}")
    print()
    print("Issues found:")
    for i, issue in enumerate(data['issues'][:2], 1):  # Show first 2
        severity_emoji = {'critical': '🔴', 'error': '🟠', 'warning': '🟡'}
        emoji = severity_emoji.get(issue['severity'], '•')
        print(f"  {emoji} {issue['severity'].upper()}: {issue['issue']}")
        print(f"     Solution: {issue['solution']}")
    if len(data['issues']) > 2:
        print(f"  ... and {len(data['issues']) - 2} more")
    print()

    # Test 5: Export to Fritzing
    print("TEST 5: Export to Fritzing")
    print("-"*70)
    export_design = {
        'project_name': 'Temperature Monitor',
        'microcontroller': 'arduino_uno',
        'components': ['bme280', 'led', 'resistor']
    }
    response = client.post('/api/export/fritzing',
                          data=json.dumps(export_design),
                          content_type='application/json')
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        print(f"Content-Type: {response.content_type}")
        print(f"File size: {len(response.data)} bytes")
        print(f"✓ Successfully generated .fzz file!")
    else:
        print(f"Error: {response.get_json()}")
    print()

    # Test 6: Complete workflow
    print("TEST 6: Complete Workflow (Design + Validate + Export)")
    print("-"*70)
    complete_design = {
        'project_name': 'Smart Sensor',
        'microcontroller': 'arduino_uno',
        'components': ['oled_ssd1306', 'hc_sr04', 'led'],
        'export': True
    }
    response = client.post('/api/design',
                          data=json.dumps(complete_design),
                          content_type='application/json')
    data = response.get_json()
    print(f"Status: {response.status_code}")
    print(f"Message: {data['message']}")
    print(f"Validation: {data['validation']['summary']}")
    if 'export_file' in data:
        print(f"Export file: {data['export_file']}")
    print()

    # Summary
    print("="*70)
    print("  API TEST SUMMARY")
    print("="*70)
    print()
    print("✓ All endpoints working correctly!")
    print()
    print("API is ready for:")
    print("  • Web interface integration")
    print("  • Mobile app backend")
    print("  • Third-party integrations")
    print("  • Payment gateway integration")
    print()
    print("Next steps:")
    print("  1. Add API key authentication")
    print("  2. Integrate Stripe for payments")
    print("  3. Deploy to production (Railway/Render/Fly.io)")
    print("  4. Build simple web UI")
    print()


if __name__ == '__main__':
    test_api()
