# Functionality-First 3D Splicer

## 🎯 **Vision: Function-Driven Design**

The 3D Splicer transforms from a simple "draw a box" tool into a **functional specification-driven** system that optimizes designs to meet real-world requirements through iterative LLM-guided optimization.

## 🧠 **Mental Model**

- **Input**: Functional Requirements (what it must do), Constraints (can't violate), Tests (how we'll verify)
- **Engine**: LLM proposes design params → CAD builds → Evaluator tests → Loop until all tests pass or budget exhausted  
- **Outputs**: Final STL/GLB + Report (which tests passed, margins, rationale)

## 🔧 **Architecture**

### Core Components

1. **Functional Specification Schema** - Structured requirements and constraints
2. **LLM Planner** - Proposes design parameters based on requirements
3. **Multi-Domain Evaluator** - Tests geometry against functional requirements
4. **Iteration Engine** - Orchestrates optimization loop
5. **Template System** - Generates CadQuery geometry from parameters

### Data Flow

```
Functional Spec → LLM Planner → Design Parameters → CadQuery Template → STL
                     ↑                                                      ↓
              Revision Logic ← Evaluator ← STL Analysis ← Mesh Validation
```

## 📋 **Functional Specification**

### Example Specification

```json
{
  "id": "sensor_board_protection_v1",
  "context": {
    "board_bbox_mm": {"x": 50.0, "y": 30.0, "z": 1.6},
    "mounts": [{"type": "standoff", "pos": [5, 5], "dia": 2.5, "height": 3}],
    "keepouts": [{"shape": "rect", "at": [25, 15], "size": [10, 8]}],
    "io": [{"type": "usb", "edge": "south", "offset_mm": 25.0, "slot": [12, 5]}]
  },
  "functional_requirements": [
    {"id": "F1", "goal": "drop_protection", "absorb_energy_J": 3.0, "max_strain_pct": 6},
    {"id": "F2", "goal": "thermal_clearance", "min_air_gap_mm": 1.0},
    {"id": "F3", "goal": "toolless_access", "max_open_time_s": 5}
  ],
  "constraints": [
    {"id": "C1", "rule": "overall_envelope_mm", "value": "[60, 40, 15]"},
    {"id": "C2", "rule": "no_geometry_in_keepouts"},
    {"id": "C3", "rule": "printability:overhang_angle_deg", "value": 55}
  ],
  "materials": {"primary": "PLA", "infill_pct": 20, "layer_height_mm": 0.2},
  "iteration_budget": {"max_iters": 8, "max_seconds": 300}
}
```

### Specification Schema

- **Context**: Physical constraints (board size, mounts, keepouts, IO)
- **Functional Requirements**: What the case must accomplish (drop protection, thermal, accessibility)
- **Constraints**: Hard limits (envelope, printability, assembly)
- **Materials**: 3D printing parameters
- **Iteration Budget**: Optimization limits

## 🔄 **Optimization Loop**

### 1. LLM Planner
- **Input**: Functional spec + iteration history
- **Output**: Design parameters (shell thickness, boss locations, vent patterns, latch design)
- **Logic**: Heuristic-based parameter estimation with failure-driven revision

### 2. CAD Builder
- **Input**: Design parameters
- **Output**: STL file
- **Process**: Parameter-driven CadQuery template generation

### 3. Multi-Domain Evaluator
- **Geometric**: Fit, clearance, envelope constraints, keepout violations
- **Printability**: Overhang angles, wall thickness, mesh validity
- **Functional**: Drop protection, thermal clearance, accessibility
- **Output**: Pass/fail per test + satisfaction scores

### 4. Revision Logic
- **Input**: Test failures + iteration history
- **Output**: Revised parameters
- **Strategy**: Monotonic improvements, constraint-based adjustments

## 🚀 **Usage Modes**

### 1. Standalone CLI
```bash
# Create example specification
splicer create-example my_board.json

# Run optimization
splicer run -f my_board.json -o output/
```

### 2. REST API
```bash
# Create planning job
curl -X POST http://localhost:8000/v1/plan \
  -H "Content-Type: application/json" \
  --data @functional_spec.json

# Check job status
curl http://localhost:8000/v1/jobs/my_job_id/status

# Download results
curl http://localhost:8000/v1/jobs/my_job_id/artifact?type=stl
```

### 3. Circuit.AI Integration
```python
from circuit_ai_client import generate_case

# Circuit.AI generates functional spec from board analysis
spec = {
    "id": "circuit_ai_board_v1",
    "context": {...},  # From Circuit.AI analysis
    "functional_requirements": [...]  # From Circuit.AI requirements
}

result = generate_case(spec)
# Returns STL path + validation report
```

## 🧪 **Evaluation Domains**

### Geometric Evaluator
- **Envelope Constraints**: Overall size limits
- **Board Clearance**: Adequate space around PCB
- **Keepout Violations**: No geometry in restricted areas
- **Mount Accessibility**: Mount points reachable

### Printability Evaluator
- **Mesh Validity**: Watertight, manifold, no degenerate faces
- **Overhang Angles**: Maximum printable overhang
- **Wall Thickness**: Minimum printable features
- **Feature Size**: Printable minimum dimensions

### Functional Evaluators

#### Drop Protection
- **Energy Absorption**: Estimated based on shell thickness
- **Strain Limits**: Maximum deformation under load
- **Impact Distribution**: Shell geometry analysis

#### Thermal Management
- **Air Gap**: Ventilation clearances
- **Ventilation Area**: Surface area for heat dissipation
- **Airflow Paths**: Convective cooling channels

#### Accessibility
- **Opening Time**: Time to access internal components
- **Latch Design**: Tool-less access mechanisms
- **Ergonomic Factors**: Human interaction requirements

## 📊 **Scoring System**

Each test produces:
- **Pass/Fail**: Boolean result
- **Score**: 0-1 satisfaction score
- **Margin**: How much above/below threshold
- **Details**: Human-readable explanation

Overall optimization score = average of all test scores

## 🎯 **Success Criteria**

### Stopping Conditions
1. **All tests pass** → Success, return best design
2. **Max iterations reached** → Return best attempt
3. **Timeout exceeded** → Return best attempt
4. **No improvement** → Return best attempt

### Output Artifacts
- **STL File**: Final printable geometry
- **GLB Preview**: Web-viewable 3D model
- **Parameters**: Final design parameters
- **Report**: Iteration history + test results
- **Validation**: Comprehensive test summary

## 🔮 **Future Enhancements**

### Advanced Features
- **FEA Integration**: Finite element analysis for drop protection
- **Thermal Simulation**: CFD-based thermal analysis
- **Material Optimization**: Multi-material design
- **Assembly Analysis**: Interference checking

### LLM Improvements
- **Real LLM Integration**: GPT-4/Claude for parameter planning
- **Learning from History**: Cross-project parameter optimization
- **Multi-Objective**: Pareto optimization for conflicting requirements

### Circuit.AI Integration
- **Automatic Spec Generation**: Board analysis → functional requirements
- **Real-time Feedback**: Live optimization during design
- **Batch Processing**: Multiple boards in parallel

## 🏆 **Benefits**

### For Users
- **Function-First**: Specify what you need, not how to build it
- **Automated Optimization**: No manual CAD tweaking
- **Validated Results**: Every design tested against requirements
- **Traceable Decisions**: Complete optimization history

### For Circuit.AI
- **Seamless Integration**: Drop-in API for case generation
- **Deterministic Output**: Reliable, testable results
- **Scalable Architecture**: Handle multiple concurrent optimizations
- **Rich Metadata**: Detailed reports for design validation

---

## 🚀 **Getting Started**

1. **Create Specification**: Define functional requirements
2. **Run Optimization**: Let the system find optimal parameters
3. **Validate Results**: Review test results and margins
4. **Generate Artifacts**: Download STL and reports
5. **Print & Test**: Physical validation of functional requirements

**This is the future of functional 3D design - specify what you need, not how to build it!** 🎯
