# 🚀 ElectroCom61 Real Dataset Setup Guide

## Quick Start (5 minutes)

### 1. Download the Real Dataset
```bash
# Visit: https://data.mendeley.com/datasets/6scy6h8sjz/2
# Download the ZIP file and save as:
# datasets/electrocom61_real.zip
```

### 2. Setup Dataset
```bash
./scripts/setup_electrocom61_real.sh
```

### 3. Train Production Model
```bash
./scripts/train_electrocom61_real.sh
```

## What This Gives You

- **61 classes** (vs current 10 synthetic classes)
- **2071+ images** (vs current 200 synthetic images)
- **Real-world data** (vs synthetic test data)
- **Production-ready model** (mAP50 ~0.6-0.8 vs current ~0.1-0.3)

## Expected Performance

| Dataset | Classes | Images | Expected mAP50 |
|---------|---------|--------|----------------|
| Current (Synthetic) | 10 | 200 | 0.1-0.3 |
| Real ElectroCom61 | 61 | 2071 | 0.6-0.8 |

## Manual Setup (if scripts fail)

### 1. Extract Dataset
```bash
mkdir -p datasets/electrocom61_real
unzip datasets/electrocom61_real.zip -d datasets/electrocom61_real
```

### 2. Create data.yaml
```yaml
# datasets/electrocom61_real/data.yaml
path: /home/phyrexian/Downloads/llm_automation/project_portfolio/Circuit-AI/datasets/electrocom61_real
train: images/train
val: images/val
test: images/test

nc: 61
names:
  - class0
  - class1
  # ... (61 classes total)
```

### 3. Validate Dataset
```bash
source venv/bin/activate
yolo detect val data=datasets/electrocom61_real/data.yaml model=yolov8n.pt
# Should show 61 classes and correct image counts
```

### 4. Train Model
```bash
yolo detect train \
  data=datasets/electrocom61_real/data.yaml \
  model=yolov8m.pt imgsz=640 epochs=150 batch=16 \
  lr0=0.01 lrf=0.1 weight_decay=0.0005 mosaic=0.5 \
  hsv_h=0.015 hsv_s=0.7 hsv_v=0.4 \
  project=pcb_runs name=electrocom61_v2 exist_ok=True
```

### 5. Export Model
```bash
yolo export model=pcb_runs/electrocom61_v2/weights/best.pt format=torchscript
mv pcb_runs/electrocom61_v2/weights/best.torchscript models/pcb/electrocom61_v2.torchscript
```

## Troubleshooting

### YOLO Can't Find Dataset
```bash
# Use absolute paths in data.yaml
path: /home/phyrexian/Downloads/llm_automation/project_portfolio/Circuit-AI/datasets/electrocom61_real
```

### Wrong Number of Classes
```bash
# Check max class ID in labels
find datasets/electrocom61_real/labels -name "*.txt" -exec cat {} \; | awk '{print $1}' | sort -n | tail -1
# Update nc: in data.yaml to max_class_id + 1
```

### Training Fails
```bash
# Check dataset structure
ls -la datasets/electrocom61_real/
# Should have: images/ labels/ data.yaml
```

## Next Steps After Training

1. **Evaluate Model**: `python scripts/evaluate.py --model models/pcb/electrocom61_v2.torchscript`
2. **Deploy to API**: Update `MODEL_VERSION=electrocom61_v2`
3. **Set Thresholds**: Run confidence threshold sweep
4. **Production Deploy**: Canary release at 10% traffic

## Performance Targets

- **mAP50 ≥ 0.6**: Production ready
- **mAP50 ≥ 0.7**: Excellent performance
- **mAP50 ≥ 0.8**: Outstanding performance

The real ElectroCom61 dataset should easily reach mAP50 ≥ 0.6, making it suitable for production deployment.
