# Circuit-AI Platform: The Visual Intelligence Engine 👁️⚡

**A Multi-Modal AI Platform for Electronics Analysis, Authentication, and Upcycling.**

[![Status](https://img.shields.io/badge/status-production-green.svg)](https://circuit-ai.io) 
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Circuit-AI is a modular intelligence engine that combines Computer Vision (YOLOv8), Optical Character Recognition (OCR), and expert logic to "see" and understand circuit boards. It powers multiple downstream applications from e-waste appraisal to retro game verification.

---

## 🚀 Powered Applications

This repository contains the core logic for **4 Distinct Commercial Tools**:

### 1. 💎 Circuit-Scout (B2B Appraiser)
*   **For:** E-Waste Resellers, Flippers.
*   **Function:** Scans junk boards for "Jackpot" chips (FPGAs, Vintage CPUs, Gold) and reusable modules.
*   **Key Tech:** `SalvageConsultant` (Reseller Mode).

### 2. 🎮 Retro-Check (Consumer Authenticator)
*   **For:** Retro Gamers, Collectors.
*   **Function:** Instantly verifies Pokemon/Nintendo cartridges by detecting "Black Blob" fakes and typo anomalies.
*   **Key Tech:** `RetroAuthenticator`.

### 3. 🏭 Pocket-AOI (Manufacturing)
*   **For:** Hardware Startups, Assembly Lines.
*   **Function:** Automated Optical Inspection (AOI) to compare production boards against a "Golden Sample".
*   **Key Tech:** `InspectionDiff`, `AdvancedTraceFollower`.

### 4. 🎓 Circuit-AI Classic (Education)
*   **For:** Makers, Students.
*   **Function:** Identifies boards, detects faults (burns/corrosion), and generates repair guides.
*   **Key Tech:** `BoardAnalysisEngine`, `FaultDetector`.

---

## 🛠️ Key Capabilities

*   **Visual Fault Detection:** Adaptive thresholding to find burns, corrosion (green/white oxidation), and broken traces.
*   **OCR Intelligence:** Reads chip markings to identify specific high-value parts (`XC3S50`, `STM32`).
*   **Net Tracing:** Reconstructs circuit topology (Nets, Junctions) from a single photo.
*   **Upcycling Logic:** Identifies functional blocks (e.g., "Power Supply Stage") that can be sawed off and reused.
*   **Topology Confidence:** Spectral/graph analysis with uncertainty bands and library matching hints.

---

## 📦 Tech Stack

*   **Vision:** YOLOv8 (Custom trained), OpenCV (Adaptive/HSV), Tesseract OCR.
*   **Intelligence:** Python-based Logic Engines (`src/intelligence/`).
*   **LLM Integration:** Llama-3.3-70b (via Cerebras) for synthesis.
*   **Backend:** FastAPI.
*   **Packaging:** `pyproject.toml` / `setup.cfg` with console scripts (`circuit-ai-cli`, `circuit-ai-api`).

---

## 🚀 Quick Start (CLI)

The CLI tool supports all modes:

```bash
# 1. Standard Repair Analysis
python circuit_ai_cli.py --image my_broken_board.jpg

# 2. Reseller/Jackpot Scan
python circuit_ai_cli.py --image junk_pile.jpg "salvage scan"

# 3. Retro Game Verification
python circuit_ai_cli.py --image pokemon_emerald.jpg "verify this game"
```

Or install the package locally:
```bash
pip install .
circuit-ai-cli --image my_board.jpg
```

### Helper scripts
- `scripts/design_assistant.py` — LLM co-designer; returns a design narrative plus machine-readable netlist JSON and an NGSpice stub.
- `scripts/aruco_scan.py` — detect ArUco markers in an image for bench/robot calibration; outputs marker IDs and pixel coordinates as JSON.
- `scripts/splicer_bridge.py` — optional bridge to the adjacent `3d-splicer` repo; submits a board spec to generate a 3D case if that service is running.
- `scripts/demo_bundle.py` — generates a quick demo pack (vision run on a sample PCB + design-assistant output with netlist/Spice) into a folder for sharing.

---

## 💰 Monetization Strategy

See [COMMERCIAL_STRATEGY.md](COMMERCIAL_STRATEGY.md) for a detailed breakdown of how to spin off and monetize these modules.

---

**Built for the new era of Hardware Intelligence.**
