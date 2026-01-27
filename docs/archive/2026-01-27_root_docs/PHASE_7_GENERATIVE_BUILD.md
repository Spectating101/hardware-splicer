# Phase 7: Intelligent Design & Resource-Aware Fabrication

**Status**: ✅ COMPLETE

## Overview

Phase 7 adds **generative build capability** to Dum-E - the ability to understand natural language requests and automatically generate complete designs with intelligent resource optimization.

**User says**: `"build me a WiFi temperature sensor"`
**Dum-E does**: Understands intent → Checks inventory → Substitutes if needed → Uses scraps → Generates design → Builds it

## What's New

### Natural Language Understanding
```bash
# These all work:
"build me a WiFi temperature sensor"
"make an LED blinker"
"I need a motor controller"
"create a battery-powered humidity monitor"
```

The system automatically:
- Detects project type (sensor, actuator, controller, etc.)
- Extracts features (WiFi, temperature, LED, motor, etc.)
- Determines required components
- Parses constraints (size, budget, power)

### Resource-Aware Design

**Component Substitution**:
```python
# No ESP32 available?
ESP32 → Arduino Nano + ESP8266

# No DHT22?
DHT22 → DHT11 or BME280
```

**Scrap Component Utilization**:
```
User: "build me a temperature sensor"
System: "Using DHT22 (SCRAP, harvested from broken weather station)"
→ Saved $3.50, reduced waste
```

**Smart Inventory Management**:
- Tracks component condition (NEW, USED, SCRAP)
- Prefers scraps over new components
- Harvests components from broken boards
- Calculates cost savings

## Architecture

### 4-Module Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                    Natural Language Request                      │
│                  "build me a WiFi sensor"                        │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  1. INTENT PARSER (intent_parser.py)                            │
│     • Pattern matching & keyword extraction                      │
│     • Project type detection                                     │
│     • Feature extraction                                         │
│     • Component requirement determination                        │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  2. RESOURCE MANAGER (resource_manager.py)                      │
│     • Check component availability                               │
│     • Find substitutes (ESP32 → Arduino + WiFi)                 │
│     • Prefer scrap components                                    │
│     • Calculate feasibility                                      │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  3. DESIGN GENERATOR (design_generator.py)                      │
│     • Generate BOM (Bill of Materials)                           │
│     • Create wiring schematic                                    │
│     • Optimize component placement                               │
│     • Generate assembly instructions                             │
│     • Estimate build time                                        │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  4. BUILD ORCHESTRATOR (build_project.py)                       │
│     • Preview design (ASCII schematic)                           │
│     • Reserve components from inventory                          │
│     • Control robot arm for assembly                             │
│     • Wire connections                                           │
│     • Test and verify                                            │
└─────────────────────────────────────────────────────────────────┘
```

## Files Created

### 1. `/src/intelligence/intent_parser.py` (325 lines)
Parses natural language into structured design specifications.

**Key Features**:
- Project type detection (sensor, actuator, controller, display, etc.)
- Feature extraction (temperature, WiFi, LED, motor, etc.)
- Constraint parsing (size, budget, power)
- Component requirement mapping

**Example**:
```python
from intelligence.intent_parser import IntentParser

parser = IntentParser()
intent = parser.parse("build me a WiFi temperature sensor")

# Returns:
# DesignIntent(
#     project_type=SENSOR,
#     features=["wifi", "temperature"],
#     required_components=["ESP32", "DHT22", "power_supply", ...],
#     confidence=0.9
# )
```

### 2. `/src/intelligence/resource_manager.py` (500 lines)
Manages component inventory with intelligent substitution.

**Key Features**:
- Component inventory (JSON persistence)
- Scrap component tracking
- Component equivalence database
- Availability checking
- Adaptive substitution
- Scrap board harvesting

**Example**:
```python
from intelligence.resource_manager import ResourceManager, Component

mgr = ResourceManager()

# Add components
mgr.add_component(Component(
    name="ESP32",
    quantity=1,
    condition=ComponentCondition.NEW,
    cost_usd=8.00
))

# Check availability
availability = mgr.check_availability(["ESP32", "DHT22"])
# Returns: {available, missing, substitutable, feasible}
```

### 3. `/src/intelligence/design_generator.py` (550 lines)
Generates complete designs from intent and resources.

**Key Features**:
- BOM generation
- Wiring schematic creation
- Component placement optimization
- Assembly instruction generation
- Build time estimation
- Design templates (WiFi sensor, LED blinker, motor controller)

**Example**:
```python
from intelligence.design_generator import DesignGenerator

generator = DesignGenerator()
design = generator.generate_design(intent, resource_mgr)

# Returns:
# Design(
#     bill_of_materials=[...],
#     wiring=[...],
#     placements=[...],
#     assembly_steps=[...],
#     estimated_build_time_min=24.5
# )
```

### 4. `/scripts/build_project.py` (410 lines)
CLI orchestrator for the complete pipeline.

**Key Features**:
- Natural language CLI
- Design preview mode
- Auto-build mode
- Scrap project suggestions
- Inventory management

## Usage

### Basic Build

```bash
# Build from natural language
python scripts/build_project.py "build me a WiFi temperature sensor"

# Output:
# [Phase 1/5] Parsing request...
#   → Project type: sensor
#   → Features: wifi, temperature
# [Phase 2/5] Checking resources...
#   → ESP32: Available (NEW)
#   → DHT22: Available (SCRAP)
# [Phase 3/5] Generating design...
#   → 5 components, 8 connections
# [Phase 4/5] Preview...
#   [ASCII schematic displayed]
# [Phase 5/5] Building...
#   ✓ Complete
```

### Preview Only (No Build)

```bash
python scripts/build_project.py "LED blinker" --preview-only
```

### Auto-Build (No Confirmation)

```bash
python scripts/build_project.py "motor controller" --auto-build
```

### Scrap Project Suggestions

```bash
python scripts/build_project.py --suggest-scraps

# Output:
# Found 3 scrap components:
#   ♻ DHT22
#   ♻ LED
#   ♻ ESP8266
#
# Possible projects:
#   1. WiFi Temperature Sensor
#      Difficulty: easy
```

### Show Inventory

```bash
python scripts/build_project.py --inventory

# Output:
# COMPONENT INVENTORY
# NEW:
#   - ESP32 ×2
#   - Arduino Nano ×1
# SCRAP:
#   - DHT22 ×1 (Harvested from broken weather station)
#   - LED ×5 (Harvested from old display)
```

## Component Equivalence Database

The system knows these substitutions:

```python
EQUIVALENTS = {
    "ESP32": {
        "substitutes": ["ESP8266", "Arduino Nano + ESP8266"],
        "capabilities": ["microcontroller", "wifi", "bluetooth"]
    },
    "DHT22": {
        "substitutes": ["DHT11", "BME280"],
        "capabilities": ["temperature", "humidity"]
    },
    "Arduino Nano": {
        "substitutes": ["Arduino Uno", "ATmega328"],
        "capabilities": ["microcontroller"]
    }
}
```

**Extensible**: Add your own substitutions to the database.

## Design Templates

### WiFi Temperature Sensor
```
Components:
  • ESP32 (microcontroller + WiFi)
  • DHT22 (temperature + humidity sensor)
  • Power supply
  • Wires, resistors, PCB

Connections:
  ESP32.3V3 → DHT22.VCC
  ESP32.GND → DHT22.GND
  ESP32.GPIO4 → DHT22.DATA
```

### LED Blinker
```
Components:
  • Arduino Nano
  • LED
  • 330Ω resistor
  • Power supply

Connections:
  Arduino.GPIO2 → Resistor.IN
  Resistor.OUT → LED.ANODE
  LED.CATHODE → Arduino.GND
```

### Motor Controller
```
Components:
  • Microcontroller
  • Motor driver (L298N)
  • DC Motor
  • Power supply

Connections:
  MCU.5V → Driver.VCC
  MCU.GPIO5 → Driver.IN1
  MCU.GPIO6 → Driver.IN2
  Driver.OUT1 → Motor.TERMINAL1
  Driver.OUT2 → Motor.TERMINAL2
```

## Examples

### Example 1: Standard Build
```bash
$ python scripts/build_project.py "build me a WiFi temperature sensor"

[Phase 1/5] Parsing request...
  Request: "build me a WiFi temperature sensor"
  → Project type: sensor
  → Features: wifi, temperature
  → Confidence: 0.90

[Phase 2/5] Checking available resources...
  Available: 5/5
  → ESP32: Available (NEW, $8.00)
  → DHT22: Available (SCRAP, free)

[Phase 3/5] Generating design...
  ✓ Design generated
  → Components: 5
  → Connections: 8
  → Estimated time: 24.5 minutes
  → Using scraps: 1 (saved $3.50)

[Phase 4/5] Design preview...

======================================================================
SCHEMATIC: build me a WiFi temperature sensor
======================================================================

COMPONENTS:
  ● ESP32
  ♻ DHT22
  ● power_supply
  ● resistors
  ● wires

WIRING:
  ESP32.3V3 ──> DHT22.VCC
      (Power supply)
  ESP32.GND ──> DHT22.GND
      (Ground)
  ESP32.GPIO4 ──> DHT22.DATA
      (Signal/data line)

======================================================================

[Phase 5/5] Physical build...
  [1/4] Reserving components...
    ✓ Reserved: ESP32
    ✓ Reserved: DHT22
  [2/4] Preparing workspace...
    ✓ Workspace ready
  [3/4] Placing components...
    [1/5] Placing ESP32...
       → Position: (10.0, 10.0)mm
    [2/5] Placing DHT22...
       → Position: (30.0, 10.0)mm
  [4/4] Creating connections...
    ✓ All connections made

======================================================================
✓ BUILD COMPLETE
======================================================================

Project: build me a WiFi temperature sensor
Components used: 5
Build time: 24.5 minutes
```

### Example 2: Missing Component with Substitution
```bash
$ python scripts/build_project.py "build me a WiFi sensor"

[Phase 2/5] Checking resources...
  ⚠ Missing: ESP32
  ↔ Can substitute:
      ESP32 → Arduino Nano + ESP8266

[Phase 3/5] Generating design...
  → Substitutions: 1
      ESP32 → Arduino Nano + ESP8266

# Build continues with substituted components
```

### Example 3: Scrap Usage
```bash
$ python scripts/build_project.py "build me a temperature sensor"

[Phase 3/5] Generating design...
  → Using scraps: 2
      DHT22 (SCRAP - harvested from weather station)
      LED (SCRAP - harvested from old display)

COST ANALYSIS
  Total cost (new): $5.00
  Savings from scraps: $6.50
  Net cost: $5.00
```

## Demo

Run the interactive demo:

```bash
python scripts/demo_generative_build.py
```

This demonstrates:
- Natural language parsing
- Resource-aware design
- Scrap component usage
- Component substitution
- Cost savings calculation

## Integration with Existing Phases

Phase 7 integrates with:

**Phase 1 (Defect Detection)**:
- Scrap board analysis uses defect detection
- Only harvest components without nearby defects

**Phase 6 (Auto-Configuration)**:
- Robot arm control for physical build
- View optimization for build verification

**3d-splicer**:
- Can generate custom enclosures for designed circuits
- PCB dimensions inform case design

## Extensibility

### Add New Project Templates

```python
# In design_generator.py
DESIGN_TEMPLATES["custom_project"] = {
    "required": ["component1", "component2"],
    "connections": [
        ("component1", "PIN1", "component2", "PIN2"),
    ],
    "code_template": "custom.ino"
}
```

### Add Component Equivalences

```python
# In resource_manager.py
EQUIVALENTS["NewComponent"] = {
    "substitutes": ["Alternative1", "Alternative2"],
    "capabilities": ["capability1", "capability2"]
}
```

### Add New Feature Keywords

```python
# In intent_parser.py
FEATURE_KEYWORDS["new_feature"] = ["keyword1", "keyword2"]
```

## Future Enhancements

Potential additions:
- [ ] LLM-based intent parsing (GPT-4, Claude) for better understanding
- [ ] Visual schematic generation (export to KiCad, Eagle)
- [ ] Code generation for microcontrollers (Arduino sketches)
- [ ] PCB layout optimization (automated routing)
- [ ] Cost optimization (suggest cheaper alternatives)
- [ ] Multi-project builds (build multiple at once)
- [ ] Learning from user feedback (improve templates)

## Testing

Test the individual modules:

```bash
# Test intent parser
python src/intelligence/intent_parser.py

# Test resource manager
python src/intelligence/resource_manager.py

# Test design generator
python src/intelligence/design_generator.py

# Run demo
python scripts/demo_generative_build.py
```

## Summary

Phase 7 completes the vision of Dum-E as a **truly intelligent robotic assistant**:

**Before Phase 7**: "Here's a PCB, analyze it"
**After Phase 7**: "Build me a WiFi sensor" → Robot builds it

The system now:
1. **Understands natural language** ("build me X")
2. **Thinks about resources** (what do we have?)
3. **Substitutes intelligently** (no ESP32? use Arduino + WiFi)
4. **Reuses scraps** (save money, reduce waste)
5. **Generates complete designs** (BOM, wiring, layout)
6. **Builds physically** (robot arm assembly)

All from just words. No manual CAD. No manual wiring diagrams. Just:
```bash
python scripts/build_project.py "build me a WiFi temperature sensor"
```

**That's the power of Phase 7.**

---

*Completed: 2025-12-28*
*Dum-E v3.0 - Generative Build Capability*
