# Knowledge Base Building Guide

## Current Status

- **PCB Images**: 2888/10000 (28.9%)
- **IC Pinouts**: 11/100 (11.0%)
- **Fault Patterns**: 5/50 (10.0%)
- **Real Repairs**: 0/100
- **Overall**: 8.9%

## Quick Start

### 1. Download Public Datasets (2-4 hours)
```bash
python scripts/data_collection/download_public_datasets.py
```

This will guide you through downloading:
- Roboflow Universe PCB datasets
- GitHub PCB repos
- Kaggle datasets
- Open Images subset

**Expected gain**: +3,000-5,000 images

### 2. Extract IC Pinouts (1 week)
```bash
# Install dependencies
pip install tabula-py PyPDF2

# Run extractor
python scripts/data_collection/scrape_datasheets.py
```

Download datasheets for top 50 ICs, then extract automatically.

**Expected gain**: +40-50 IC pinouts

### 3. Scrape Fault Patterns (4-6 hours)
```bash
python scripts/data_collection/scrape_electronics_stackexchange.py
```

Extracts repair knowledge from Electronics StackExchange Q&A.

**Expected gain**: +15-20 fault patterns

## Data Sources

### Already Have
- ✅ ElectroCom61: 1,478 images, 61 component classes
- ✅ Real PCB Archive (Cap/MOSFET set): 1,410 images across 9 component classes (`datasets/real_pcb_archive/`)
- ✅ 11 IC pinouts (manual entry)
- ✅ 5 fault patterns (manual entry)

### Can Get (Free)
- [ ] Roboflow Universe: ~3,000-5,000 images
- [ ] GitHub PCB datasets: ~2,000-3,000 images
- [ ] Kaggle: ~1,000-2,000 images
- [ ] Stack Exchange: ~20-30 fault patterns
- [ ] Common IC datasheets: ~50 pinouts

### Need to Build
- [ ] Community contribution portal
- [ ] Beta tester program for real repairs
- [ ] Automated datasheet parser (for 1000+ ICs)

## Timeline

### Week 1: Quick Wins
- Download all public datasets
- Merge into training set
- Scrape Stack Exchange

**Result**: 5,000+ images, 20 fault patterns

### Week 2-4: IC Pinouts
- Download top 50 IC datasheets
- Extract pin tables (manual + automated)
- Add to database

**Result**: 50+ IC pinouts

### Month 2-3: Community & Beta
- Build contribution portal
- Recruit beta testers
- Collect real repair data

**Result**: Ongoing data flow

## Tools Available

1. **download_public_datasets.py**: Aggregates public sources
2. **scrape_datasheets.py**: Extracts pinouts from PDFs
3. **scrape_electronics_stackexchange.py**: Gets repair Q&A

## Next Steps

Run this to see current status and action plan:
```bash
python scripts/build_knowledge_base.py
```
