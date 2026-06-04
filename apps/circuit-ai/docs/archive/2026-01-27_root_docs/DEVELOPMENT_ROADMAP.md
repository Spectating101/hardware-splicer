# Circuit-AI Full Platform Development Roadmap

**Date:** 2026-01-17
**Goal:** Push from "PCB validation tool" → "Complete build-to-sell platform"
**Context:** Dual track - MCP ready NOW (cash), full vision needs work

---

## Current State Discovery

### ✅ What EXISTS (Infrastructure)
```
Total intelligence code: 18,350 lines!

Key files:
- recipe_optimizer.py (1,054 lines) - Project recipe engine
- build_instructions.py (594 lines) - Step-by-step guides
- arduino_code_generator.py (368 lines) - Code generation
- learning_paths.py (733 lines) - Educational paths
- component_pricer.py (413 lines) - Pricing engine
- design_generator.py (719 lines) - Circuit design
- + 40 more intelligence modules
```

**This is WAY more complete than the API suggests!**

### ❌ What's MISSING (Data)
```
1. Component database: 100 items, ALL prices = $0
2. Project recipes: 1 defined (need 20-30)
3. Build instructions: Code exists, data missing
4. Arduino sketches: Generator exists, templates missing
5. Market pricing: Code exists, no API integration
```

**Pattern: Code infrastructure is 80% done, data population is 5% done**

---

## The Gap Analysis

| Component | Code | Data | Integration | Total |
|-----------|------|------|-------------|-------|
| **PCB Validation** | 100% | 100% | 100% | ✅ **100%** |
| **Gerber Export** | 100% | 100% | 100% | ✅ **100%** |
| **BOM Generation** | 100% | 50% | 100% | 🟡 **83%** |
| **Component DB** | 100% | 0% | 100% | 🟡 **67%** |
| **Project Recipes** | 100% | 5% | 30% | ❌ **45%** |
| **Build Instructions** | 100% | 0% | 30% | ❌ **43%** |
| **Arduino Code** | 100% | 0% | 30% | ❌ **43%** |
| **Market Analysis** | 80% | 0% | 0% | ❌ **27%** |
| **Learning Paths** | 100% | 50% | 50% | 🟡 **67%** |

**Overall Platform Completion: ~60%**

---

## Development Tracks

### Track 1: Quick Wins (1-2 weeks)
**Goal:** Get ONE complete project working end-to-end

**Week 1: "Smart Plant Monitor" Template**
```
Day 1-2: Component pricing automation
  → Scrape DigiKey API for 100 components
  → Auto-populate prices in database
  → Test: GET /api/components returns real prices

Day 3-4: First complete project template
  → Pick "Smart Plant Monitor" (beginner-friendly)
  → Define full ProjectRecipe with real data
  → Write complete build instructions
  → Create Arduino code template

Day 5-7: Integration & testing
  → Wire recipe → instructions → code → validation
  → Test complete workflow end-to-end
  → Fix any integration issues
```

**Deliverable:** ONE product users can actually build and sell

### Track 2: Scale It (2-3 weeks)
**Goal:** 10 complete projects across difficulty levels

**Projects to add (priority order):**
1. Smart Plant Monitor (beginner) ✓ From Track 1
2. LED Mood Light (beginner)
3. Distance Parking Sensor (beginner)
4. WiFi Weather Station (intermediate)
5. Air Quality Monitor (intermediate)
6. Home Security System (intermediate)
7. Robot Car (intermediate)
8. Drone Flight Controller (advanced)
9. Smart Thermostat (advanced)
10. Solar Power Monitor (advanced)

**Template per project:**
- Component list with prices
- Build instructions (8-12 steps)
- Arduino code (tested)
- Circuit diagram (Fritzing)
- Market analysis (Amazon/Etsy pricing)
- ROI calculation

### Track 3: Market Intelligence (1-2 weeks)
**Goal:** Automated arbitrage analysis

**Phase 1: Data collection**
```python
# Auto-scrape product prices
sources = [
    "Amazon" (API if available, else scraping),
    "Etsy" (API available),
    "eBay" (API available),
    "AliExpress" (for cheap sourcing)
]

for project in projects:
    market_price = scrape_average_price(project.name)
    build_cost = sum([component.price for c in project.components])
    profit_margin = market_price - build_cost
    roi = (profit_margin / build_cost) * 100
```

**Phase 2: Intelligence layer**
- Identify profitable niches
- Suggest component substitutions to maximize profit
- Calculate scaling economics (1 vs 10 vs 100 units)
- Recommend optimal selling platform

---

## Implementation Plan

### Sprint 1: Foundation (Days 1-3)
**Goal:** Data infrastructure ready

**Tasks:**
1. ✅ Component price scraper
   ```python
   # Auto-populate from DigiKey API
   # File: src/data/populate_prices.py
   ```

2. ✅ Project template schema
   ```python
   # Standardize project format
   # File: src/intelligence/project_schema.py
   ```

3. ✅ Database migration
   ```python
   # Move from YAML to SQLite for projects
   # Easier to query, update, scale
   ```

**Output:** Clean data layer ready for population

### Sprint 2: First Product (Days 4-7)
**Goal:** "Smart Plant Monitor" fully working

**Tasks:**
1. ✅ Define complete recipe
   ```python
   {
     "name": "Smart Plant Monitor",
     "components": [
       {"name": "ESP32", "price": 8.00, "quantity": 1},
       {"name": "Soil Moisture Sensor", "price": 3.00, "quantity": 1},
       {"name": "OLED Display", "price": 6.00, "quantity": 1},
       # ... full BOM
     ],
     "build_cost": 25.00,
     "market_price": 55.00,
     "profit": 30.00,
     "roi": "120%"
   }
   ```

2. ✅ Write build instructions
   ```markdown
   Step 1: Connect soil sensor to ESP32
     - Sensor VCC → ESP32 3.3V
     - Sensor GND → ESP32 GND
     - Sensor DATA → ESP32 GPIO34

   Step 2: Connect OLED display
     - OLED VCC → ESP32 3.3V
     - OLED GND → ESP32 GND
     - OLED SDA → ESP32 GPIO21
     - OLED SCL → ESP32 GPIO22

   # ... 10 more steps
   ```

3. ✅ Create Arduino code
   ```cpp
   // Complete, tested sketch
   // Reads soil moisture
   // Displays on OLED
   // WiFi notifications
   ```

4. ✅ Test complete workflow
   ```bash
   POST /api/v2/workflow/complete
   {
     "user": {"skill_level": 2},
     "project_name": "Smart Plant Monitor"
   }

   # Should return EVERYTHING:
   # - Component list
   # - Instructions
   # - Code
   # - Cost analysis
   # - Next steps
   ```

**Output:** ONE complete, sellable product

### Sprint 3: Rapid Expansion (Days 8-14)
**Goal:** 5 more projects

**Strategy:** Template-based rapid creation
```python
# Use first project as template
# Swap components, adjust instructions
# Test each one

projects = [
    template_beginner("LED Mood Light"),
    template_beginner("Distance Sensor"),
    template_intermediate("Weather Station"),
    template_intermediate("Air Quality Monitor"),
    template_advanced("Drone FC")
]
```

**Output:** 6 total projects ready

### Sprint 4: Market Intelligence (Days 15-21)
**Goal:** Automated profit analysis

**Tasks:**
1. ✅ Amazon scraper
2. ✅ Etsy scraper
3. ✅ Cost calculator
4. ✅ ROI engine

**Output:** Every project shows:
- Build cost: $X
- Sells for: $Y
- Profit: $Z
- ROI: W%
- Best platform: Etsy/Amazon

---

## Code to Write (Prioritized)

### 1. Component Price Populator (HIGH PRIORITY)
```python
# File: scripts/populate_component_prices.py

import requests
import json

def scrape_digikey_price(component_name):
    # Use DigiKey API or scraping
    # Return current price
    pass

def update_database():
    with open('data/component_cache/component_database.json') as f:
        components = json.load(f)

    for component in components:
        price = scrape_digikey_price(component['name'])
        component['price'] = price
        component['supplier'] = 'DigiKey'
        component['last_updated'] = now()

    save(components)

# Run: python scripts/populate_component_prices.py
```

### 2. Project Recipe Generator (HIGH PRIORITY)
```python
# File: src/intelligence/project_generator.py

def create_project_template(name, difficulty, components):
    """Generate complete project from template"""

    recipe = ProjectRecipe(
        name=name,
        difficulty=difficulty,
        components=components,
        build_cost=sum([c.price * c.qty for c in components]),
        market_price=scrape_market_price(name),
        instructions=generate_instructions(components),
        code=generate_arduino_code(components),
        diagram=generate_fritzing(components)
    )

    return recipe
```

### 3. Complete Workflow Fixer (MEDIUM PRIORITY)
```python
# File: api_server.py (update existing endpoint)

@app.route('/api/v2/workflow/complete', methods=['POST'])
def complete_workflow():
    project_name = data['project_name']

    # Load from actual database (not hardcoded)
    recipe = load_project_recipe(project_name)

    if not recipe:
        return {"error": f"Project '{project_name}' not found"}

    # Return EVERYTHING
    return {
        "project": recipe.to_dict(),
        "components": recipe.components,
        "instructions": recipe.instructions,
        "code": recipe.arduino_code,
        "validation": validate_if_provided(kicad_file),
        "cost_analysis": {
            "build_cost": recipe.build_cost,
            "market_price": recipe.market_price,
            "profit": recipe.profit,
            "roi": recipe.roi
        },
        "next_steps": generate_next_steps(recipe)
    }
```

---

## Success Metrics

### Week 1 Goals
- ✅ All 100 components have real prices
- ✅ 1 complete project works end-to-end
- ✅ Workflow endpoint returns full data

### Week 2 Goals
- ✅ 6 projects available
- ✅ Each project has instructions + code
- ✅ Market pricing integrated

### Week 3 Goals
- ✅ 10+ projects
- ✅ Automated ROI calculation
- ✅ Platform shows "Top 5 Most Profitable Projects"

### Week 4 Goals
- ✅ 20+ projects
- ✅ Learning paths integrated
- ✅ User can go from idea → sellable product in 1 day

---

## What This Unlocks

### Business Model Evolution
```
Current (MCP only):
  → $9/mo for PCB validation
  → Target: Engineers
  → Revenue: $10-50K/mo at scale

With Full Platform:
  → $49/mo for product builder tier
  → Target: Entrepreneurs
  → Revenue: $100-500K/mo at scale

  PLUS:
  → Marketplace fees (10% of sales)
  → Component affiliate commissions
  → Premium project templates
```

### User Journeys Unlocked
```
Journey 1: "I Want to Start a Hardware Business"
  → Browse profitable projects
  → Pick one with good ROI
  → Get complete build guide
  → Validate design
  → Export manufacturing files
  → List on Etsy
  → Start selling!

Journey 2: "Learn Electronics While Building Products"
  → Start with LED Blink
  → Progress through learning path
  → Build portfolio of projects
  → Each project = sellable product
  → Graduate to professional designs
  → Launch hardware startup

Journey 3: "Rapid Prototyping Service"
  → Startup needs sensor prototype
  → Browse similar projects
  → Customize to requirements
  → Validate in minutes
  → Export files
  → Manufacture in days
```

---

## Next Steps (Immediate)

**Ready to START RIGHT NOW:**

1. **Component Price Automation** (2-3 days)
   - Write DigiKey scraper
   - Populate all 100 components
   - Verify prices are current

2. **First Project Template** (3-4 days)
   - Smart Plant Monitor
   - Complete instructions
   - Tested Arduino code
   - Market analysis

3. **Integration Test** (1 day)
   - Complete workflow endpoint works
   - Returns full project package
   - User can actually build it

**Total: ~1 week to first fully working product**

Then scale from there (5 projects/week after template established)

---

## Resource Requirements

**Time Investment:**
- Week 1: Foundation + first project (40 hours)
- Weeks 2-4: Rapid scaling (30 hours/week)
- **Total: ~130 hours = ~3 weeks full-time**

**Tools Needed:**
- DigiKey API access (free tier OK)
- Amazon/Etsy APIs (for market research)
- Arduino IDE (for code testing)
- KiCad (for validation testing)

**No Additional Costs:**
- Use existing infrastructure
- Free APIs where available
- Scraping for unavailable data

---

## The Unlock

**Right now:** Professional PCB validation tool (MCP ready)
**After this:** Complete build-to-sell platform

The infrastructure is 80% there. Just needs **DATA**.

Fill the tanks → Rocket launches 🚀
