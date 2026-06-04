# Circuit-AI: Modular Architecture

## Core Philosophy

Circuit-AI is NOT a linear pipeline. It's a **collection of independent modules** that can be used:
- Standalone (just one module)
- Combined (multiple modules)
- In any order (flexible workflow)
- For different purposes (prototype, repair, modify, scale)

---

## The 8 Core Modules

### 1. Intent Parser
**Purpose**: Natural language → Structured requirements

**Input**: Plain English description
```python
"WiFi temperature sensor for outdoor use, battery powered"
```

**Output**: Structured intent
```python
{
    'project_type': 'sensor',
    'features': ['wifi', 'temperature', 'battery_powered', 'outdoor'],
    'constraints': ['weatherproof', 'low_power'],
    'confidence': 0.90
}
```

**Use Cases**:
- Starting new project from description
- Understanding user requirements
- Extracting features from vague ideas

**Can be used alone**: YES
```python
# Just parse intent, don't generate design
parser = create_parser()
intent = parser.parse("robot arm with 6 servos")
# Now you know what features are needed
```

---

### 2. Component Selector
**Purpose**: Intelligent component comparison and selection

**Input**: Component category + requirements
```python
{
    'category': 'wifi_microcontroller',
    'requirements': {
        'bluetooth': True,
        'dual_core': True
    },
    'quantity': 1
}
```

**Output**: Recommended component with reasoning
```python
{
    'selected': 'ESP32 DevKit Module',
    'cost': 8.00,
    'reasoning': 'Dual-core needed for servo control, Bluetooth for remote',
    'alternatives': [
        {'name': 'ESP8266', 'cost': 4.00, 'when_to_use': 'If no Bluetooth needed'},
        {'name': 'ESP32-C6', 'cost': 8.10, 'when_to_use': 'If want WiFi 6'}
    ]
}
```

**Use Cases**:
- "Should I use ESP8266 or ESP32?"
- Component comparison without full design
- Learning about tradeoffs
- Optimizing existing design

**Can be used alone**: YES
```python
# Just compare components, don't generate full design
selector = SmartDesignGenerator()
choice = selector.select_component(
    'wifi_microcontroller',
    requirements={'battery_powered': True}
)
print(f"Use {choice.selected}: {choice.reasoning}")
```

---

### 3. Vision System
**Purpose**: Reverse-engineer circuits from photos

**Input**: Image of circuit board
```
photo.jpg (picture of PCB or breadboard)
```

**Output**: Identified components and connections
```python
{
    'components': [
        {'type': 'ESP32', 'location': (x, y), 'confidence': 0.95},
        {'type': 'DHT22', 'location': (x, y), 'confidence': 0.88},
        {'type': 'Resistor', 'value': '10k', 'location': (x, y)}
    ],
    'connections': [
        {'from': 'ESP32.GPIO4', 'to': 'DHT22.DATA'},
        {'from': 'ESP32.3V3', 'to': 'DHT22.VCC'}
    ]
}
```

**Use Cases**:
- "What is this circuit?"
- Reverse-engineer existing design
- Identify unknown components
- Repair broken device (identify burned component)
- Learn from others' builds

**Can be used alone**: YES
```python
# Just identify components, don't generate new design
from vision.circuit_analyzer import analyze_circuit
components = analyze_circuit('photo.jpg')
print(f"Found: {components}")
```

---

### 4. Design Generator
**Purpose**: Create complete circuit design

**Input**: Intent + component choices
```python
{
    'intent': {intent from parser},
    'components': {selected components},
    'constraints': {'cost': 'minimize', 'difficulty': 'beginner'}
}
```

**Output**: Complete buildable design
```python
{
    'bom': [list of components with costs],
    'wiring': [connection diagram],
    'assembly': [step-by-step instructions],
    'code': 'Arduino sketch',
    'total_cost': 11.00,
    'estimated_build_time': '30 minutes'
}
```

**Use Cases**:
- Generate complete design from scratch
- Convert requirements to buildable project
- Create documentation

**Can be used alone**: NO (needs components selected first)

---

### 5. 3D Splicer (Case Generator)
**Purpose**: Generate 3D printable enclosures

**Input**: Component dimensions + mounting requirements
```python
{
    'components': [
        {'name': 'ESP32', 'dimensions': (25, 50, 3)},
        {'name': 'DHT22', 'dimensions': (15, 40, 6)}
    ],
    'enclosure_type': 'weatherproof',
    'mounting': 'wall_mount'
}
```

**Output**: 3D model file
```python
{
    'stl_file': 'enclosure.stl',
    'dimensions': (80, 60, 40),
    'features': ['snap_fit_lid', 'cable_gland', 'mounting_holes'],
    'print_time': '3 hours',
    'material': 'PETG'
}
```

**Use Cases**:
- "I need a case for my circuit"
- Weatherproof outdoor projects
- Professional-looking builds
- Custom mounting solutions

**Can be used alone**: YES
```python
# Just generate case, I already designed circuit
from splicer.case_generator import generate_case
case = generate_case(components, enclosure_type='weatherproof')
```

---

### 6. Resource Manager
**Purpose**: Inventory management + cost optimization

**Input**: Component list + available inventory
```python
{
    'needed': ['ESP32', 'DHT22', 'resistors'],
    'have': {
        'ESP8266': 2,
        'resistors': 50
    },
    'quantity': 10  # building 10 units
}
```

**Output**: Shopping list + cost analysis
```python
{
    'can_use_from_stock': ['resistors'],
    'need_to_buy': ['ESP32 x10', 'DHT22 x10'],
    'shopping_list': [
        {'item': 'ESP32', 'qty': 10, 'unit_cost': 8.00, 'total': 80.00, 'vendor': 'Amazon'}
    ],
    'total_cost': 115.00,
    'cost_per_unit': 11.50,
    'savings_vs_retail': 15.00
}
```

**Use Cases**:
- "What parts do I need to order?"
- Manage makerspace inventory
- Bulk ordering for class/workshop
- Cost optimization for production

**Can be used alone**: YES
```python
# Just check what I need to buy
from intelligence.resource_manager import ResourceManager
rm = ResourceManager('my_inventory.json')
shopping = rm.generate_shopping_list(needed_components)
```

---

### 7. Modification Planner
**Purpose**: Modify existing designs

**Input**: Current design + desired changes
```python
{
    'current_design': {existing BOM and wiring},
    'changes': [
        'add Bluetooth',
        'switch to battery power',
        'add motion sensor'
    ]
}
```

**Output**: Modified design + migration guide
```python
{
    'component_changes': [
        {'remove': 'ESP8266', 'add': 'ESP32', 'reason': 'Need Bluetooth'},
        {'add': 'PIR sensor', 'reason': 'Motion detection'},
        {'add': 'Battery pack', 'reason': 'Portable power'}
    ],
    'wiring_changes': [
        {'change': 'Connect ESP32 GPIO5 to PIR output'},
        {'change': 'Remove 5V wall adapter, add battery'}
    ],
    'code_changes': 'Added Bluetooth and PIR libraries',
    'cost_difference': +5.00
}
```

**Use Cases**:
- "I want to add feature X to my existing project"
- Upgrade designs with new components
- Fix design issues
- Version control for hardware

**Can be used alone**: YES
```python
# Just plan modifications, don't rebuild from scratch
from intelligence.modification_planner import plan_modifications
changes = plan_modifications(current_design, add_features=['bluetooth'])
```

---

### 8. Repair Guidance
**Purpose**: Fix broken circuits

**Input**: Problem description + circuit info
```python
{
    'problem': 'Device stopped working, smell of burning',
    'circuit': {components and connections},
    'symptoms': ['no LED', 'hot regulator']
}
```

**Output**: Diagnosis + repair steps
```python
{
    'likely_cause': 'Voltage regulator failure',
    'damaged_components': ['LM7805'],
    'replacement_parts': [
        {'part': 'LM7805', 'cost': 0.15, 'where': 'Amazon'}
    ],
    'repair_steps': [
        '1. Desolder old regulator',
        '2. Check for shorted capacitors',
        '3. Install new regulator',
        '4. Test with multimeter before powering'
    ],
    'prevention': 'Add fuse to prevent overcurrent'
}
```

**Use Cases**:
- "My circuit stopped working"
- Identify failed components
- Learn troubleshooting
- Repair instead of rebuild

**Can be used alone**: YES
```python
# Just get repair guidance
from intelligence.repair_guidance import diagnose
fix = diagnose(symptoms=['no power', 'hot chip'])
```

---

## Flexible Combinations

### Example 1: Quick Component Question
```python
# User: "Should I use ESP8266 or ESP32 for battery project?"

# Use ONLY Component Selector module
selector = SmartDesignGenerator()
choice = selector.select_component(
    'wifi_microcontroller',
    requirements={'battery_powered': True}
)

# Output: "ESP8266 - uses 50% less power, battery lasts 3x longer"
```

### Example 2: Reverse Engineer + Modify
```python
# User uploads photo of circuit: "What is this? Can I add WiFi?"

# Step 1: Vision module
components = analyze_circuit('photo.jpg')

# Step 2: Modification Planner module
changes = plan_modifications(
    current=components,
    add_features=['wifi']
)

# Output: "This is a temperature logger. To add WiFi, replace Arduino
#          with ESP8266, add these connections..."
```

### Example 3: Scale Optimization
```python
# User: "I want to manufacture 1000 units of my design"

# Use Resource Manager module
rm = ResourceManager()
scaled = rm.optimize_for_scale(
    current_bom=my_design,
    quantity=1000
)

# Output: "At 1000 units:
#          - Switch from modules to raw ICs (save $3000)
#          - Order from Digikey bulk (save $1200)
#          - Consider custom PCB (save assembly time)
#          Total savings: $5400"
```

### Example 4: Full Pipeline
```python
# User: "WiFi sensor"

# All modules in sequence
intent = intent_parser.parse("WiFi sensor")
components = component_selector.select_all(intent)
design = design_generator.generate(intent, components)
case = splicer.generate_case(design.components)
bom = resource_manager.create_shopping_list(design.bom)

# Output: Complete project package
```

---

## Module Independence

Each module can be:

### 1. Used Alone
```python
# Just need component comparison? Use only that module.
choice = selector.select_component('wifi_mcu', {...})
```

### 2. Combined Differently
```python
# Reverse engineer, then scale
components = vision.analyze(photo)
scaled = resource_manager.scale(components, qty=100)
```

### 3. Skipped If Not Needed
```python
# I already know what components I want, just need case
case = splicer.generate(my_components)
# Skip: intent parser, component selector
```

### 4. Extended
```python
# Add your own modules
from my_module import PCBLayoutGenerator
pcb = PCBLayoutGenerator(design)
# Works with Circuit-AI modules
```

---

## API-First Design

Each module exposes clean API:

```python
# Intent Parser
from intelligence.llm_intent_parser import create_parser
parser = create_parser()
intent = parser.parse(text)

# Component Selector
from intelligence.smart_design_generator import SmartDesignGenerator
selector = SmartDesignGenerator()
choice = selector.select_component(type, requirements, quantity)

# Vision
from vision.circuit_analyzer import analyze_circuit
components = analyze_circuit(image_path)

# 3D Splicer
from splicer.case_generator import generate_case
case = generate_case(components, options)

# Resource Manager
from intelligence.resource_manager import ResourceManager
rm = ResourceManager(inventory_file)
shopping = rm.generate_shopping_list(components)
```

All modules are **independent Python modules** - no tight coupling!

---

## Web Interface Should Reflect This

Instead of one linear workflow, the interface should offer:

### Home Page - Choose Your Path:
```
┌─────────────────────────────────────────────────┐
│  What do you want to do?                        │
│                                                 │
│  [Start New Design]                             │
│     Natural language → Complete design          │
│                                                 │
│  [Compare Components]                           │
│     Should I use ESP8266 or ESP32?              │
│                                                 │
│  [Reverse Engineer]                             │
│     Upload photo → Identify circuit             │
│                                                 │
│  [Modify Existing]                              │
│     I have a design, want to add features       │
│                                                 │
│  [Repair Circuit]                               │
│     My circuit broke, help me fix it            │
│                                                 │
│  [Optimize for Scale]                           │
│     Going from 1 to 1000 units                  │
│                                                 │
│  [Generate Case Only]                           │
│     I need an enclosure for my circuit          │
└─────────────────────────────────────────────────┘
```

Each path uses different module combinations!

---

## The Power of Modularity

### ✅ Use What You Need
- Don't need full design? Just use component selector
- Already have circuit? Just generate case
- Need to repair? Just use vision + repair guidance

### ✅ Combine Flexibly
- Vision + Modification: "What is this? How do I add WiFi?"
- Component Selector + Resource Manager: "What to buy for 100 units?"
- Intent Parser + Vision: "I saw this project, make me something similar"

### ✅ Extend Easily
- Add PCB layout generator module
- Add code generator module
- Add simulation module
- All work with existing modules

### ✅ API-Based
- Build web interface using modules
- Build CLI using same modules
- Build mobile app using same modules
- Build desktop app using same modules

---

## Bottom Line

Circuit-AI is NOT:
❌ Linear pipeline (describe → generate → build)
❌ All-or-nothing system
❌ One-size-fits-all workflow

Circuit-AI IS:
✅ Modular toolkit
✅ Mix-and-match capabilities
✅ Flexible workflows
✅ Independent modules that work together

**Use the modules YOU need, in the order YOU need them.**

That's the power of the modular architecture!
