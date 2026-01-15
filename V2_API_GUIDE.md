# Circuit-AI v2 API Guide

**Version:** 0.4.0
**Status:** Production Ready
**Integration:** Complete (Educational + Professional)

---

## What's New in v2

The v2 API represents a **complete platform integration** that bridges educational tools with professional PCB validation:

```
┌──────────────────────────────────────────────────────────┐
│                    V2 UNIFIED WORKFLOWS                  │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  Educational Layer (My Work)                             │
│  • Recipe Optimizer (29 projects)                        │
│  • Learning Paths (106 hours)                            │
│  • Build Instructions (step-by-step)                     │
│  • Pricing Service (DigiKey + eBay)                      │
│                     ↓                                    │
│              UNIFIED ENGINE                              │
│                     ↓                                    │
│  Professional Layer (ChatGPT's Work)                     │
│  • KiCAD Integration                                     │
│  • DC Circuit Solver (MNA)                               │
│  • Power Tree Validator                                  │
│  • Quantitative Fixes                                    │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

### Key Advantages

1. **Complete User Journeys**: From "I want to learn Arduino" to "Here's your validated PCB design"
2. **Skill-Based Routing**: Different workflows for BEGINNER → PROFESSIONAL
3. **End-to-End Integration**: Recipe → Instructions → Validation → Manufacturing
4. **Quantitative Validation**: "Widen trace to 2mm" not "traces too thin"

---

## V2 API Endpoints

## Authentication (v2)

If API keys are enabled (see `.env.example`), send one of:

```http
Authorization: Bearer YOUR_API_KEY
```

or:

```http
X-API-Key: YOUR_API_KEY
```

### 1. POST `/api/v2/workflow/beginner`

**Complete beginner workflow with learning path recommendations and project selection.**

**Request Body:**
```json
{
  "skill_level": 1,                           // 1-5 (BEGINNER-PROFESSIONAL)
  "completed_projects": ["LED Blink"],        // optional
  "inventory": [                              // optional
    {"id": "arduino_uno", "condition": "used", "quantity": 1},
    {"id": "bme280", "condition": "new", "quantity": 1}
  ],
  "budget": 50.0,                             // optional (default: 50)
  "goal": "learning"                          // "learning", "roi", or "speed"
}
```

**Response:**
```json
{
  "status": "success",
  "project": {
    "name": "Air Quality Monitor",
    "category": "iot",
    "description": "WiFi-enabled air quality monitor with BME280 sensor",
    "difficulty": "medium",
    "build_time_hours": 2.5,
    "economics": {
      "parts_cost": 22.0,
      "market_price_low": 30.0,
      "market_price_high": 45.0,
      "roi_percent": 59.1,
      "missing_parts_cost": 8.0
    },
    "inventory": {
      "match_percent": 85.0,
      "components_owned": ["esp32", "bme280"],
      "components_needed": ["oled_ssd1306"]
    }
  },
  "instructions": {
    "title": "Air Quality Monitor Build Guide",
    "steps": [...],
    "wiring_diagram": "...",
    "code_url": "..."
  },
  "next_steps": [
    "Build Air Quality Monitor",
    "Follow 9 step instructions",
    "Upload your design for validation (optional)",
    "Estimated time: 2.5 hours"
  ],
  "estimated_cost": 8.0,
  "estimated_time_hours": 2.5
}
```

**Example Use Cases:**
- Complete beginner asks "What can I build?"
- Hobbyist with spare parts wants project recommendations
- Student following learning curriculum

---

### 2. POST `/api/v2/workflow/complete`

**End-to-end workflow from recipe selection to validated design.**

**Request Body:**
```json
{
  "user": {
    "skill_level": 2,                       // 1-5 (BEGINNER-PROFESSIONAL)
    "completed_projects": ["LED Blink"],
    "inventory": [
      {"id": "esp32", "condition": "new", "quantity": 1},
      {"id": "bme280", "condition": "used", "quantity": 1}
    ],
    "budget": 20.0,
    "goal": "learning"
  },
  "project_name": "Air Quality Monitor",
  "kicad_file": "/path/to/design.net"      // optional - for validation
}
```

**Response (without KiCAD file):**
```json
{
  "status": "success",
  "project": {
    "name": "Air Quality Monitor",
    "category": "iot",
    "difficulty": "medium",
    "build_time_hours": 2.5,
    "economics": {
      "parts_cost": 22.0,
      "roi_percent": 59.1,
      "missing_parts_cost": 8.0
    }
  },
  "instructions": {
    "title": "Air Quality Monitor Build Guide",
    "steps": [...]
  },
  "next_steps": [
    "Build Air Quality Monitor",
    "Estimated time: 2.5 hours",
    "Cost: $8.00",
    "Upload KiCAD design for validation (optional)"
  ],
  "estimated_cost": 8.0,
  "estimated_time_hours": 2.5
}
```

**Response (with KiCAD file - validation included):**
```json
{
  "status": "validation_warning",
  "project": {...},
  "instructions": {...},
  "validation": {
    "issues_count": 2,
    "issues": [
      {
        "severity": "warning",
        "component": "Trace +3V3",
        "issue": "Excessive voltage drop (0.35V exceeds 0.25V limit)",
        "solution": "Widen trace from 0.5mm to 2.0mm or use copper pour"
      },
      {
        "severity": "warning",
        "component": "LDO U1",
        "issue": "Marginal dropout voltage (0.32V, min 0.3V)",
        "solution": "Consider increasing VBUS to 5.5V or using lower-dropout LDO"
      }
    ]
  },
  "manufacturing": null,
  "next_steps": [
    "Fix trace width issues",
    "Re-upload for final validation",
    "Then generate manufacturing files"
  ],
  "estimated_cost": 8.0,
  "estimated_time_hours": 2.5
}
```

**Example Use Cases:**
- User wants complete workflow from "what to build" to "validated PCB"
- Professional wants to validate existing design
- Student submitting project for grading

---

### 3. POST `/api/v2/workflow/validate-kicad`

**Professional KiCAD PCB validation with quantitative fixes.**

**Request (JSON):**
```json
{
  "kicad_file": "/path/to/design.net",
  "hints": {
    "sources": [
      {"name": "VUSB", "net": "VBUS", "volts": 5.0, "max_current_a": 0.5}
    ],
    "loads_cc": [
      {"name": "ESP32", "net": "+3V3", "amps": 0.24}
    ],
    "voltage_constraints": [
      {"net": "+3V3", "min_v": 3.0, "max_v": 3.6}
    ]
  }
}
```

**Request (File Upload):**
```bash
curl -X POST http://localhost:5000/api/v2/workflow/validate-kicad \
  -F "kicad_file=@my_design.net" \
  -F 'hints={"sources":[{"name":"VUSB","net":"VBUS","volts":5.0,"max_current_a":0.5}]}'
```

**Response:**
```json
{
  "status": "validation_warning",
  "validation": {
    "issues_count": 2,
    "critical": 0,
    "errors": 0,
    "warnings": 2,
    "issues": [
      {
        "severity": "warning",
        "component": "Trace +3V3",
        "issue": "Excessive voltage drop",
        "physics": {
          "current_a": 1.2,
          "voltage_drop": 0.35,
          "power_loss": 0.42,
          "current_width_mm": 0.5,
          "required_width_mm": 2.0
        },
        "solution": "Widen trace from 0.5mm to 2.0mm or use copper pour"
      },
      {
        "severity": "warning",
        "component": "LDO U1 (AMS1117-3.3)",
        "issue": "Marginal dropout voltage",
        "physics": {
          "vin": 3.62,
          "vout": 3.3,
          "dropout": 0.32,
          "min_dropout": 0.3
        },
        "solution": "Increase input voltage to 3.9V or use lower-dropout LDO"
      }
    ]
  },
  "manufacturing_ready": false,
  "next_steps": [
    "Fix trace width on +3V3 rail",
    "Consider LDO dropout margin",
    "Re-upload for final validation",
    "Generate manufacturing files"
  ]
}
```

**Example Use Cases:**
- Professional EE validating PCB before manufacturing
- Hobbyist wants to check custom design
- Teacher grading student PCB submissions

---

## User Skill Levels

The v2 API uses skill-based routing to provide appropriate workflows:

```python
class UserLevel(Enum):
    BEGINNER = 1      # Never built anything
    HOBBYIST = 2      # Built a few projects
    INTERMEDIATE = 3  # Comfortable with circuits
    ADVANCED = 4      # Designs PCBs
    PROFESSIONAL = 5  # EE degree / commercial work
```

### How Skill Levels Affect Workflows

| Skill Level | Beginner Workflow | Complete Workflow | KiCAD Validation |
|-------------|-------------------|-------------------|------------------|
| **BEGINNER (1)** | Learning path recommendations | Prerequisites check → learning path | N/A |
| **HOBBYIST (2)** | Buildable projects from inventory | Recipe → instructions | Basic validation |
| **INTERMEDIATE (3)** | Advanced projects | Recipe → instructions → validation | Full validation |
| **ADVANCED (4)** | Complex projects | Recipe → design → validation | Full validation + trace analysis |
| **PROFESSIONAL (5)** | All projects | Design → validation → manufacturing | Full validation + quantitative fixes |

---

## Complete User Journeys

### Journey 1: Complete Beginner

**Goal:** Learn Arduino basics

```bash
# Step 1: Ask for beginner workflow
curl -X POST http://localhost:5000/api/v2/workflow/beginner \
  -H "Content-Type: application/json" \
  -d '{
    "skill_level": 1,
    "goal": "learning"
  }'

# Response: Learning path recommendation
{
  "status": "prerequisites_missing",
  "next_steps": [
    "Start learning path: Arduino Basics",
    "First module: Module 1: Hello Arduino",
    "First project: LED Blink Trainer",
    "Complete this module to unlock more projects"
  ],
  "estimated_time_hours": 3.5
}

# Step 2: After completing first module, ask again with updated profile
curl -X POST http://localhost:5000/api/v2/workflow/beginner \
  -H "Content-Type: application/json" \
  -d '{
    "skill_level": 1,
    "completed_projects": ["LED Blink Trainer"],
    "inventory": [
      {"id": "arduino_uno", "condition": "new", "quantity": 1}
    ],
    "goal": "learning"
  }'

# Response: Next project recommendation
{
  "status": "success",
  "project": {
    "name": "Button Counter",
    "difficulty": "easy",
    ...
  },
  "instructions": {...}
}
```

---

### Journey 2: Hobbyist with Parts

**Goal:** Build something useful with spare parts

```bash
# Step 1: Get project recommendations
curl -X POST http://localhost:5000/api/v2/workflow/beginner \
  -H "Content-Type: application/json" \
  -d '{
    "skill_level": 2,
    "completed_projects": ["LED Blink", "Button Counter"],
    "inventory": [
      {"id": "esp32", "condition": "used", "quantity": 1},
      {"id": "bme280", "condition": "new", "quantity": 1},
      {"id": "oled_ssd1306", "condition": "new", "quantity": 1}
    ],
    "budget": 20.0,
    "goal": "learning"
  }'

# Response: Perfect match found
{
  "status": "success",
  "project": {
    "name": "Air Quality Monitor",
    "inventory": {
      "match_percent": 100.0,
      "components_owned": ["esp32", "bme280", "oled_ssd1306"],
      "components_needed": []
    },
    "economics": {
      "missing_parts_cost": 0.0,
      "roi_percent": 59.1
    }
  },
  "instructions": {
    "steps": [...]
  }
}

# Step 2: Build the project, then validate PCB design
curl -X POST http://localhost:5000/api/v2/workflow/validate-kicad \
  -F "kicad_file=@air_quality_monitor.net"

# Response: Validation results with fixes
```

---

### Journey 3: Professional Engineer

**Goal:** Validate PCB before manufacturing

```bash
# Direct KiCAD validation
curl -X POST http://localhost:5000/api/v2/workflow/validate-kicad \
  -F "kicad_file=@production_board_v2.net" \
  -F 'hints={"sources":[...],"loads_cc":[...]}'

# Response: Professional validation with quantitative fixes
{
  "status": "validation_warning",
  "validation": {
    "issues": [
      {
        "severity": "warning",
        "component": "Trace +12V",
        "physics": {
          "current_a": 2.5,
          "voltage_drop": 0.8,
          "current_width_mm": 1.0,
          "required_width_mm": 4.5
        },
        "solution": "Widen trace to 4.5mm or use 2oz copper"
      }
    ]
  }
}
```

---

## Integration Examples

### Python Client

```python
import requests

API_BASE = "http://localhost:5000/api/v2"

# Example 1: Beginner workflow
def get_beginner_recommendation(inventory, skill_level=1):
    response = requests.post(
        f"{API_BASE}/workflow/beginner",
        json={
            "skill_level": skill_level,
            "inventory": inventory,
            "budget": 50.0,
            "goal": "learning"
        }
    )
    return response.json()

# Example 2: Complete workflow
def get_complete_workflow(user, project_name, kicad_file=None):
    response = requests.post(
        f"{API_BASE}/workflow/complete",
        json={
            "user": user,
            "project_name": project_name,
            "kicad_file": kicad_file
        }
    )
    return response.json()

# Example 3: KiCAD validation
def validate_kicad(kicad_file_path, hints=None):
    with open(kicad_file_path, 'rb') as f:
        files = {'kicad_file': f}
        data = {'hints': hints} if hints else {}
        response = requests.post(
            f"{API_BASE}/workflow/validate-kicad",
            files=files,
            data=data
        )
    return response.json()

# Usage
inventory = [
    {"id": "esp32", "condition": "new", "quantity": 1},
    {"id": "bme280", "condition": "used", "quantity": 1}
]

result = get_beginner_recommendation(inventory, skill_level=2)
print(f"Recommended project: {result['project']['name']}")
print(f"Cost to complete: ${result['estimated_cost']}")
```

---

## Comparison: V1 vs V2

| Feature | V1 API | V2 API |
|---------|--------|--------|
| **Scope** | Individual features | Complete workflows |
| **User Types** | Generic | Skill-based (1-5) |
| **Output** | JSON responses | End-to-end journeys |
| **Education** | Recipes + Paths separately | Integrated (learn → build) |
| **Validation** | Basic circuit checks | Professional KiCAD + physics |
| **Fixes** | Generic suggestions | Quantitative ("widen to 2mm") |
| **Workflows** | Manual chaining | Automatic orchestration |
| **Manufacturing** | Not integrated | Ready for manufacturing files |

---

## Best Practices

### 1. Choose the Right Endpoint

- **Beginner workflow**: Use for education, learning paths, project discovery
- **Complete workflow**: Use for end-to-end projects (recipe → validation)
- **KiCAD validation**: Use for professional PCB validation only

### 2. Provide Accurate Skill Levels

Skill levels affect workflow routing:
- Don't overestimate (leads to frustration)
- Don't underestimate (limits opportunities)

### 3. Use KiCAD Hints When Possible

Hints improve validation accuracy:
```json
{
  "sources": [{"name": "VUSB", "net": "VBUS", "volts": 5.0, "max_current_a": 0.5}],
  "loads_cc": [{"name": "ESP32", "net": "+3V3", "amps": 0.24}],
  "voltage_constraints": [{"net": "+3V3", "min_v": 3.0, "max_v": 3.6}]
}
```

Without hints, the system will auto-generate them, but manual hints are more accurate.

### 4. Handle All Status Types

Possible status values:
- `success`: Everything ready
- `prerequisites_missing`: User needs to complete learning path
- `no_projects`: No buildable projects with current inventory
- `validation_passed`: Design is good
- `validation_warning`: Design works but has minor issues
- `validation_failed`: Design has critical issues
- `project_not_found`: Requested project doesn't exist

---

## Error Handling

### Common Errors

**400 Bad Request:**
```json
{"error": "Request body required"}
{"error": "user and project_name fields required"}
{"error": "kicad_file required"}
```

**404 Not Found:**
```json
{"error": "Project 'XYZ' not found"}
{"error": "Instructions not found for project: XYZ"}
```

**500 Internal Server Error:**
```json
{"error": "Error processing KiCAD file: Invalid netlist format"}
```

---

## Performance Considerations

- **Beginner workflow**: ~100-200ms (recipe generation + instructions)
- **Complete workflow**: ~200-500ms (without KiCAD), ~1-2s (with KiCAD validation)
- **KiCAD validation**: ~500ms-1.5s (depending on circuit complexity)

---

## What's Next

### Planned v2.1 Features

1. **Manufacturing Integration**:
   - Gerber file generation
   - BOM generation with supplier links
   - One-click JLCPCB ordering

2. **Enhanced Validation**:
   - AC analysis
   - Thermal analysis
   - EMI/EMC checks

3. **Progress Tracking**:
   - User progress API
   - Achievement system
   - Project portfolio

---

## Support

- **API Documentation**: `GET /` (root endpoint)
- **Health Check**: `GET /api/health`
- **GitHub Issues**: [Circuit-AI Issues](https://github.com/user/circuit-ai/issues)

---

**Built by integrating educational tools (recipe optimizer, learning paths) with professional validation (KiCAD, MNA solver, power tree analysis).**

**The result: A complete electronics platform from beginner to professional.**
