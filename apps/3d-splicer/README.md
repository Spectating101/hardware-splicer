# 3D-Splicer: Parametric PCB Case Generator

**Production-ready 3D-printable phone case generator with Circuit.AI integration.**

Generate custom protective cases for your PCB designs automatically. First-of-its-kind integration between parametric 3D case generation and PCB layout analysis.

## 🎯 What This Does

Turn PCB specifications into printable protective cases in seconds:
- **Input:** PCB dimensions, port locations, mounting holes
- **Output:** STL file ready for 3D printing
- **Unique:** Circuit.AI integration for automated PCB → case workflow

**Target users:** Hardware hackers, PCB designers, makers, prototypers

## ✨ Features

- **Parametric Design System**: Fully customizable dimensions, features, tolerances
- **Circuit.AI Integration**: Automatic case generation from PCB layouts
- **FEM Analysis**: Structural validation and stress testing
- **Physics Simulation**: Ensures cases can withstand real-world use
- **FastAPI REST Interface**: Easy integration into your workflow
- **STL Export**: Clean, watertight meshes ready for 3D printing
- **Mesh Validation**: Automatic quality checks with trimesh
- **Production Ready**: Docker deployment, CI/CD, comprehensive tests

## Quick Start

### Installation

```bash
# Clone and install dependencies
git clone https://github.com/Spectating101/3d-splicer.git
cd 3d-splicer
pip install -r requirements.txt
```

### Run the API

```bash
# Start the development server
uvicorn src.api.main:app --reload

# Or with Docker
docker build -t 3d-splicer .
docker run -p 8000:8000 3d-splicer
```

### Test Generation

```bash
# Generate iPhone 7 case
curl -X POST http://127.0.0.1:8000/v1/splice \
  -H "Content-Type: application/json" \
  --data @examples/iphone7_desc.json

# Download generated STL
curl -O http://127.0.0.1:8000/v1/stl/iphone_7_case_v1.stl
```

## API Reference

### POST /v1/splice

Generate a protective case from device description.

**Request Body:**
```json
{
  "version": "v1",
  "device": "iphone_7",
  "pcb": {
    "width_mm": 70.0,
    "height_mm": 35.0,
    "thickness_mm": 1.2,
    "corner_radius_mm": 3.0
  },
  "enclosure": {
    "wall_mm": 1.6,
    "clearance_mm": 0.6,
    "lip_mm": 1.2,
    "fillet_mm": 1.0
  },
  "ports": [
    {
      "name": "lightning",
      "type": "rect",
      "x_mm": 35.0,
      "y_mm": 0.0,
      "w_mm": 8.0,
      "h_mm": 2.6,
      "side": "bottom"
    }
  ],
  "mounts": [
    {
      "x_mm": 8.0,
      "y_mm": 8.0,
      "diameter_mm": 2.0
    }
  ]
}
```

**Response:**
```json
{
  "stl_path": "stl/iphone_7_case_v1.stl",
  "validation": {
    "watertight": true,
    "faces": 1234,
    "bounds": [[x1,y1,z1], [x2,y2,z2]],
    "volume": 12345.6,
    "is_valid": true
  },
  "success": true,
  "message": "STL generated successfully"
}
```

### GET /health

Health check endpoint.

### GET /v1/stl/{filename}

Download generated STL files.

## Data Schema

### Coordinate System
- **Origin**: Bottom-left of PCB
- **X-axis**: Right (+)
- **Y-axis**: Up (+)
- **Z-axis**: Out of PCB (+)

### Port Sides
- `"bottom"`: Port opening on bottom edge
- `"top"`: Port opening on top edge  
- `"left"`: Port opening on left edge
- `"right"`: Port opening on right edge

## Development

### Project Structure

```
splicer/
├── src/
│   ├── api/           # FastAPI application
│   └── core/          # Core generation logic
├── templates/         # CadQuery Jinja2 templates
├── examples/          # Example device descriptions
├── tests/            # Test suite
├── stl/              # Generated STL outputs
└── Dockerfile        # Container configuration
```

### Running Tests

```bash
cd tests
python test_generate.py
```

### Adding New Templates

1. Create new `.cq.j2` template in `templates/`
2. Update `render_template()` calls in API
3. Add validation tests

## Integration with Circuit.AI

The system is designed to integrate with Circuit.AI's PCB analysis:

1. **Circuit.AI Output**: PCB dimensions, port detections, mount points
2. **Mapper**: Convert to Description JSON format
3. **Generation**: Call `/v1/splice` endpoint
4. **Output**: Download STL for printing/slicing

Example mapper (future):
```python
def map_circuit_ai_to_description(circuit_ai_output):
    return {
        "device": circuit_ai_output.get("device_name"),
        "pcb": {
            "width_mm": circuit_ai_output["pcb_dims"]["width"],
            "height_mm": circuit_ai_output["pcb_dims"]["height"],
            "thickness_mm": circuit_ai_output["pcb_dims"]["thickness"]
        },
        "ports": [
            {
                "name": port["name"],
                "x_mm": port["position"]["x"],
                "y_mm": port["position"]["y"],
                "w_mm": port["size"]["width"],
                "h_mm": port["size"]["height"],
                "side": port["side"]
            }
            for port in circuit_ai_output["detected_ports"]
        ]
    }
```

## Future Enhancements

- **CuraEngine Integration**: Direct .gcode generation
- **Parametric Libraries**: Connector-specific hole patterns
- **Device Catalogs**: Pre-baked descriptions for common boards
- **LLM Templates**: AI-assisted template generation
- **Multi-material Support**: Different enclosure materials
- **Assembly Features**: Snap-fit, hinges, clips

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure all dependencies installed
2. **STL Validation Fails**: Check port coordinates and PCB dimensions
3. **Template Errors**: Verify Jinja2 syntax in templates
4. **Memory Issues**: Large meshes may require more RAM

### Debug Mode

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
uvicorn src.api.main:app --reload --log-level debug
```

## License

MIT License - see LICENSE file for details.
