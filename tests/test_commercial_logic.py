"""
Unit tests for the Commercial Intelligence Modules.
Verifies logic for Retro-Verify, Salvage Consultant, and Inspection.
"""

import pytest
import sys
import os
# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.vision.enhanced_detector import ComponentDetection, DetectionMethod
from src.intelligence.salvage_consultant import SalvageConsultant
from src.intelligence.retro_authenticator import RetroAuthenticator

# --- Mock Data Helpers ---
def mock_det(name, text=None):
    return ComponentDetection(
        bbox=[0,0,10,10],
        class_name=name,
        confidence=0.9,
        method=DetectionMethod.YOLO,
        metadata={},
        text_content=text
    )

# --- Retro Authenticator Tests ---
def test_retro_fake_blob():
    auth = RetroAuthenticator()
    # Case 1: No ICs found (Blob fake)
    detections = [mock_det("Resistor"), mock_det("Capacitor")]
    result = auth.verify_cartridge(detections, "Pokemon Emerald")
    print(f"DEBUG Result: {result}")
    assert result["verdict"] == "FAKE"
    assert any("No standard IC chips" in r for r in result["reasons"])

def test_retro_typo():
    auth = RetroAuthenticator()
    # Case 2: Chips exist, but typo
    detections = [mock_det("ic_chip")]
    result = auth.verify_cartridge(detections, "Nintondo Inc.")
    assert result["verdict"] == "FAKE"
    assert any("Typos detected" in r for r in result["reasons"])

def test_retro_genuine_emerald():
    auth = RetroAuthenticator()
    # Case 3: Proper Chips + Battery + Correct Text
    detections = [mock_det("ic_chip"), mock_det("battery")]
    result = auth.verify_cartridge(detections, "Nintendo Pokemon Emerald")
    assert result["verdict"] == "LIKELY GENUINE"

def test_retro_missing_battery():
    auth = RetroAuthenticator()
    # Case 4: Emerald without battery
    detections = [mock_det("ic_chip")] # No battery
    result = auth.verify_cartridge(detections, "Pokemon Emerald")
    assert result["verdict"] == "SUSPICIOUS"
    assert any("require a battery" in r for r in result["reasons"])

# --- Salvage Consultant Tests ---
def test_salvage_jackpot():
    cons = SalvageConsultant()
    # Case 1: Xilinx FPGA text
    detections = [mock_det("ic_chip", text="Xilinx Spartan-6")]
    result = cons.evaluate_harvest_potential(detections, "Unknown")
    
    assert len(result["jackpots"]) > 0
    assert result["jackpots"][0]["type"] == "FPGA"

def test_salvage_module_power_supply():
    cons = SalvageConsultant()
    # Case 2: Transformer + Cap4 = Power Supply Stage
    detections = [mock_det("Transformer"), mock_det("Cap4")]
    result = cons.evaluate_harvest_potential(detections, "Unknown")
    
    modules = [m["name"] for m in result["modules"]]
    assert "Power Supply Stage" in modules

def test_salvage_module_audio():
    cons = SalvageConsultant()
    # Case 3: Keyword "Audio" + Chip + Cap
    detections = [mock_det("ic_chip", text="Audio Amp"), mock_det("capacitor")]
    result = cons.evaluate_harvest_potential(detections, "Unknown")
    
    modules = [m["name"] for m in result["modules"]]
    assert "Audio Amplifier Stage" in modules

def test_project_recipe_wifi_switch():
    cons = SalvageConsultant()
    # Case 4: Relay + ESP32 (Wireless) -> Smart WiFi Switch
    detections = [
        mock_det("relay", text="Relay 5V"), 
        mock_det("ic_chip", text="ESP32-WROOM")
    ]
    result = cons.evaluate_harvest_potential(detections, "Unknown")
    
    projects = [p["name"] for p in result["projects"]]
    assert "Smart WiFi Switch" in projects

if __name__ == "__main__":
    # Manually run if pytest not installed
    try:
        print("Running: test_retro_fake_blob")
        test_retro_fake_blob()
        print("Running: test_retro_typo")
        test_retro_typo()
        print("Running: test_retro_genuine_emerald")
        test_retro_genuine_emerald()
        print("Running: test_retro_missing_battery")
        test_retro_missing_battery()
        print("✅ Retro Tests Passed")
        
        print("Running: test_salvage_jackpot")
        test_salvage_jackpot()
        print("Running: test_salvage_module_power_supply")
        test_salvage_module_power_supply()
        print("Running: test_salvage_module_audio")
        test_salvage_module_audio()
        print("Running: test_project_recipe_wifi_switch")
        test_project_recipe_wifi_switch()
        print("✅ Salvage Tests Passed")
    except AssertionError as e:
        print(f"❌ Test Failed: {e}")
