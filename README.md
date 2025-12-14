# Circuit-AI: The Visual Electronics Debugger 👁️⚡

**Your AI Co-Pilot for Hardware Engineering. It sees what you see.**

[![Status](https://img.shields.io/badge/status-live-green.svg)](https://circuit-ai.io) 
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Circuit-AI is not just a chatbot. It is a **Multimodal Intelligence** system that combines Computer Vision (YOLOv8) with LLM Reasoning (Llama-3/GPT-4) to debug hardware like a senior engineer.

---

## 🚀 The "J.A.R.V.I.S." Experience

Don't just ask questions. **Show it your board.**

1.  **Upload a photo** of your Arduino/PCB setup.
2.  **Circuit-AI analyzes it** in <200ms:
    *   "Detected: Arduino Uno, DHT22 Sensor, Resistor (Color: Red-Red-Brown)."
    *   "Alert: Pinout Mismatch detected on Pin 4."
3.  **You ask:** "Why isn't it working?"
4.  **Circuit-AI replies:** "I see you have the DHT22 signal connected to Pin 4, but your code is initialized for Pin 2. Move the yellow wire."

---

## ✨ Key Features

### 👁️ PCB Defect Detection (Vision)
*   **Solder Bridge Detection:** Instantly spots short circuits.
*   **Missing Components:** Flags unpopulated pads.
*   **Part Verification:** Confirms resistor values via color bands.

### 🧠 Context-Aware Chat (LLM)
*   **"What is this?"**: Point to a chip, and it identifies it.
*   **"Is this wired right?"**: It traces your jumper wires visually.
*   **Data-Sheet Retrieval**: Pulls pinouts for the exact board detected (Uno, Mega, ESP32).

### 🛠️ The Toolkit
*   **Resistor Calculator:** (Visual or Text)
*   **Schematic Generator:** "Draw me a circuit for..."
*   **Code Writer:** Generates Arduino C++ / MicroPython compatible with your specific board.

---

## 📦 Tech Stack

*   **Vision Engine:** YOLOv8 (Custom trained on ElectroCom61 dataset)
*   **Intelligence:** Llama-3.3-70b (via Cerebras)
*   **Backend:** FastAPI (Python)
*   **Frontend:** Next.js 14 (React)

---

## 💰 Pricing

| Tier | Price | Features |
| :--- | :--- | :--- |
| **Maker** | **Free** | 5 visual queries/day, Unlimited text chat |
| **Pro** | **$5/mo** | Unlimited visual debugging, Custom component training |
| **Team** | **Custom** | API Access, Private deployments for PCBA lines |

---

## 🚀 Quick Start

### 1. Run with Docker (Recommended)
```bash
docker-compose up --build
```
Visit `http://localhost:3000`

### 2. Manual Setup
```bash
# Backend
cd src
pip install -r requirements.txt
python -m uvicorn api.v1.main:app --reload

# Frontend
cd circuit-ai-frontend
npm install && npm run dev
```

---

**Stop guessing. Start building.**