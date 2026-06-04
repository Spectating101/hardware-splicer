# Circuit-AI MCP Server

MCP (Model Context Protocol) server for Circuit-AI - AI-powered circuit diagnosis and repair guidance.

## Features

- **Device Diagnosis**: Analyze symptoms and identify device issues with confidence scoring
- **Repair Guides**: Step-by-step repair instructions with tools, parts, and safety warnings
- **Circuit Validation**: Check circuit designs for power mismatches and connection issues
- **Project Recipes**: Generate project ideas from your component inventory

## Installation

```bash
npm install circuit-ai-mcp
```

Or clone and build:

```bash
git clone https://github.com/your-repo/circuit-ai-mcp
cd circuit-ai-mcp
npm install
npm run build
```

## Configuration

Set the API URL via environment variable:

```bash
export CIRCUIT_AI_API_URL=https://your-circuit-ai-api.com
```

Default: `http://localhost:5000`

## Usage with Claude Desktop

Add to your Claude Desktop config (`~/.config/claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "circuit-ai": {
      "command": "npx",
      "args": ["circuit-ai-mcp"],
      "env": {
        "CIRCUIT_AI_API_URL": "https://your-api-url.com"
      }
    }
  }
}
```

## Available Tools

### diagnose_device

Diagnose device issues from symptoms.

```json
{
  "symptoms": ["battery drains fast", "shuts down at 30%", "phone getting hot"],
  "device_type": "iPhone"
}
```

Returns:
- Top recommendation with confidence score
- Difficulty level
- Estimated time and cost
- Link to repair guide

### get_repair_guide

Get detailed repair instructions.

```json
{
  "issue_name": "iPhone Battery Replacement",
  "preview": false
}
```

Returns:
- Step-by-step instructions (10-16 steps)
- Tools needed
- Parts list with prices
- Safety warnings
- Pro tips

### validate_circuit

Check circuit design for issues.

```json
{
  "components": [
    {"id": "U1", "type": "ESP32", "value": "3.3V"},
    {"id": "R1", "type": "resistor", "value": "10k"}
  ],
  "connections": [
    {"from": "U1.GPIO2", "to": "R1.1"}
  ]
}
```

Returns:
- Validation status
- Power analysis
- Warnings and suggestions

### list_repair_guides

List all available repair guides.

Returns array of guides with:
- Issue name
- Device type
- Difficulty
- Time estimate

### generate_project_recipe

Generate project ideas from inventory.

```json
{
  "inventory": ["ESP32", "DHT22", "OLED display", "resistors"],
  "project_type": "sensor"
}
```

Returns:
- Matching projects
- Required vs available components
- Instructions
- ROI estimate

## Supported Devices

- iPhone (Screen, Battery, Charging Port, Water Damage, Camera)
- Samsung/Android (Screen, Battery)
- Laptop (Screen, Battery, Keyboard, SSD/RAM, Overheating)

## License

MIT
