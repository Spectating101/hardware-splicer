# Circuit-AI Platform: Complete Electronics Workflow 🎓⚡🔬

**A Unified Platform: Education → Design → Validation → Manufacturing**

[![Status](https://img.shields.io/badge/status-production-green.svg)](https://circuit-ai.io)
[![Version](https://img.shields.io/badge/version-0.4.0-blue.svg)](https://github.com/user/circuit-ai)
[![API](https://img.shields.io/badge/API-v2-success.svg)](V2_API_GUIDE.md)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Circuit-AI is a **complete electronics platform** that combines educational tools, professional PCB validation, and visual intelligence. It takes users from "I want to learn Arduino" to "Here's your validated PCB design ready for manufacturing."

## 🚀 V2 API - NEW! Unified Workflows

The v2 API integrates educational tools with professional validation:

```
Learn → Build → Validate → Manufacture
  ↓       ↓        ↓           ↓
Recipe  Instructions  KiCAD    Gerber
Optimizer  Generator  Validator  Export
```

**Key Features:**
- 🎓 Skill-based routing (BEGINNER → PROFESSIONAL)
- ⚡ End-to-end workflows in one request
- 🔬 Professional KiCAD PCB validation (MNA solver, power tree)
- 📐 Quantitative fixes: "Widen trace to 2mm" (not "traces too thin")

**[→ V2 API Guide](V2_API_GUIDE.md)** | **[→ Integration Details](V2_INTEGRATION_COMPLETE.md)**

---

## 🏗️ Platform Architecture

Circuit-AI v0.4.0 is a **unified platform** with three integrated layers:

### 1️⃣ Educational Layer
*Recipe optimizer, learning paths, build instructions, pricing service*
- 29 project recipes with ROI calculations
- 5 structured learning paths (106 hours curriculum)
- Step-by-step build instructions
- Real-time component pricing (DigiKey + eBay)

### 2️⃣ Professional Validation Layer
*KiCAD integration, circuit solver, power tree validator*
- KiCAD netlist parsing and compilation
- DC operating point solver (Modified Nodal Analysis)
- Power tree validation with trace drop calculations
- Quantitative fixes: "Widen trace from 0.5mm to 2.0mm"

### 3️⃣ Visual Intelligence Layer
*Computer vision, OCR, fault detection*
- YOLOv8-based component detection
- OCR for chip marking identification
- Fault detection (burns, corrosion, broken traces)
- Net tracing and topology reconstruction

**Result:** Complete workflow from education to manufacturing.

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

## 🚀 Quick Start

### V2 API - Unified Workflows

Start the API server:
```bash
python3 api_server.py
```

Test the v2 endpoints:
```bash
# 1. Beginner workflow - Get project recommendations
curl -X POST http://localhost:5000/api/v2/workflow/beginner \
  -H "Content-Type: application/json" \
  -d '{
    "skill_level": 2,
    "inventory": [
      {"id": "esp32", "condition": "new", "quantity": 1},
      {"id": "bme280", "condition": "used", "quantity": 1}
    ],
    "goal": "learning"
  }'

# 2. Complete workflow - End-to-end (recipe → instructions → validation)
curl -X POST http://localhost:5000/api/v2/workflow/complete \
  -H "Content-Type: application/json" \
  -d '{
    "user": {"skill_level": 2, "inventory": [...], "goal": "learning"},
    "project_name": "Air Quality Monitor"
  }'

# 3. KiCAD validation - Professional PCB validation
curl -X POST http://localhost:5000/api/v2/workflow/validate-kicad \
  -F "kicad_file=@my_design.net"
```

**See [V2_API_GUIDE.md](V2_API_GUIDE.md) for complete documentation.**

---

### CLI Tools

The CLI tool supports all modes:

```bash
# 1. Standard Repair Analysis
circuit-ai-cli analyze-image --image my_broken_board.jpg

# 2. Reseller/Jackpot Scan
# (coming soon as a dedicated subcommand)

# 3. Retro Game Verification
# (coming soon as a dedicated subcommand)
```

Or install the package locally:
```bash
pip install .
circuit-ai-cli analyze-image --image my_board.jpg
```

Physics engine helpers:
```bash
circuit-ai-cli validate-kicad my_project.net --auto-hints
circuit-ai-cli validate-design design.json --json
```

Run the API:
```bash
circuit-ai-api --host 0.0.0.0 --port 8000
```

### Helper scripts
- `scripts/design_assistant.py` — LLM co-designer; returns a design narrative plus machine-readable netlist JSON and an NGSpice stub (auto-runs NGSpice if available).
- `scripts/aruco_scan.py` — detect ArUco markers in an image for bench/robot calibration; outputs marker IDs and pixel coordinates as JSON.
- `scripts/splicer_bridge.py` — optional bridge to the adjacent `3d-splicer` repo; submits a board spec to generate a 3D case if that service is running.
- `scripts/demo_bundle.py` — generates a quick demo pack (vision run on a sample PCB + design-assistant output with netlist/Spice) into a folder for sharing.
- `scripts/task_planner.py` — emits a JSON inspection task plan from an image (checklist + detection summary) as a step toward robot/bench integration.
- `scripts/netlist_to_kicad.py` — convert a design_assistant netlist JSON into a minimal KiCad netlist XML for EDA handoff.

---

## 💰 Monetization Strategy

See [COMMERCIAL_STRATEGY.md](COMMERCIAL_STRATEGY.md) for a detailed breakdown of how to spin off and monetize these modules.

---

**Built for the new era of Hardware Intelligence.**
