# Circuit.AI Model Training Guide

## 🚀 Quick Start (30 minutes to working model)

### 1. Setup Environment
```bash
# Activate virtual environment
source venv/bin/activate

# Install training dependencies (already done)
pip install ultralytics==8.3.0 opencv-python pycocotools shapely
```

### 2. Run Quick Start Training
```bash
# This will create a minimal test dataset and train a basic model
./scripts/quick_start_training.sh
```

**What this does:**
- Creates minimal test dataset (1 image, 1 label)
- Trains YOLOv8m on ElectroCom61 format
- Exports model to ONNX for production
- Tests model loading

**Expected output:**
- Model: `models/pcb/electrocom61_v1.onnx`
- Training logs: `pcb_runs/electrocom61_v1/`

---

## 📊 Phase 1: ElectroCom61 (Day 1-2)

### Dataset Setup
```bash
# Download ElectroCom61 dataset (you'll need to source this)
# Place in: datasets/electrocom61/
# Structure:
datasets/electrocom61/
├── data.yaml
├── images/
│   ├── train/
│   ├── val/
│   └── test/
└── labels/
    ├── train/
    ├── val/
    └── test/
```

### Training Command
```bash
python scripts/train_model.py \
    --dataset electrocom61 \
    --data-yaml datasets/electrocom61/data.yaml \
    --project pcb_runs \
    --name electrocom61_v1 \
    --epochs 100 \
    --batch 16 \
    --imgsz 640 \
    --export \
    --export-format onnx
```

### Expected Results
- **mAP50**: ≥ 0.7
- **Training time**: 2-4 hours (GPU), 8-12 hours (CPU)
- **Model size**: ~50MB (ONNX)

---

## 🔄 Phase 2: FPIC Dataset (Day 3-4)

### Dataset Conversion
```bash
# Convert FPIC annotations to YOLO format
python scripts/convert_fpic_to_yolo.py \
    --ann-dir datasets/fpic_raw/annotations \
    --img-dir datasets/fpic_raw/images \
    --out-dir datasets/fpic_yolo \
    --train-ratio 0.8 \
    --val-ratio 0.1
```

### Training FPIC Model
```bash
python scripts/train_model.py \
    --dataset fpic \
    --data-yaml datasets/fpic_yolo/data.yaml \
    --project pcb_runs \
    --name fpic_v1 \
    --epochs 100 \
    --batch 8 \
    --imgsz 768 \
    --export \
    --export-format onnx
```

### Expected Results
- **mAP50**: ≥ 0.65
- **Training time**: 4-6 hours (GPU), 12-16 hours (CPU)
- **Model size**: ~50MB (ONNX)

---

## 🔍 Phase 3: DeepPCB Defects (Day 5)

### Dataset Preparation
```bash
# Prepare DeepPCB defect annotations
# (You'll need to create YOLO labels from their format)
```

### Training Defect Model
```bash
python scripts/train_model.py \
    --dataset deeppcb \
    --data-yaml datasets/deeppcb/data.yaml \
    --project pcb_runs \
    --name deeppcb_v1 \
    --epochs 80 \
    --batch 16 \
    --imgsz 640 \
    --export \
    --export-format onnx
```

### Expected Results
- **mAP50**: ≥ 0.6
- **Classes**: 6 defect types
- **Model size**: ~50MB (ONNX)

---

## 🧪 Phase 4: Validation & Testing

### Model Validation
```bash
# Test all models
python -c "
from src.vision.loader import get_detector, get_available_models
print('Available models:', get_available_models())

for model_name in ['electrocom61_v1', 'fpic_v1', 'deeppcb_v1']:
    model = get_detector(model_name)
    if model:
        print(f'✅ {model_name}: Loaded successfully')
    else:
        print(f'❌ {model_name}: Failed to load')
"
```

### API Testing
```bash
# Start the API server
uvicorn src.api.main:app --reload

# Test YOLO endpoint
curl -X POST "http://localhost:8000/v1/analyze-yolo" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F "file=@test_pcb.jpg" \
  -F "model_name=electrocom61_v1" \
  -F "confidence=0.25"
```

### Performance Testing
```bash
# Test inference speed
python -c "
import time
import numpy as np
from src.vision.loader import get_detector, preprocess_image

model = get_detector('electrocom61_v1')
if model:
    # Create test image
    test_img = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)
    
    # Warm up
    for _ in range(5):
        model(test_img)
    
    # Benchmark
    times = []
    for _ in range(20):
        start = time.time()
        model(test_img)
        times.append(time.time() - start)
    
    print(f'Average inference time: {np.mean(times):.3f}s')
    print(f'Min: {np.min(times):.3f}s, Max: {np.max(times):.3f}s')
"
```

---

## 📈 Phase 5: Production Deployment

### Model Selection
```bash
# Compare models and select best performer
python scripts/compare_models.py \
    --models electrocom61_v1,fpic_v1 \
    --test-dir test_images/ \
    --output results/comparison.json
```

### Production Configuration
```bash
# Set default model in environment
export DEFAULT_MODEL=electrocom61_v1
export MODEL_CONFIDENCE=0.25
export MODEL_BATCH_SIZE=1
```

### Deployment
```bash
# Deploy with Docker
docker build -f Dockerfile.prod -t circuit-ai-backend .
docker run -p 8000:8000 \
  -e DEFAULT_MODEL=electrocom61_v1 \
  -v $(pwd)/models:/app/models \
  circuit-ai-backend
```

---

## 🛠️ Troubleshooting

### Common Issues

#### 1. CUDA Out of Memory
```bash
# Reduce batch size
python scripts/train_model.py --batch 4

# Or use CPU training
export CUDA_VISIBLE_DEVICES=""
python scripts/train_model.py
```

#### 2. Dataset Not Found
```bash
# Check dataset structure
ls -la datasets/electrocom61/
cat datasets/electrocom61/data.yaml
```

#### 3. Model Loading Failed
```bash
# Check model file exists
ls -la models/pcb/
file models/pcb/electrocom61_v1.onnx

# Test model loading
python -c "from ultralytics import YOLO; YOLO('models/pcb/electrocom61_v1.onnx')"
```

#### 4. Poor Model Performance
```bash
# Check dataset quality
python scripts/analyze_dataset.py --data-yaml datasets/electrocom61/data.yaml

# Increase training epochs
python scripts/train_model.py --epochs 200

# Adjust learning rate
python scripts/train_model.py --lr0 0.001
```

### Performance Optimization

#### 1. Model Quantization
```bash
# Quantize ONNX model for faster inference
python scripts/quantize_model.py \
    --input models/pcb/electrocom61_v1.onnx \
    --output models/pcb/electrocom61_v1_quantized.onnx
```

#### 2. Batch Processing
```bash
# Enable batch processing for multiple images
python scripts/batch_inference.py \
    --model electrocom61_v1 \
    --input-dir test_images/ \
    --output-dir results/
```

#### 3. GPU Acceleration
```bash
# Use GPU for inference
export CUDA_VISIBLE_DEVICES=0
python -c "from ultralytics import YOLO; YOLO('models/pcb/electrocom61_v1.onnx')"
```

---

## 📊 Monitoring & Metrics

### Training Metrics
- **mAP50**: Mean Average Precision at IoU 0.5
- **mAP50-95**: Mean Average Precision at IoU 0.5-0.95
- **Precision**: True Positives / (True Positives + False Positives)
- **Recall**: True Positives / (True Positives + False Negatives)

### Production Metrics
- **Inference Time**: < 300ms per image
- **Memory Usage**: < 1GB RAM
- **Model Size**: < 100MB
- **Accuracy**: > 70% mAP50

### Monitoring Commands
```bash
# Check model performance
python scripts/evaluate_model.py \
    --model electrocom61_v1 \
    --test-dir test_images/ \
    --output results/evaluation.json

# Monitor API performance
curl -X GET "http://localhost:8000/v1/metrics" | grep circuit_ai
```

---

## 🎯 Success Criteria

### Phase 1 (ElectroCom61)
- [ ] Model trains successfully
- [ ] mAP50 ≥ 0.7
- [ ] Inference time < 300ms
- [ ] API endpoint working

### Phase 2 (FPIC)
- [ ] Dataset conversion successful
- [ ] Model trains successfully
- [ ] mAP50 ≥ 0.65
- [ ] Better than ElectroCom61 on test set

### Phase 3 (DeepPCB)
- [ ] Defect detection working
- [ ] 6 defect classes detected
- [ ] mAP50 ≥ 0.6

### Phase 4 (Production)
- [ ] All models deployed
- [ ] API performance optimized
- [ ] Monitoring in place
- [ ] Documentation complete

---

## 📚 Additional Resources

### Datasets
- **ElectroCom61**: 61-class PCB component dataset
- **FPIC**: FPCB Image Classification dataset
- **DeepPCB**: PCB defect detection dataset

### Tools
- **Ultralytics YOLO**: Model training and inference
- **OpenCV**: Image processing
- **ONNX**: Model optimization and deployment

### Documentation
- [YOLO Documentation](https://docs.ultralytics.com/)
- [ONNX Runtime](https://onnxruntime.ai/)
- [OpenCV Python](https://opencv-python-tutroals.readthedocs.io/)

---

**Ready to start? Run `./scripts/quick_start_training.sh` to begin!**

