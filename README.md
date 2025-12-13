# Circuit-AI: Universal Electronics Assistant (v2.0)

## Overview
Circuit-AI has been upgraded from a simple board recognizer to a **Universal Safety & Identification Assistant**. It now combines Computer Vision (YOLO), Optical Character Recognition (OCR), and a specialized Knowledge Base to assist with electronics repair, debugging, and fabrication.

## Key Features

### 1. Augmented Reality Pinout Overlays
Automatically detects development boards and draws pinout labels directly on the image.
*   **Supported Boards:**
    *   Arduino Uno R3
    *   Arduino Nano V3
    *   Raspberry Pi 4 Model B
    *   ESP32 DevKit V1
*   **Mechanism:** Uses YOLO for bounding boxes and geometric projection based on physical board dimensions (stored in `knowledge_base/boards/*.json`).

### 2. Universal Hazard Inspector
Scans component text for critical safety warnings.
*   **Li-Ion Batteries:** Detects "Li-Ion", "3.7V", "Polymer". Warns about fire hazards and puncturing.
*   **High Voltage:** Detects "110V/220V", "AC". Warns about electrocution risks.
*   **Lasers:** Detects Class 3B/4 warnings.
*   **Mechanism:** `safety/critical_hazards.json` database matched against OCR text.

### 3. Smart Component Identification
Identifies common integrated circuits (ICs) even if the object detector only sees a "chip".
*   **Supported ICs:** NE555 (Timer), LM358 (Op-Amp), LM317/7805 (Regulators), ATmega328P.
*   **Output:** Provides description and key pinout hints (e.g., "Pin 1 is GND").
*   **Mechanism:** `components/common_ics.json` database matched against OCR text.

### 4. Common Mistake Consultant
Provides heuristic advice for generic components.
*   **LEDs:** Warns about polarity (Flat side = Cathode).
*   **Capacitors:** Warns about electrolytic polarity (Stripe = Negative).

## Usage

### Running the Agent
The main entry point is `src/circuit_agent.py`.

```python
import asyncio
from circuit_agent import CircuitAgent

async def analyze(image_path):
    agent = CircuitAgent()
    
    # Load image as base64
    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode('utf-8')
        
    # Query
    response = await agent.process_request("What is this?", image_b64=img_b64)
    
    print(response['llm_response'])
    print(response['vision_report'])
    
    # Save Augmented Image (if available)
    if response['augmented_image_b64']:
        with open("output.png", "wb") as f:
            f.write(base64.b64decode(response['augmented_image_b64']))
```

## Directory Structure
*   `knowledge_base/boards/`: JSON definitions for specific boards (dimensions, headers).
*   `knowledge_base/components/`: JSON for ICs and components.
*   `knowledge_base/safety/`: Critical hazard definitions.
*   `src/vision/enhanced_detector.py`: Core vision logic (YOLO + OCR).
*   `src/circuit_agent.py`: Main agent logic (Orchestrator).
