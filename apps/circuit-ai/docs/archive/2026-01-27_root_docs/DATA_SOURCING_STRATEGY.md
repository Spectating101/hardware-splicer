# Data Sourcing Strategy for Circuit.AI

## THE PROBLEM
We have a beautiful kitchen (architecture) but only 5 recipes (11 ICs, 1,478 images, 5 fault patterns).

Need:
- 10,000+ PCB images (diverse boards, lighting, angles)
- 100+ IC pinout definitions
- 50+ fault patterns with diagnostics
- Real repair case studies

---

## DATA SOURCES TO EXPLORE

### 1. PCB Image Datasets (Public)

#### Already Have:
- ✅ **ElectroCom61**: 1,478 train, 438 val images
  - Location: `datasets/electrocom61_full/`
  - Components: 61 classes
  - Quality: Good, but limited diversity

#### Can Get (Free/Open):
- [ ] **PCB DSLR Dataset** - GitHub
  - https://github.com/WeiChungChang/pcb_dslr_dataset
  - ~2,000 high-res PCB images
  - Multiple angles per board

- [ ] **Open Images Dataset** - Google
  - Filter for "circuit board", "PCB", "electronics"
  - Potentially 10,000+ images
  - Need manual filtering/annotation

- [ ] **Roboflow Universe PCB Datasets**
  - https://universe.roboflow.com/ (search "PCB" or "circuit board")
  - Pre-annotated datasets
  - Various: PCB defect detection, component detection

- [ ] **Kaggle Datasets**
  - Search: "PCB", "circuit board", "electronics"
  - Examples:
    - "PCB Defect Detection"
    - "Circuit Board Images"

#### Can Scrape (Gray Area - need permission):
- [ ] **iFixit Teardowns**
  - https://www.ifixit.com/Teardown
  - Thousands of high-quality PCB photos
  - Would need to respect their API terms

- [ ] **EEVblog Forum**
  - PCB repair/reverse engineering posts
  - Community might contribute if asked

- [ ] **Reddit**: r/AskElectronics, r/PrintedCircuitBoard
  - User-submitted repair photos
  - Could ask community to contribute

- [ ] **Hackaday Projects**
  - DIY electronics with PCB photos
  - Community-driven, might allow scraping for education

#### Can Generate (Synthetic):
- [ ] **Blender + Procedural PCB Models**
  - Generate 3D PCB models
  - Render from multiple angles/lighting
  - Infinite variations
  - Tools: KiCad → Blender pipeline

---

### 2. Component Pinout Knowledge

#### Manual Entry Needed (but sources exist):
- [ ] **Datasheets (Official)**
  - Texas Instruments, Microchip, Espressif, etc.
  - Extract pinouts programmatically from PDFs
  - Tools: `tabula-py` for PDF table extraction

- [ ] **AllDatasheet.com**
  - Has searchable database
  - Could scrape (check robots.txt)

- [ ] **Octopart API**
  - https://octopart.com/api/home
  - Has component specs, datasheets
  - Free tier available

- [ ] **SnapEDA / Ultra Librarian**
  - Component symbols/footprints
  - Includes pin information
  - May have bulk export

#### Crowdsource Strategy:
- [ ] **Build web form**: "Add a component"
  - Users submit IC pinouts
  - Community validation
  - Gamification (leaderboard)

---

### 3. Fault Pattern Knowledge

#### Expert Knowledge Sources:
- [ ] **EEVblog Forum Posts**
  - Search for repair threads
  - Extract: symptoms → diagnosis → fix
  - Tools: web scraper + LLM to structure

- [ ] **Electronics Stack Exchange**
  - https://electronics.stackexchange.com/
  - Questions tagged: "repair", "debugging", "troubleshooting"
  - Extract Q&A patterns

- [ ] **Reddit r/AskElectronics**
  - "My X broke, how do I fix it?" posts
  - Top answers are expert knowledge

- [ ] **Instructables / Hackaday Repair Guides**
  - Step-by-step repair tutorials
  - Can structure into our fault database format

#### Books (Manual Extraction):
- [ ] **"Troubleshooting and Repairing Electronic Circuits"**
  - Classic repair book
  - Contains fault trees
  - Manual entry required

- [ ] **"The Art of Electronics"**
  - Chapter on debugging
  - Common failure modes

---

### 4. Real Repair Case Studies

#### Collect From Users:
- [ ] **Beta Program**
  - Recruit 10-20 electronics hobbyists
  - They submit: broken board photos + symptoms
  - We guide repair, collect data

- [ ] **Partner with Repair Shops**
  - Offer free tool in exchange for anonymized data
  - Photos + repair notes
  - Build real-world dataset

- [ ] **YouTube Repair Videos**
  - Louis Rossmann, NorthridgeFix, etc.
  - Transcribe diagnosis process
  - Extract fault patterns

---

## ACTIONABLE PLAN (Priority Order)

### Phase 1: Quick Wins (1-2 weeks)
1. **Download public datasets**
   - [ ] PCB DSLR Dataset
   - [ ] Roboflow Universe (top 3 PCB datasets)
   - [ ] Kaggle (2-3 relevant datasets)
   - **Goal**: Get to 5,000+ images

2. **Build IC scraper**
   - [ ] Script to extract pinouts from common datasheets
   - [ ] Start with top 20 most common ICs (Arduino, Raspberry Pi, ESP)
   - **Goal**: 50 ICs in database

3. **Scrape repair forums**
   - [ ] Electronics StackExchange Q&A (top 100 repair questions)
   - [ ] Structure into fault database format
   - **Goal**: 20 fault patterns

### Phase 2: Medium Effort (2-4 weeks)
4. **Community contribution**
   - [ ] Build web form for IC submissions
   - [ ] Post on r/AskElectronics, EEVblog asking for contributions
   - [ ] Offer free API access in return

5. **Synthetic data generation**
   - [ ] KiCad → Blender pipeline
   - [ ] Generate 1,000 synthetic PCB renders
   - [ ] Various lighting/angles

6. **YouTube scraping**
   - [ ] Transcribe top 50 PCB repair videos
   - [ ] Extract: symptoms, tests performed, diagnosis, fix
   - [ ] Add to fault database

### Phase 3: Long-term (Ongoing)
7. **Beta program**
   - [ ] Recruit 20 beta testers
   - [ ] Collect real repair data
   - [ ] Iterate on accuracy

8. **Automated datasheet parsing**
   - [ ] PDF → structured pinout data
   - [ ] Process 1000+ datasheets automatically

9. **Continuous learning**
   - [ ] System learns from user interactions
   - [ ] When user corrects chatbot, save correction
   - [ ] Improve over time

---

## IMMEDIATE FIRST STEPS (Start Right Now)

### Step 1: Download Public Datasets (30 minutes)
```bash
# Roboflow
# Go to: https://universe.roboflow.com/
# Search: "PCB component detection"
# Download top 3 datasets (YOLO format)

# Kaggle
pip install kaggle
kaggle datasets download -d <pcb-dataset-name>
```

### Step 2: Build Simple Datasheet Scraper (2 hours)
```python
# Extract pin tables from PDF datasheets
import tabula
import pandas as pd

def extract_pinout_from_pdf(pdf_path):
    # Find pin table
    tables = tabula.read_pdf(pdf_path, pages='all')
    # Parse pin number, name, description
    # Return structured data
```

### Step 3: Scrape Stack Exchange (1 hour)
```python
# Get repair questions with Stack Exchange API
import requests

def get_repair_questions():
    url = "https://api.stackexchange.com/2.3/questions"
    params = {
        "order": "desc",
        "sort": "votes",
        "tagged": "repair;troubleshooting",
        "site": "electronics"
    }
    # Extract Q&A, structure into fault patterns
```

---

## TOOLS WE NEED TO BUILD

### 1. Dataset Aggregator
- Script to download from multiple sources
- Auto-convert to YOLO format
- Deduplicate images
- Quality filtering

### 2. Datasheet Parser
- PDF → JSON converter
- Extract pin tables, electrical specs
- Auto-populate database

### 3. Community Contribution Portal
- Web form: "Submit a component"
- Validation workflow
- Leaderboard/gamification

### 4. Knowledge Extractor
- Scrape forums/Stack Exchange
- LLM to structure into fault patterns
- Human validation step

---

## METRICS TO TRACK

- **Images**: Currently 1,478 → Target 10,000
- **ICs**: Currently 11 → Target 100
- **Faults**: Currently 5 → Target 50
- **Real repairs**: Currently 0 → Target 100

---

## QUESTIONS TO ANSWER

1. **Legal**: What can we legally scrape?
   - Check robots.txt
   - Review API terms
   - Get permission where needed

2. **Quality**: How to ensure good data?
   - Manual validation of first 1,000 images
   - Automated quality checks (blur detection, etc.)
   - Community voting on contributions

3. **Diversity**: What's missing?
   - Different board types (Arduino, Raspberry Pi, custom)
   - Different lighting conditions
   - Different damage types (burned, corroded, etc.)

---

## WHERE IS YOUR RESEARCH?

You mentioned you have deep research already. Let's find it:

Possible locations:
- [ ] `docs/research/`
- [ ] `data/sources.md`
- [ ] `RESEARCH.md` or `DATA_SOURCES.md`
- [ ] Notes app / Google Docs
- [ ] Browser bookmarks (export and search)
- [ ] Old emails to yourself

**Action**: Let's search your entire system for it.

---

## BOTTOM LINE

**We CAN source the data, but it's manual work:**
- 20% can be downloaded (public datasets)
- 30% can be scraped (with permission/care)
- 30% needs manual entry (datasheets, expert knowledge)
- 20% needs community contributions

**Estimated effort**: 2-3 months part-time to get to production-ready dataset.

**But we can START NOW** with quick wins in Phase 1.

Want me to start building the data aggregator/scrapers?
