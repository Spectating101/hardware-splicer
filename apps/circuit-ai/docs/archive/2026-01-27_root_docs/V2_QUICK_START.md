# Circuit-AI v2 API - Quick Start Guide

**Version:** 0.4.0 | **Status:** Production Ready | **Date:** 2026-01-09

---

## What is v2?

v2 integrates educational tools with professional PCB validation into **complete workflows**:

```
Learn → Build → Validate → Manufacture
```

---

## Start Server

```bash
python3 api_server.py
```

Server starts on: `http://localhost:5000`

---

## Three Main Endpoints

### 1. Beginner Workflow
**Get project recommendations based on skill and inventory**

```bash
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
```

**Returns:**
- Project recommendation
- Build instructions
- Cost estimate
- Next steps

---

### 2. Complete Workflow
**End-to-end: Recipe → Instructions → Validation**

```bash
curl -X POST http://localhost:5000/api/v2/workflow/complete \
  -H "Content-Type: application/json" \
  -d '{
    "user": {
      "skill_level": 2,
      "inventory": [...],
      "goal": "learning"
    },
    "project_name": "Air Quality Monitor"
  }'
```

**Returns:**
- Project details
- Build instructions
- Validation results (if KiCAD file provided)
- Manufacturing status

---

### 3. KiCAD Validation
**Professional PCB validation with quantitative fixes**

```bash
curl -X POST http://localhost:5000/api/v2/workflow/validate-kicad \
  -F "kicad_file=@my_design.net"
```

**Returns:**
- Validation issues with severity
- Physics calculations (current, voltage, power)
- Quantitative fixes: "Widen trace to 2mm"
- Manufacturing readiness

---

## Example Response

```json
{
  "status": "success",
  "project": {
    "name": "Air Quality Monitor",
    "difficulty": "medium",
    "build_time_hours": 3.0,
    "economics": {
      "parts_cost": 14.0,
      "roi_percent": 150.0,
      "missing_parts_cost": 0.0
    }
  },
  "instructions": {
    "steps": [...]
  },
  "next_steps": [
    "Build Air Quality Monitor",
    "Estimated time: 3.0 hours",
    "Cost: $0.00"
  ]
}
```

---

## User Skill Levels

```python
1 = BEGINNER      # Never built anything
2 = HOBBYIST      # Built a few projects
3 = INTERMEDIATE  # Comfortable with circuits
4 = ADVANCED      # Designs PCBs
5 = PROFESSIONAL  # EE degree / commercial
```

---

## Demo

```bash
python3 demo_v2_api.py
```

Shows complete workflows for:
- Beginner (learning paths)
- Hobbyist (project recommendations)
- Complete end-to-end
- KiCAD validation example

---

## Key Advantages

| Before | After |
|--------|-------|
| Generic: "Traces too thin" | Quantitative: "Widen to 2mm" |
| Manual chaining | Single API call |
| Educational OR professional | Educational AND professional |
| Text-based | Complete workflows |

---

## Documentation

| File | Purpose |
|------|---------|
| **V2_QUICK_START.md** | This file |
| **V2_API_GUIDE.md** | Complete API documentation |
| **V2_INTEGRATION_SUMMARY.md** | Executive summary |
| **demo_v2_api.py** | Interactive demo |

---

## Quick Test

```bash
# Health check
curl http://localhost:5000/api/health

# API documentation
curl http://localhost:5000/

# Test beginner workflow
curl -X POST http://localhost:5000/api/v2/workflow/beginner \
  -H "Content-Type: application/json" \
  -d '{"skill_level": 1, "goal": "learning"}'
```

---

## What's Included

✅ 3 v2 workflow endpoints
✅ 29 project recipes
✅ 5 learning paths (106 hours)
✅ Professional KiCAD validation
✅ Quantitative fixes
✅ Skill-based routing

---

**That's it! You're ready to use the v2 API.**

For detailed documentation, see: **[V2_API_GUIDE.md](V2_API_GUIDE.md)**
