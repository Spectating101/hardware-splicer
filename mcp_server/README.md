# Circuit-AI MCP Server

**Professional PCB validation, project recipes, and manufacturing tools via Model Context Protocol (MCP).**

[![Version](https://img.shields.io/badge/version-0.4.0-blue.svg)]()
[![MCP](https://img.shields.io/badge/MCP-compatible-success.svg)]()

---

## What is This?

An MCP server that brings Circuit-AI's professional electronics tools into your IDE:
- **Validate KiCAD designs** without leaving VSCode/Cursor/Claude Desktop
- **Get quantitative fixes**: "Widen trace to 2mm" not "traces too thin"
- **Find buildable projects** from your component inventory
- **Generate BOMs** with supplier links

---

## Installation

### Prerequisites
- Node.js 18+ (for MCP server)
- Python 3.8+ (for Circuit-AI API backend)
- Circuit-AI API running (defaults to `http://localhost:5000`)

### Install MCP Server

```bash
cd mcp_server
npm install
npm run build
```

### Install in Claude Desktop

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "circuit-ai": {
      "command": "node",
      "args": ["/path/to/Circuit-AI/mcp_server/dist/index.js"],
      "env": {
        "CIRCUIT_AI_API_URL": "http://localhost:5000",
        "CIRCUIT_AI_API_KEY": "your-api-key-here"
      }
    }
  }
}
```

### Install in VSCode (via Cline/Continue)

Add to your MCP settings:

```json
{
  "circuit-ai": {
    "command": "node",
    "args": ["/path/to/Circuit-AI/mcp_server/dist/index.js"],
    "env": {
      "CIRCUIT_AI_API_URL": "http://localhost:5000"
    }
  }
}
```

---

## Available Tools

### 1. `validate-kicad`
**Validate KiCAD PCB design with quantitative fixes**

```typescript
validate-kicad({
  netlist_path: "/path/to/design.net",
  hints: {  // optional
    sources: [{
      name: "VUSB",
      net: "VBUS",
      volts: 5.0,
      max_current_a: 0.5
    }],
    loads_cc: [{
      name: "ESP32",
      net: "+3V3",
      amps: 0.24
    }]
  }
})
```

**Returns:**
```json
{
  "status": "validation_warning",
  "validation": {
    "issues": [
      {
        "severity": "warning",
        "component": "Trace +3V3",
        "issue": "Excessive voltage drop",
        "physics": {
          "current_a": 1.2,
          "voltage_drop": 0.35,
          "required_width_mm": 2.0
        },
        "solution": "Widen trace to 2.0mm"
      }
    ]
  }
}
```

---

### 2. `suggest-projects`
**Get buildable project recommendations**

```typescript
suggest-projects({
  inventory: [
    { id: "esp32", condition: "new", quantity: 1 },
    { id: "bme280", condition: "used", quantity: 1 }
  ],
  skill_level: 2,  // 1-5
  goal: "learning",  // "learning", "roi", or "speed"
  budget: 50
})
```

**Returns:**
```json
{
  "status": "success",
  "project": {
    "name": "Air Quality Monitor",
    "difficulty": "medium",
    "build_time_hours": 3.0,
    "economics": {
      "roi_percent": 150.0,
      "missing_parts_cost": 0.0
    },
    "inventory": {
      "match_percent": 100,
      "components_needed": []
    }
  },
  "instructions": {...}
}
```

---

### 3. `calculate-roi`
**Calculate economics for a project**

```typescript
calculate-roi({
  project_name: "Air Quality Monitor",
  inventory: [...]  // optional
})
```

---

### 4. `generate-bom`
**Generate bill of materials**

```typescript
generate-bom({
  netlist_path: "/path/to/design.net",
  include_pricing: true
})
```

---

### 5. `get-build-instructions`
**Get step-by-step build guide**

```typescript
get-build-instructions({
  project_name: "Air Quality Monitor"
})
```

---

## Usage Examples

### In Claude Desktop

```
User: "Validate my PCB design"
Claude: [Uses validate-kicad tool]
Result: "Your design has 2 issues:
1. Trace +3V3 needs to be 2mm wide (currently 0.5mm)
2. LDO dropout is marginal, increase Vin to 3.9V"

User: "What can I build with ESP32 and BME280?"
Claude: [Uses suggest-projects tool]
Result: "You can build an Air Quality Monitor!
- You have 100% of parts
- Cost: $0 (no missing parts)
- ROI: 150%
- Build time: 3 hours"
```

### In VSCode (via AI assistant)

```typescript
// Ask your AI assistant:
"Check if my PCB design has any issues"

// It will use validate-kicad tool and show:
// - Power tree validation
// - Trace drop calculations
// - Quantitative fixes
```

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CIRCUIT_AI_API_URL` | `http://localhost:5000` | Circuit-AI API backend URL |
| `CIRCUIT_AI_API_KEY` | _(empty)_ | API key for authentication (optional) |

---

## Development

### Build
```bash
npm run build
```

### Watch mode
```bash
npm run watch
```

### Test locally
```bash
# Terminal 1: Start Circuit-AI API
cd ..
python3 api_server.py

# Terminal 2: Test MCP server
cd mcp_server
npm run dev
```

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│            Claude Desktop / VSCode / Cursor         │
│                                                     │
│  User: "Validate my PCB"                            │
│                                                     │
└──────────────────┬──────────────────────────────────┘
                   │ MCP Protocol
                   ↓
┌─────────────────────────────────────────────────────┐
│          Circuit-AI MCP Server (Node.js)            │
│                                                     │
│  Tools:                                             │
│  • validate-kicad                                   │
│  • suggest-projects                                 │
│  • generate-bom                                     │
│                                                     │
└──────────────────┬──────────────────────────────────┘
                   │ HTTP/REST
                   ↓
┌─────────────────────────────────────────────────────┐
│       Circuit-AI API Backend (Python/Flask)         │
│                                                     │
│  v2 Workflows:                                      │
│  • POST /api/v2/workflow/validate-kicad             │
│  • POST /api/v2/workflow/beginner                   │
│  • GET  /api/instructions/<project>                 │
│                                                     │
│  Engines:                                           │
│  • KiCAD netlist compiler                           │
│  • DC circuit solver (MNA)                          │
│  • Power tree validator                             │
│  • Recipe optimizer                                 │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

## Pricing (When Deployed)

| Tier | Price | Tools |
|------|-------|-------|
| **Free** | $0 | 10 validations/month |
| **Maker** | $19/mo | Unlimited validations + recipes |
| **Pro** | $49/mo | + Manufacturing (Gerber, BOM, JLCPCB) |
| **Team** | $149/mo | 5 seats + API access |

---

## Troubleshooting

### "Connection refused"
- Make sure Circuit-AI API is running (`python3 api_server.py`)
- Check `CIRCUIT_AI_API_URL` points to correct URL

### "File not found"
- Provide absolute path to .net file
- Check file exists and is readable

### "Tool not available"
- Rebuild MCP server: `npm run build`
- Restart Claude Desktop / IDE

---

## Roadmap

**Week 1 (Current):**
- [x] MCP server core
- [x] validate-kicad tool
- [x] suggest-projects tool
- [ ] generate-bom tool (basic)

**Week 2:**
- [ ] Gerber generation tool
- [ ] JLCPCB integration
- [ ] Enhanced BOM with pricing

**Week 3:**
- [ ] DUM-E design assistant tool
- [ ] Visual PCB analysis tool
- [ ] Streaming support for long outputs

---

## Support

- **Issues:** [GitHub Issues](https://github.com/user/circuit-ai/issues)
- **Docs:** [V2_API_GUIDE.md](../V2_API_GUIDE.md)
- **API Backend:** [api_server.py](../api_server.py)

---

**Built by:** Circuit-AI Team
**License:** MIT
**Version:** 0.4.0
