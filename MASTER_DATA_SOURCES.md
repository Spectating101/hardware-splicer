# Master Data Sources for Circuit.AI Knowledge Base

## Source: ChatGPT Deep Research (Comprehensive)

This document consolidates the complete research on data sources for building Circuit.AI's knowledge base.

---

## 1. TECHNICAL MANUALS & DOCUMENTATION (Top Priority)

### Free/Open Manual Libraries
- **ManualsLib** - 1.6M+ product manuals, no signup required
  - URL: https://www.manualslib.com/
  - Status: ✅ Can scrape
  - Gain: 1M+ manuals

- **eServiceInfo (eSI)** - Service manuals & schematics
  - URL: https://www.eserviceinfo.com/
  - Note: Some watermarking
  - Status: ✅ Can scrape

- **KO4BB Manuals** - Test equipment & electronics
  - URL: http://www.ko4bb.com/
  - Focus: Oscilloscopes, multimeters
  - Status: ✅ Can scrape

- **BAMA** - Boat Anchor Manual Archive (vintage radio/electronics)
  - URL: http://bama.edebris.com/
  - Status: ✅ Can scrape

- **Schematics Unlimited** - Free schematics & service manuals
  - URL: http://www.schematicsunlimited.com/
  - Status: ✅ Can scrape

- **OpWeb** - User & service manuals (TV, audio, lab instruments)
  - URL: http://www.opweb.net/
  - Status: ✅ Can scrape

- **CNCManual.com** - CNC machine manuals
  - URL: https://www.cncmanual.com/
  - Status: ✅ Can scrape

- **Archive.org** - Massive archive of manuals
  - ATECORP instrumentation manuals
  - "Free Service Manuals" collections
  - Status: ✅ Can scrape (public domain)

---

## 2. MANUFACTURER DOCUMENTATION (High Quality)

### Major Manufacturers
- **Rockwell Automation Literature Library**
  - URL: https://literature.rockwellautomation.com/
  - Content: PLCs, drives, sensors (Allen-Bradley)
  - Status: ✅ Can scrape (public facing)

- **Siemens Industry Online Support**
  - URL: https://support.industry.siemens.com/
  - Content: SIMATIC PLCs, SINAMICS drives, HMI panels
  - Status: ✅ Can scrape (public facing)

- **Haas Automation** - CNC manuals
  - URL: https://www.haascnc.com/service/manuals-and-documentation.html
  - Status: ✅ Can scrape

- **Fanuc** - Controller parameter manuals
  - Status: Check website for public docs

- **ABB Robotics** - Robot manuals
  - Status: Check website

- **Norman Machine Tool PDF Library**
  - URL: https://www.normanmachinetool.com/
  - Content: Shears, lathes, press brakes
  - Status: ✅ Can scrape

---

## 3. COMMUNITY Q&A (Real-World Knowledge)

### Stack Exchange Network
- **Stack Exchange Data Dump** (CC-BY-SA licensed)
  - URL: https://archive.org/details/stackexchange
  - Sites: Electrical Engineering, Engineering, DIY
  - Format: Structured XML
  - Status: ✅ Can download legally
  - Gain: Millions of Q&A pairs

### Reddit (Historical Archive)
- **Pushshift Reddit Dataset** (2005-2022)
  - URL: https://arxiv.org/abs/2001.08435
  - Size: ~2TB compressed
  - Subreddits: r/AskEngineers, r/electrical, r/PLC, r/MechanicalEngineering
  - Status: ✅ Can download (historical dump)
  - Gain: Billions of comments

### Specialist Forums (Scrape Required)
- **EEVBlog Forums** - Electronics repair
  - URL: https://www.eevblog.com/forum/
  - Status: ⚠️ Scrape carefully (rate limit)

- **PLCtalk / PLCs.net** - PLC programming & troubleshooting
  - Status: ⚠️ Scrape carefully

- **Practical Machinist** - Machine tool usage & repair
  - Status: ⚠️ Scrape carefully

- **Usenet Archives** (sci.electronics.repair, etc.)
  - Decades of discussions
  - Status: Check Google Groups archives

---

## 4. PATENTS & TECHNICAL RESEARCH

### Patents (Public Domain)
- **Google Patents** - 120M+ patent documents
  - URL: https://patents.google.com/
  - Bulk data: Patent Public Datasets
  - Status: ✅ Can scrape (public domain)
  - Gain: Technical diagrams, explanations, mechanisms

- **USPTO Bulk Downloads**
  - URL: https://bulkdata.uspto.gov/
  - Status: ✅ Can download

### Government Technical Reports
- **NASA Technical Reports Server (NTRS)**
  - URL: https://ntrs.nasa.gov/
  - Content: 500K+ full-text technical documents
  - Status: ✅ Public domain

- **Defense Technical Information Center (DTIC)**
  - Content: Military technical reports (older = public domain)
  - Status: Check for public docs

### Academic Papers
- **ArXiv** - Engineering & CS papers
  - URL: https://arxiv.org/
  - Topics: Predictive maintenance, fault diagnosis
  - Status: ✅ Can scrape (open access)

---

## 5. STANDARDS & SAFETY GUIDELINES

### Safety & Compliance
- **OSHA Technical Manual (OTM)**
  - URL: https://www.osha.gov/otm
  - Content: Workplace hazards, safety procedures
  - Status: ✅ Public domain

- **NIST Publications**
  - URL: https://www.nist.gov/publications
  - Content: Manufacturing best practices
  - Status: ✅ Public domain

### Standards (Summaries/Older Versions)
- ISO/IEC standards (some public summaries)
- National Electrical Code (NEC) - older versions
- IEC standards (check for open versions)

### Vendor Application Notes
- Schneider Electric, Fluke, etc. publish free whitepapers
- Status: ✅ Can scrape from resource centers

---

## 6. MULTIMODAL DATA (Diagrams & Schematics)

### Diagram Datasets
- **AI2D Dataset** - 4,817 annotated diagrams
  - URL: https://allenai.org/data/diagrams
  - Status: ✅ Open dataset

- **Schematics from Patents**
  - 120M+ patent figures available via Google Patents
  - Status: ✅ Public domain

- **Circuit Schematics**
  - Schematics Unlimited
  - All About Circuits forum
  - EEVblog shared schematics

### CAD Models & Exploded Views
- **AssemblyNet** - 3D CAD assemblies
  - Research dataset for mechanical assemblies
  - Render to 2D for training

---

## 7. LARGE-SCALE TEXT CORPORA

### Pre-training Bases
- **The Pile** (EleutherAI) - 886GB open-source dataset
  - URL: https://pile.eleuther.ai/
  - Contains: Stack Exchange (~35GB), ArXiv (~60GB), USPTO patents (~24GB)
  - Status: ✅ Can download

- **Common Crawl / C4**
  - Filtered web crawl
  - Filter for technical keywords
  - Status: ✅ Can download

### Domain-Specific Crawls
- Industrial tech blogs
- Equipment vendor knowledge bases
- Control Engineering magazine
- IEEE Spectrum articles
- SME (Society of Manufacturing Engineers)

---

## IMPLEMENTATION PRIORITY

### PHASE 1: Quick Wins (1-2 weeks)
1. **Stack Exchange Data Dump** → 100K+ Q&A pairs
2. **Archive.org Manuals** → 10K+ manuals
3. **ManualsLib scraper** → 50K+ manuals

**Estimated gain**: 5,000+ PCB images, 20+ fault patterns

### PHASE 2: High-Value Sources (1 month)
1. **Rockwell/Siemens documentation** → Official manuals
2. **Google Patents bulk** → Technical diagrams
3. **NASA NTRS** → Technical reports

**Estimated gain**: +100K technical documents

### PHASE 3: Community Knowledge (Ongoing)
1. **EEVBlog forum scraper**
2. **Reddit Pushshift analysis** (filter relevant subreddits)
3. **Usenet archives**

**Estimated gain**: +1M forum posts/comments

---

## LEGAL CONSIDERATIONS

### ✅ Safe to Use (Public Domain/Open)
- Stack Exchange dumps (CC-BY-SA)
- Patents (public domain)
- Government reports (NASA, OSHA, NIST)
- Archive.org public domain collections
- The Pile dataset (open source)

### ⚠️ Gray Area (Proceed Carefully)
- Forum scraping (check TOS, rate limit)
- Manufacturer documentation (publicly available but may have restrictions)
- ManualsLib (publicly accessible but copyrighted content)

### ❌ Risky (Avoid or Get Permission)
- Paywalled standards (ISO, IEC) - use only summaries/older versions
- Service manuals marked "dealer only"
- Content behind authentication

---

## RECOMMENDED TOOLS TO BUILD

### 1. Multi-Source Aggregator
```python
# Download from multiple sources
# - Stack Exchange dumps
# - Archive.org collections
# - Patent bulk data
# - The Pile subsets
```

### 2. Forum Scraper
```python
# Scrape with respect:
# - Rate limiting
# - robots.txt
# - User-Agent headers
# - Save to structured format
```

### 3. PDF Processor
```python
# Extract from PDFs:
# - Text (OCR if needed)
# - Tables (pinouts)
# - Diagrams/images
# - Metadata
```

### 4. Quality Filter
```python
# Filter for:
# - Technical relevance
# - Language quality
# - Deduplication
# - Image quality
```

---

## METRICS

### Current Status
- PCB Images: 1,478
- IC Pinouts: 11
- Fault Patterns: 5
- Real Repairs: 0

### Target After Phase 1-3
- PCB Images: 10,000+
- IC Pinouts: 100+
- Fault Patterns: 50+
- Manuals: 100,000+
- Q&A Pairs: 1,000,000+

---

## NEXT ACTIONS

1. **Start with legal/safe sources first:**
   - Download Stack Exchange dump
   - Access Archive.org collections
   - Get NASA NTRS reports

2. **Build scrapers for public sites:**
   - ManualsLib
   - Rockwell/Siemens docs
   - Google Patents

3. **Process The Pile:**
   - Extract technical subsets
   - Filter for electronics/manufacturing

4. **Launch community program:**
   - Invite contributors
   - Gamify submissions
   - Validate quality
