#!/usr/bin/env python3
"""
Device Diagnostic Engine
Combines computer vision fault detection with repair guide recommendations
Analyzes photos of broken devices and suggests fixes
"""

from typing import Dict, List, Optional, Tuple
from pathlib import Path

# Optional imports for image processing
try:
    import numpy as np
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

# Import our existing modules
try:
    from intelligence.repair_guide_generator import RepairGuideGenerator
except ImportError:
    from repair_guide_generator import RepairGuideGenerator

# Fault detector requires OpenCV/numpy, import conditionally
FaultDetector = None
if CV2_AVAILABLE:
    try:
        from intelligence.fault_detector import FaultDetector as FD
        FaultDetector = FD
    except ImportError:
        try:
            from fault_detector import FaultDetector as FD
            FaultDetector = FD
        except ImportError:
            pass


class DeviceDiagnosticEngine:
    """
    AI-powered device diagnostics combining visual analysis with repair recommendations.

    Workflow:
    1. User uploads photo of broken device
    2. Computer vision identifies physical damage
    3. System maps damage to likely issues
    4. Returns repair guide recommendations
    """

    def __init__(self):
        """Initialize diagnostic engine."""
        if CV2_AVAILABLE and FaultDetector is not None:
            self.fault_detector = FaultDetector()
        else:
            self.fault_detector = None
        self.repair_guide_gen = RepairGuideGenerator()

        # Map visual faults to repair guides
        self.fault_to_repair_map = {
            'cracked_screen': 'iPhone Screen Replacement',
            'swollen_battery': 'iPhone Battery Replacement',
            'corrosion': 'iPhone Water Damage',
            'charging_port_debris': 'iPhone Charging Port',
            'burned_component': 'iPhone Water Damage',  # Often related
        }

    def diagnose_from_image(self, image_path: str, device_type: str = 'iPhone') -> Dict:
        """
        Analyze device image and return diagnosis with repair recommendations.

        Args:
            image_path: Path to image of broken device
            device_type: Type of device (iPhone, Android, Laptop, etc.)

        Returns:
            Dict with diagnosis, confidence, and repair guide recommendations
        """
        if not CV2_AVAILABLE or self.fault_detector is None:
            return {
                'error': 'Computer vision analysis not available (OpenCV not installed)',
                'suggestion': 'Use symptom-based diagnosis instead or install opencv-python'
            }

        # Load image
        image = cv2.imread(image_path)
        if image is None:
            return {'error': 'Failed to load image'}

        # Convert BGR to RGB
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        # Detect faults
        faults = self.fault_detector.detect_faults(image_rgb)

        # Analyze faults and recommend repairs
        diagnosis = self._analyze_faults(faults, device_type)

        return diagnosis

    def diagnose_from_symptoms(self, symptoms: List[str], device_type: str = 'iPhone') -> Dict:
        """
        Diagnose device based on user-reported symptoms (no image).

        Args:
            symptoms: List of symptoms (e.g., ["won't charge", "gets hot"])
            device_type: Type of device

        Returns:
            Dict with possible issues and repair guide recommendations
        """
        # Comprehensive symptom to issue mapping (100+ symptoms)
        symptom_map = {
            # ============================================================
            # SCREEN ISSUES (iPhone & Android)
            # ============================================================
            'cracked screen': 'iPhone Screen Replacement',
            'broken screen': 'iPhone Screen Replacement',
            'shattered screen': 'iPhone Screen Replacement',
            'screen cracked': 'iPhone Screen Replacement',
            'glass broken': 'iPhone Screen Replacement',
            'black screen': 'iPhone Screen Replacement',
            'screen black': 'iPhone Screen Replacement',
            'blank screen': 'iPhone Screen Replacement',
            'screen won\'t turn on': 'iPhone Screen Replacement',
            'screen not working': 'iPhone Screen Replacement',
            'display not working': 'iPhone Screen Replacement',
            'screen not responding': 'iPhone Screen Replacement',
            'touch not working': 'iPhone Screen Replacement',
            'touchscreen broken': 'iPhone Screen Replacement',
            'no touch response': 'iPhone Screen Replacement',
            'screen unresponsive': 'iPhone Screen Replacement',
            'dead pixels': 'iPhone Screen Replacement',
            'lines on screen': 'iPhone Screen Replacement',
            'screen lines': 'iPhone Screen Replacement',
            'vertical lines': 'iPhone Screen Replacement',
            'horizontal lines': 'iPhone Screen Replacement',
            'screen flickering': 'iPhone Screen Replacement',
            'flickering display': 'iPhone Screen Replacement',
            'screen flashing': 'iPhone Screen Replacement',
            'green tint': 'iPhone Screen Replacement',
            'yellow screen': 'iPhone Screen Replacement',
            'discolored screen': 'iPhone Screen Replacement',
            'screen dim': 'iPhone Screen Replacement',
            'dark screen': 'iPhone Screen Replacement',
            'backlight not working': 'iPhone Screen Replacement',

            # ============================================================
            # BATTERY ISSUES (All devices)
            # ============================================================
            'battery drains fast': 'iPhone Battery Replacement',
            'battery dies quickly': 'iPhone Battery Replacement',
            'battery not lasting': 'iPhone Battery Replacement',
            'poor battery life': 'iPhone Battery Replacement',
            'battery percentage drops': 'iPhone Battery Replacement',
            'shuts down randomly': 'iPhone Battery Replacement',
            'random shutdowns': 'iPhone Battery Replacement',
            'turns off unexpectedly': 'iPhone Battery Replacement',
            'shuts down at 20%': 'iPhone Battery Replacement',
            'shuts down at 30%': 'iPhone Battery Replacement',
            'dies at 50%': 'iPhone Battery Replacement',
            'phone getting hot': 'iPhone Battery Replacement',
            'phone overheating': 'iPhone Battery Replacement',
            'gets hot while charging': 'iPhone Battery Replacement',
            'warm to touch': 'iPhone Battery Replacement',
            'battery swollen': 'iPhone Battery Replacement',
            'battery bulging': 'iPhone Battery Replacement',
            'back popping off': 'iPhone Battery Replacement',
            'screen lifting': 'iPhone Battery Replacement',
            'battery expanded': 'iPhone Battery Replacement',
            'battery percentage jumps': 'iPhone Battery Replacement',
            'percentage inaccurate': 'iPhone Battery Replacement',
            'shows wrong percentage': 'iPhone Battery Replacement',
            'battery health low': 'iPhone Battery Replacement',
            'maximum capacity low': 'iPhone Battery Replacement',
            'service battery message': 'iPhone Battery Replacement',

            # ============================================================
            # CHARGING ISSUES (All devices)
            # ============================================================
            'won\'t charge': 'iPhone Charging Port',
            'not charging': 'iPhone Charging Port',
            'doesn\'t charge': 'iPhone Charging Port',
            'charging not working': 'iPhone Charging Port',
            'no charging': 'iPhone Charging Port',
            'charging cable loose': 'iPhone Charging Port',
            'cable falls out': 'iPhone Charging Port',
            'loose charging port': 'iPhone Charging Port',
            'wiggle to charge': 'iPhone Charging Port',
            'have to hold cable': 'iPhone Charging Port',
            'charges intermittently': 'iPhone Charging Port',
            'charges on and off': 'iPhone Charging Port',
            'charging stops': 'iPhone Charging Port',
            'slow charging': 'iPhone Charging Port',
            'takes forever to charge': 'iPhone Charging Port',
            'charging very slow': 'iPhone Charging Port',
            'moisture detected': 'iPhone Charging Port',
            'liquid detected': 'iPhone Charging Port',
            'charging disabled': 'iPhone Charging Port',
            'port not working': 'iPhone Charging Port',
            'lint in port': 'iPhone Charging Port',
            'dirty charging port': 'iPhone Charging Port',
            'charging port broken': 'iPhone Charging Port',

            # ============================================================
            # WATER DAMAGE (All devices)
            # ============================================================
            'dropped in water': 'iPhone Water Damage',
            'fell in water': 'iPhone Water Damage',
            'water damage': 'iPhone Water Damage',
            'got wet': 'iPhone Water Damage',
            'dropped in toilet': 'iPhone Water Damage',
            'dropped in pool': 'iPhone Water Damage',
            'rain damage': 'iPhone Water Damage',
            'speaker sounds muffled': 'iPhone Water Damage',
            'speaker quiet': 'iPhone Water Damage',
            'crackling speaker': 'iPhone Water Damage',
            'distorted audio': 'iPhone Water Damage',
            'camera foggy': 'iPhone Water Damage',
            'camera blurry': 'iPhone Water Damage',
            'moisture in camera': 'iPhone Water Damage',
            'corrosion visible': 'iPhone Water Damage',
            'white residue': 'iPhone Water Damage',
            'green corrosion': 'iPhone Water Damage',
            'mic not working': 'iPhone Water Damage',
            'can\'t hear me': 'iPhone Water Damage',
            'microphone broken': 'iPhone Water Damage',

            # ============================================================
            # CAMERA ISSUES
            # ============================================================
            'camera not working': 'iPhone Camera Not Working',
            'camera black screen': 'iPhone Camera Not Working',
            'rear camera broken': 'iPhone Camera Not Working',
            'front camera not working': 'iPhone Camera Not Working',
            'camera won\'t open': 'iPhone Camera Not Working',
            'camera app crashes': 'iPhone Camera Not Working',
            'blurry photos': 'iPhone Camera Not Working',
            'can\'t focus': 'iPhone Camera Not Working',
            'camera shaking': 'iPhone Camera Not Working',

            # ============================================================
            # BUTTONS & CONTROLS
            # ============================================================
            'power button stuck': 'iPhone Button Repair',
            'power button not working': 'iPhone Button Repair',
            'can\'t turn on': 'iPhone Button Repair',
            'volume buttons broken': 'iPhone Button Repair',
            'volume stuck': 'iPhone Button Repair',
            'home button broken': 'iPhone Button Repair',
            'home button not clicking': 'iPhone Button Repair',
            'touch id not working': 'iPhone Button Repair',

            # ============================================================
            # CONNECTIVITY ISSUES
            # ============================================================
            'wifi not working': 'iPhone WiFi Repair',
            'can\'t connect wifi': 'iPhone WiFi Repair',
            'wifi greyed out': 'iPhone WiFi Repair',
            'bluetooth not working': 'iPhone WiFi Repair',
            'no signal': 'iPhone Antenna Repair',
            'no service': 'iPhone Antenna Repair',
            'poor reception': 'iPhone Antenna Repair',
            'calls dropping': 'iPhone Antenna Repair',

            # ============================================================
            # PERFORMANCE ISSUES
            # ============================================================
            'phone slow': 'iPhone Performance Issues',
            'lagging': 'iPhone Performance Issues',
            'freezing': 'iPhone Performance Issues',
            'apps crashing': 'iPhone Performance Issues',
            'keeps restarting': 'iPhone Performance Issues',
            'boot loop': 'iPhone Performance Issues',
            'stuck on apple logo': 'iPhone Performance Issues',

            # ============================================================
            # LAPTOP-SPECIFIC ISSUES
            # ============================================================
            'laptop won\'t turn on': 'Laptop Not Charging',
            'laptop not charging': 'Laptop Not Charging',
            'battery not detected': 'Laptop Not Charging',
            'plugged in not charging': 'Laptop Not Charging',
            'laptop overheating': 'Laptop Overheating',
            'fan loud': 'Laptop Overheating',
            'keyboard not working': 'Laptop Keyboard Replacement',
            'keys not working': 'Laptop Keyboard Replacement',
            'sticky keys': 'Laptop Keyboard Replacement',
            'laptop screen broken': 'Laptop Screen Replacement',
            'laptop screen cracked': 'Laptop Screen Replacement',
            'laptop slow': 'Laptop SSD/RAM Upgrade',
            'laptop freezing': 'Laptop SSD/RAM Upgrade',
        }

        # Find matching repair guides
        recommendations = []
        confidence_scores = {}

        for symptom in symptoms:
            symptom_lower = symptom.lower()
            for key, repair_guide in symptom_map.items():
                if key in symptom_lower:
                    if repair_guide not in confidence_scores:
                        confidence_scores[repair_guide] = 0
                    confidence_scores[repair_guide] += 1

        # Sort by confidence
        sorted_repairs = sorted(
            confidence_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )

        # Generate recommendations
        for repair_guide, score in sorted_repairs:
            guide = self.repair_guide_gen.generate_repair_guide(repair_guide)
            if guide.get('status') != 'coming_soon':
                recommendations.append({
                    'issue': repair_guide,
                    'confidence': min(score / len(symptoms), 1.0),
                    'guide_summary': {
                        'difficulty': guide.get('difficulty'),
                        'time': guide.get('repair_time'),
                        'cost': guide.get('estimated_cost'),
                        'steps': len(guide.get('steps', []))
                    }
                })

        return {
            'device_type': device_type,
            'symptoms_analyzed': symptoms,
            'diagnosis_method': 'symptom_analysis',
            'recommendations': recommendations,
            'top_recommendation': recommendations[0] if recommendations else None
        }

    def _analyze_faults(self, faults: Dict, device_type: str) -> Dict:
        """
        Analyze detected faults and generate repair recommendations.

        Args:
            faults: Fault detection results from FaultDetector
            device_type: Type of device

        Returns:
            Diagnosis with repair recommendations
        """
        recommendations = []
        detected_issues = []

        # Check each fault type
        if faults.get('burned_components', {}).get('detected'):
            severity = faults['burned_components'].get('severity', 0)
            detected_issues.append({
                'type': 'burned_component',
                'severity': severity,
                'description': faults['burned_components'].get('description')
            })

            # Burned components often indicate water damage or short circuit
            guide = self.repair_guide_gen.generate_repair_guide('iPhone Water Damage')
            if guide.get('status') != 'coming_soon':
                recommendations.append({
                    'issue': 'Burned Component (Possible Water Damage)',
                    'confidence': min(severity, 0.9),
                    'repair_guide': 'iPhone Water Damage',
                    'note': 'Burned components often result from water damage or short circuits. Professional repair recommended.',
                    'difficulty': 'expert'
                })

        if faults.get('corrosion', {}).get('detected'):
            severity = faults['corrosion'].get('severity', 0)
            detected_issues.append({
                'type': 'corrosion',
                'severity': severity,
                'description': faults['corrosion'].get('description')
            })

            guide = self.repair_guide_gen.generate_repair_guide('iPhone Water Damage')
            if guide.get('status') != 'coming_soon':
                recommendations.append({
                    'issue': 'Corrosion Detected',
                    'confidence': min(severity, 0.95),
                    'repair_guide': 'iPhone Water Damage',
                    'note': 'Corrosion indicates water/liquid exposure. Immediate cleaning required to prevent further damage.',
                    'difficulty': 'hard'
                })

        if faults.get('broken_traces', {}).get('detected'):
            severity = faults['broken_traces'].get('severity', 0)
            detected_issues.append({
                'type': 'broken_trace',
                'severity': severity,
                'description': faults['broken_traces'].get('description')
            })

            recommendations.append({
                'issue': 'Broken Circuit Traces',
                'confidence': min(severity, 0.8),
                'repair_guide': 'Professional Board Repair',
                'note': 'Broken traces on logic board require microsoldering. Recommend professional repair.',
                'difficulty': 'expert'
            })

        # Overall assessment
        overall_condition = faults.get('overall_condition', 'Unknown')

        return {
            'device_type': device_type,
            'diagnosis_method': 'computer_vision',
            'overall_condition': overall_condition,
            'detected_issues': detected_issues,
            'recommendations': recommendations,
            'top_recommendation': recommendations[0] if recommendations else None,
            'visual_analysis': {
                'burned_components': faults.get('burned_components'),
                'corrosion': faults.get('corrosion'),
                'broken_traces': faults.get('broken_traces')
            }
        }

    def get_full_repair_plan(self, diagnosis: Dict) -> Dict:
        """
        Get complete repair plan with detailed guides for all recommendations.

        Args:
            diagnosis: Diagnosis result from diagnose_from_image or diagnose_from_symptoms

        Returns:
            Complete repair plan with full guides
        """
        repair_plan = {
            'diagnosis_summary': {
                'device_type': diagnosis.get('device_type'),
                'overall_condition': diagnosis.get('overall_condition'),
                'method': diagnosis.get('diagnosis_method')
            },
            'repair_guides': []
        }

        # Get full guides for each recommendation
        for rec in diagnosis.get('recommendations', []):
            guide_name = rec.get('repair_guide')
            if guide_name:
                full_guide = self.repair_guide_gen.generate_repair_guide(guide_name)
                repair_plan['repair_guides'].append({
                    'recommendation': rec,
                    'full_guide': full_guide
                })

        return repair_plan


def demo_diagnostic_engine():
    """Demo the diagnostic engine with example scenarios."""
    engine = DeviceDiagnosticEngine()

    print("="*70)
    print("  DEVICE DIAGNOSTIC ENGINE - DEMO")
    print("="*70)
    print()

    # Test 1: Symptom-based diagnosis
    print("Test 1: Symptom-Based Diagnosis")
    print("-" * 70)

    symptoms = [
        "won't charge",
        "charging cable falls out",
        "charging port feels loose"
    ]

    diagnosis = engine.diagnose_from_symptoms(symptoms, 'iPhone')

    print(f"Symptoms: {', '.join(symptoms)}")
    print(f"Analysis Method: {diagnosis['diagnosis_method']}")
    print(f"\nTop Recommendation:")
    if diagnosis['top_recommendation']:
        top = diagnosis['top_recommendation']
        print(f"  Issue: {top['issue']}")
        print(f"  Confidence: {top['confidence']*100:.0f}%")
        print(f"  Difficulty: {top['guide_summary']['difficulty']}")
        print(f"  Estimated Time: {top['guide_summary']['time']}")
        print(f"  Estimated Cost: {top['guide_summary']['cost']}")

    print()
    print("-" * 70)

    # Test 2: Another symptom scenario
    print("\nTest 2: Battery Issue Diagnosis")
    print("-" * 70)

    symptoms2 = [
        "battery drains fast",
        "phone shuts down at 30%",
        "phone getting hot"
    ]

    diagnosis2 = engine.diagnose_from_symptoms(symptoms2, 'iPhone')

    print(f"Symptoms: {', '.join(symptoms2)}")
    print(f"\nRecommendations ({len(diagnosis2['recommendations'])} found):")
    for i, rec in enumerate(diagnosis2['recommendations'][:3], 1):
        print(f"  {i}. {rec['issue']} (Confidence: {rec['confidence']*100:.0f}%)")
        print(f"     Difficulty: {rec['guide_summary']['difficulty']}, Time: {rec['guide_summary']['time']}")

    print()
    print("="*70)
    print("  DIAGNOSTIC ENGINE READY")
    print("="*70)


if __name__ == '__main__':
    demo_diagnostic_engine()
