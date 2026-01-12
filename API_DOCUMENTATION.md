# Circuit-AI API Documentation
## For Frontend Integration

**Base URL:** `https://circuit-ai.railway.app` (when deployed)
**Local:** `http://localhost:5000`

**API Version:** v2 (Unified Workflow API)
**Backend:** Flask (Python)

---

## Authentication

Currently no authentication required for testing. Will add API key authentication later.

**Future format:**
```http
Authorization: Bearer YOUR_API_KEY
```

---

## Core Endpoints

### 1. Health Check

**Endpoint:** `GET /api/health`

**Purpose:** Check if API is running

**Request:**
```bash
curl http://localhost:5000/api/health
```

**Response:**
```json
{
  "status": "healthy",
  "version": "0.4.0",
  "timestamp": "2026-01-12T10:30:00Z"
}
```

---

### 2. List Components

**Endpoint:** `GET /api/components`

**Purpose:** Get list of all supported components

**Response:**
```json
{
  "components": [
    {
      "id": "esp32",
      "name": "ESP32 Dev Board",
      "category": "microcontroller",
      "pins": ["VCC", "GND", "GPIO0", "GPIO2", ...],
      "voltage_range": [3.0, 3.6],
      "current_typical_ma": 80
    },
    {
      "id": "arduino_nano",
      "name": "Arduino Nano",
      "category": "microcontroller",
      "pins": ["D0", "D1", "D2", ..., "A0", "A1", ...],
      "voltage_range": [7, 12],
      "current_max_ma": 500
    },
    {
      "id": "led",
      "name": "LED",
      "category": "passive",
      "forward_voltage_v": 2.0,
      "max_current_ma": 20
    }
  ],
  "total_count": 29
}
```

---

### 3. Validate KiCAD File

**Endpoint:** `POST /api/v2/workflow/validate-kicad`

**Purpose:** Upload KiCAD netlist and get validation results

**Request:**
```bash
curl -X POST http://localhost:5000/api/v2/workflow/validate-kicad \
  -F "kicad_file=@my_board.kicad_pcb"
```

**Request (multipart/form-data):**
- `kicad_file`: File upload (`.kicad_pcb` or `.net` format)

**Response:**
```json
{
  "success": true,
  "validation": {
    "circuit_valid": false,
    "issues_found": 2,
    "issues": [
      {
        "severity": "critical",
        "type": "trace_width",
        "component_id": "T1",
        "message": "Trace T1 is too thin for current load",
        "details": {
          "current_width_mm": 0.5,
          "current_a": 2.0,
          "voltage_drop_v": 0.45,
          "required_width_mm": 1.2,
          "standard": "IPC-2152"
        },
        "fix": {
          "action": "widen_trace",
          "parameters": {
            "new_width_mm": 1.2
          },
          "reasoning": "IPC-2152 standard for 2A at 10°C rise, 1oz copper, external layer"
        },
        "location": {
          "from": {"x": 10.5, "y": 20.3},
          "to": {"x": 25.8, "y": 20.3}
        }
      },
      {
        "severity": "warning",
        "type": "component_rating",
        "component_id": "R1",
        "message": "Resistor R1 exceeds power rating",
        "details": {
          "component": "R1",
          "value": "150Ω",
          "current_rating": "1/4W",
          "actual_power_w": 0.31,
          "rated_power_w": 0.25,
          "utilization_pct": 124
        },
        "fix": {
          "action": "replace_component",
          "parameters": {
            "new_rating": "1/2W"
          },
          "reasoning": "Power dissipation exceeds rating by 24%"
        },
        "location": {
          "x": 15.2,
          "y": 30.5,
          "rotation": 0
        }
      }
    ],
    "components": [
      {
        "id": "U1",
        "type": "arduino_nano",
        "position": {"x": 50.0, "y": 50.0, "rotation": 0},
        "nets": {
          "VCC": "net_vcc",
          "GND": "net_gnd",
          "D13": "net_led"
        }
      },
      {
        "id": "R1",
        "type": "resistor",
        "value": "150Ω",
        "rating": "1/4W",
        "position": {"x": 15.2, "y": 30.5, "rotation": 0},
        "nets": {
          "1": "net_vcc",
          "2": "net_led"
        }
      },
      {
        "id": "LED1",
        "type": "led",
        "color": "red",
        "position": {"x": 20.0, "y": 35.0, "rotation": 90},
        "nets": {
          "anode": "net_led",
          "cathode": "net_gnd"
        }
      }
    ],
    "traces": [
      {
        "id": "T1",
        "net": "net_vcc",
        "from_component": "U1",
        "to_component": "R1",
        "width_mm": 0.5,
        "length_mm": 25.3,
        "layer": "F.Cu",
        "current_a": 2.0,
        "voltage_drop_v": 0.45,
        "path": [
          {"x": 10.5, "y": 20.3},
          {"x": 15.0, "y": 20.3},
          {"x": 25.8, "y": 20.3}
        ]
      }
    ],
    "nets": [
      {
        "id": "net_vcc",
        "name": "VCC",
        "voltage_v": 5.0,
        "components": ["U1", "R1"],
        "traces": ["T1"]
      },
      {
        "id": "net_gnd",
        "name": "GND",
        "voltage_v": 0.0,
        "components": ["U1", "LED1"]
      }
    ],
    "dc_analysis": {
      "converged": true,
      "iterations": 5,
      "node_voltages": {
        "net_vcc": 5.0,
        "net_led": 4.55,
        "net_gnd": 0.0
      },
      "branch_currents": {
        "R1": 0.020
      }
    },
    "power_tree": {
      "valid": false,
      "total_current_a": 2.1,
      "issues": ["Trace T1 voltage drop exceeds 0.1V threshold"]
    }
  },
  "board_info": {
    "width_mm": 100.0,
    "height_mm": 80.0,
    "layers": ["F.Cu", "B.Cu"],
    "thickness_mm": 1.6
  }
}
```

---

### 4. Validate Circuit Design (JSON)

**Endpoint:** `POST /api/validate`

**Purpose:** Validate circuit from component list (no file upload)

**Request:**
```bash
curl -X POST http://localhost:5000/api/validate \
  -H "Content-Type: application/json" \
  -d '{
    "components": [
      {
        "type": "arduino_nano",
        "pins": {
          "D13": "led_anode",
          "GND": "gnd"
        }
      },
      {
        "type": "LED",
        "color": "red",
        "pins": {
          "anode": "led_anode",
          "cathode": "resistor_out"
        }
      },
      {
        "type": "resistor",
        "value": 150,
        "pins": {
          "1": "resistor_out",
          "2": "gnd"
        }
      }
    ],
    "power_source": {
      "voltage": 5.0,
      "pin": "D13"
    }
  }'
```

**Response:**
```json
{
  "valid": true,
  "components_validated": 3,
  "warnings": [],
  "suggestions": [
    "Circuit is correctly wired for LED control",
    "Resistor value (150Ω) is appropriate for 5V with red LED",
    "Expected current: ~17mA"
  ],
  "calculations": {
    "led_current_ma": 17.3,
    "resistor_power_w": 0.045,
    "voltage_across_led_v": 2.0,
    "voltage_across_resistor_v": 3.0
  }
}
```

---

### 5. Generate BOM (Bill of Materials)

**Endpoint:** `POST /api/v2/manufacture/bom`

**Purpose:** Generate component list with pricing

**Request:**
```bash
curl -X POST http://localhost:5000/api/v2/manufacture/bom \
  -F "netlist_file=@my_board.net" \
  -F "include_pricing=true" \
  -F "format=json"
```

**Response:**
```json
{
  "success": true,
  "bom": {
    "components": [
      {
        "reference": "U1",
        "value": "Arduino Nano",
        "quantity": 1,
        "price_usd": 3.50,
        "supplier": "DigiKey",
        "part_number": "A000005",
        "availability": "in_stock"
      },
      {
        "reference": "R1, R2, R3",
        "value": "150Ω",
        "quantity": 3,
        "price_usd": 0.10,
        "price_total_usd": 0.30,
        "supplier": "DigiKey",
        "part_number": "RC0805FR-07150RL",
        "availability": "in_stock"
      },
      {
        "reference": "C1",
        "value": "10µF",
        "quantity": 1,
        "price_usd": 0.15,
        "supplier": "DigiKey"
      }
    ],
    "total_cost_usd": 4.95,
    "total_components": 5,
    "unique_parts": 3
  }
}
```

---

### 6. Export Gerber Files

**Endpoint:** `POST /api/v2/manufacture/gerber`

**Purpose:** Convert KiCAD to Gerber files for manufacturing

**Request:**
```bash
curl -X POST http://localhost:5000/api/v2/manufacture/gerber \
  -F "kicad_file=@my_board.kicad_pcb" \
  -F "apply_fixes=true"
```

**Response:**
```json
{
  "success": true,
  "gerber_files": {
    "zip_filename": "my_board_gerbers_20260112.zip",
    "download_url": "/api/v2/manufacture/download-gerber/my_board_gerbers_20260112.zip",
    "files_included": [
      "my_board-F_Cu.gbr",
      "my_board-B_Cu.gbr",
      "my_board-F_Mask.gbr",
      "my_board-B_Mask.gbr",
      "my_board-Edge_Cuts.gbr",
      "my_board-PTH.drl"
    ],
    "manufacturer_ready": true,
    "notes": "Ready for JLCPCB, PCBWay, or similar manufacturers"
  }
}
```

**Download Gerber:**
```bash
curl -O http://localhost:5000/api/v2/manufacture/download-gerber/my_board_gerbers_20260112.zip
```

---

### 7. Get Learning Paths

**Endpoint:** `GET /api/learning-paths`

**Purpose:** Get structured curriculum for learning

**Response:**
```json
{
  "paths": [
    {
      "id": "beginner",
      "name": "Arduino Basics",
      "level": 1,
      "duration_hours": 20,
      "modules": [
        {
          "id": "module_1",
          "name": "Getting Started with Arduino",
          "duration_hours": 4,
          "topics": ["IDE setup", "First sketch", "Serial monitor"]
        }
      ]
    }
  ]
}
```

---

### 8. Get Recipe Recommendations

**Endpoint:** `POST /api/recipes/generate`

**Purpose:** Get project ideas based on available components

**Request:**
```json
{
  "inventory": [
    {"id": "esp32", "quantity": 1, "condition": "new"},
    {"id": "bme280", "quantity": 1, "condition": "used"}
  ],
  "skill_level": 2,
  "goal": "learning"
}
```

**Response:**
```json
{
  "recipes": [
    {
      "project_name": "Air Quality Monitor",
      "difficulty": 2,
      "time_hours": 3,
      "components_available": 2,
      "components_needed": 0,
      "estimated_cost": 0,
      "roi_score": 95,
      "description": "Build a WiFi-enabled air quality monitor using ESP32 and BME280"
    }
  ]
}
```

---

## Data Formats

### KiCAD Netlist Format (.net)

**Example:**
```
(export (version D)
  (design
    (source /path/to/project.kicad_pcb)
    (date "2026-01-12")
  )
  (components
    (comp (ref U1)
      (value Arduino_Nano)
      (footprint Package_DIP:DIP-30)
    )
    (comp (ref R1)
      (value 150)
      (footprint Resistor_SMD:R_0805)
    )
  )
  (nets
    (net (code 1) (name VCC)
      (node (ref U1) (pin 27))
      (node (ref R1) (pin 1))
    )
  )
)
```

**Frontend doesn't need to parse this** - just upload to backend.

---

### KiCAD PCB Format (.kicad_pcb)

**Example (simplified):**
```lisp
(kicad_pcb (version 20221018) (generator pcbnew)
  (general
    (thickness 1.6)
  )
  (paper "A4")
  (layers
    (0 "F.Cu" signal)
    (31 "B.Cu" signal)
  )
  (module "Resistor_SMD:R_0805" (at 15.2 30.5)
    (fp_text reference "R1" (at 0 0))
    (fp_text value "150" (at 0 2))
  )
  (segment (start 10.5 20.3) (end 25.8 20.3) (width 0.5) (layer "F.Cu"))
)
```

**Frontend doesn't parse** - backend handles this.

---

## Error Responses

### Standard Error Format

```json
{
  "error": "Invalid file format",
  "message": "Expected .kicad_pcb or .net file, got .txt",
  "code": 400
}
```

### Common Error Codes

- `400` - Bad request (invalid file, missing parameters)
- `401` - Unauthorized (API key invalid)
- `404` - Not found (endpoint doesn't exist)
- `413` - File too large (>10MB)
- `500` - Server error (backend crashed)

---

## File Upload Limits

- **Max file size:** 10MB
- **Accepted formats:**
  - KiCAD: `.kicad_pcb`, `.net`
  - Images: `.jpg`, `.png` (for vision analysis)
  - Gerber: `.gbr`, `.drl`
- **Max components:** 1000 per board

---

## Rate Limiting (Future)

**Not implemented yet**, but will be:

```
Free tier: 10 requests/hour
Pro tier: 100 requests/hour
Enterprise: Unlimited
```

**Response headers:**
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1705063200
```

---

## WebSocket Support (Future)

For real-time validation progress:

```javascript
const ws = new WebSocket('ws://localhost:5000/ws/validate');

ws.onmessage = (event) => {
  const progress = JSON.parse(event.data);
  console.log(`Validation ${progress.percent}% complete`);
};
```

**Not implemented yet** - use polling for now.

---

## CORS Configuration

Backend allows cross-origin requests from:
- `http://localhost:*` (development)
- `https://circuit-ai.vercel.app` (production frontend)
- `*` (temporary - will restrict later)

---

## Example Integration (TypeScript)

```typescript
// api-client.ts
class CircuitAIAPI {
  private baseURL = 'http://localhost:5000';

  async validateKiCAD(file: File): Promise<ValidationResult> {
    const formData = new FormData();
    formData.append('kicad_file', file);

    const response = await fetch(`${this.baseURL}/api/v2/workflow/validate-kicad`, {
      method: 'POST',
      body: formData
    });

    if (!response.ok) {
      throw new Error(`Validation failed: ${response.statusText}`);
    }

    return await response.json();
  }

  async generateBOM(file: File, includePricing: boolean = true): Promise<BOMResult> {
    const formData = new FormData();
    formData.append('netlist_file', file);
    formData.append('include_pricing', includePricing.toString());

    const response = await fetch(`${this.baseURL}/api/v2/manufacture/bom`, {
      method: 'POST',
      body: formData
    });

    return await response.json();
  }

  async getComponents(): Promise<Component[]> {
    const response = await fetch(`${this.baseURL}/api/components`);
    const data = await response.json();
    return data.components;
  }
}

// Usage in React component
const client = new CircuitAIAPI();

function UploadBoard() {
  const handleUpload = async (file: File) => {
    try {
      const result = await client.validateKiCAD(file);
      console.log('Validation result:', result);
      // Update UI with result.validation.issues
    } catch (error) {
      console.error('Upload failed:', error);
    }
  };

  return (
    <input
      type="file"
      accept=".kicad_pcb,.net"
      onChange={(e) => handleUpload(e.target.files[0])}
    />
  );
}
```

---

## Testing Endpoints

**Quick test with curl:**

```bash
# Health check
curl http://localhost:5000/api/health

# List components
curl http://localhost:5000/api/components | jq

# Validate example (create test file first)
echo '(export (version D))' > test.net
curl -X POST http://localhost:5000/api/v2/workflow/validate-kicad \
  -F "kicad_file=@test.net"
```

---

## Deployment

**Production URL:** `https://circuit-ai.railway.app` (to be deployed)

**Change baseURL in frontend:**
```typescript
const baseURL = process.env.NODE_ENV === 'production'
  ? 'https://circuit-ai.railway.app'
  : 'http://localhost:5000';
```

---

## Summary for Frontend Dev

**To integrate:**

1. Create API client class (see example above)
2. Call `validateKiCAD()` when user uploads file
3. Parse `result.validation.issues` to show in UI
4. Use `result.validation.components` and `result.validation.traces` for 3D rendering
5. Display `result.validation.fixes` as actionable buttons

**Key data structures:**
- `ValidationResult.issues[]` - List of problems
- `ValidationResult.components[]` - Component positions for 3D
- `ValidationResult.traces[]` - Trace paths for 3D rendering
- `ValidationResult.fixes[]` - Suggested solutions

**All JSON, no complex parsing needed.**
