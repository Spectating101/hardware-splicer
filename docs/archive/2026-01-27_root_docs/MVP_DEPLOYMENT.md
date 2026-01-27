# Circuit.AI - MVP Deployment Guide

**Status**: Ready for MVP Deployment  
**Date**: November 6, 2025  
**Phase**: 1 - MVP Launch with Pre-trained YOLOv8 Model

---

## 🎯 MVP Deployment Overview

This guide covers deploying Circuit.AI as a minimum viable product with:
- ✅ SQLite database (already created)
- ✅ Pre-trained YOLOv8 model (yolov8n.pt included)
- ✅ FastAPI backend with all security fixes
- ✅ Next.js frontend
- ✅ LLM integration for repair guidance

**Estimated Time**: 30 minutes for database init + model loading  
**Infrastructure Required**: CPU (no GPU needed for inference)

---

## 📋 STEP 1: Initialize Database

### 1.1 Check SQLite Installation
```bash
sqlite3 --version
```

### 1.2 Initialize Database with Schema
```bash
cd /home/phyrexian/Downloads/llm_automation/project_portfolio/Circuit-AI

# Create database file and initialize schema
sqlite3 data/circuit_ai.db < db/schema_sqlite.sql

# Verify database was created
sqlite3 data/circuit_ai.db ".tables"
```

**Expected Output:**
```
api_keys  audit_logs  billing_events  components  projects  repair_procedures  
usage_tracking  users  analyses
```

---

## 🔐 STEP 2: Configure Environment Variables

### 2.1 Create .env File
```bash
cp deploy/env.production.example .env
```

### 2.2 Generate Secure Secrets
```bash
# Generate JWT_SECRET
python3 -c "import secrets; print(f'JWT_SECRET={secrets.token_urlsafe(32)}')"

# Generate API key for testing
python3 -c "import secrets; print(f'TEST_API_KEY={secrets.token_urlsafe(32)}')"
```

### 2.3 Update .env with Required Values

Edit `.env` file and set:

```bash
# Database
DATABASE_URL=sqlite:///./data/circuit_ai.db

# Security
JWT_SECRET=<your-generated-secret>
CORS_ORIGINS=http://localhost:3000,http://localhost:8000,http://localhost:8080

# API Keys (Get from respective services)
OPENAI_API_KEY=<optional>
COHERE_API_KEY=<optional>
MISTRAL_API_KEY=<optional>
ANTHROPIC_API_KEY=<optional>
CEREBRAS_API_KEY=<optional>

# LLM Configuration
LLM_PROVIDER=cohere
LLM_MODEL=command-r

# Model Paths
YOLO_MODEL_PATH=models/yolo/yolov8n.pt

# Server Configuration
HOST=0.0.0.0
PORT=8000
DEBUG=False

# Logging
LOG_LEVEL=INFO

# Optional: Test API Keys
TEST_API_KEYS=<generated-test-key-1>,<generated-test-key-2>
```

---

## 📦 STEP 3: Install Python Dependencies

```bash
cd /home/phyrexian/Downloads/llm_automation/project_portfolio/Circuit-AI

# Create virtual environment (optional but recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Optional: Install dev dependencies
pip install -r requirements-dev.txt
```

**Key Dependencies for MVP:**
- FastAPI 0.104.1
- Ultralytics (YOLOv8)
- PyTorch
- Pydantic
- SQLAlchemy

---

## 🚀 STEP 4: Verify Model Loading

### 4.1 Test Model Import
```bash
python3 -c "
from ultralytics import YOLO
import torch

print('Device:', 'cuda' if torch.cuda.is_available() else 'cpu')
print('Loading yolov8n.pt...')
model = YOLO('models/yolov8n.pt')
print('✅ Model loaded successfully')
print('Model classes:', model.names)
"
```

**Expected Output:**
```
Device: cpu
Loading yolov8n.pt...
✅ Model loaded successfully
Model classes: {...}
```

### 4.2 Test on Sample Image (Optional)
```bash
python3 << 'EOF'
from ultralytics import YOLO
from PIL import Image
import os

# Load model
model = YOLO('models/yolov8n.pt')

# Find test image
test_image = 'data/test_images/sample.jpg' if os.path.exists('data/test_images/sample.jpg') else 'data/uploads/test.jpg'

if os.path.exists(test_image):
    results = model(test_image)
    print(f"✅ Inference successful: {len(results[0].boxes)} objects detected")
else:
    print("⚠️ No test image found, skipping inference test")
EOF
```

---

## 🔧 STEP 5: Start Backend API Server

```bash
# From project root directory
cd /home/phyrexian/Downloads/llm_automation/project_portfolio/Circuit-AI

# Option A: Direct execution
python3 -m uvicorn src.api.v1.main:app --host 0.0.0.0 --port 8000 --reload

# Option B: Using poetry (if available)
poetry run uvicorn src.api.v1.main:app --host 0.0.0.0 --port 8000

# Option C: Using docker (if available)
docker build -t circuit-ai-backend .
docker run -p 8000:8000 circuit-ai-backend
```

**Expected Output:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
```

**Access API Documentation:**
- OpenAPI Docs: http://localhost:8000/docs
- ReDoc Docs: http://localhost:8000/redoc

---

## 🎨 STEP 6: Start Frontend Server

In a new terminal:

```bash
cd circuit-ai-frontend

# Install dependencies
npm install

# Start development server
npm run dev

# Or build and serve production
npm run build
npm run start
```

**Expected Output:**
```
> Ready on http://localhost:3000
```

**Access Frontend:**
- URL: http://localhost:3000

---

## ✅ STEP 7: Test MVP Endpoints

### 7.1 Health Check
```bash
curl http://localhost:8000/health
# Expected: {"status": "ok"}
```

### 7.2 Analyze PCB Image via API
```bash
# Upload and analyze image
curl -X POST "http://localhost:8000/v1/analyze" \
  -F "file=@data/test_images/sample_pcb.jpg" \
  -H "Authorization: Bearer <your-test-api-key>"

# Or use YOLO endpoint specifically
curl -X POST "http://localhost:8000/v1/analyze-yolo" \
  -F "file=@data/test_images/sample_pcb.jpg"
```

### 7.3 Get Component Classes
```bash
curl http://localhost:8000/v1/components/classes
```

### 7.4 Test Authentication
```bash
# Create API key
curl -X POST "http://localhost:8000/v1/auth/create-key" \
  -H "Content-Type: application/json" \
  -d '{"name": "test_key", "tier": "free"}'

# Use API key
curl -X POST "http://localhost:8000/v1/analyze" \
  -F "file=@test_image.jpg" \
  -H "X-API-Key: <generated-key>"
```

---

## 📊 STEP 8: Test WebSocket Real-time Analysis

```bash
# Using wscat (install: npm install -g wscat)
wscat -c ws://localhost:8000/v1/ws

# Or using Python
python3 << 'EOF'
import asyncio
import websockets
import json

async def test_websocket():
    uri = "ws://localhost:8000/v1/ws"
    async with websockets.connect(uri) as websocket:
        # Send analysis request
        msg = {"action": "analyze", "image_id": "test"}
        await websocket.send(json.dumps(msg))
        
        # Receive response
        response = await websocket.recv()
        print("Response:", json.loads(response))

asyncio.run(test_websocket())
EOF
```

---

## 🧪 STEP 9: Run Test Suite

```bash
# Run all tests
pytest tests/ -v

# Run specific test module
pytest tests/test_api.py -v

# Run with coverage
pytest --cov=src tests/
```

---

## 📈 STEP 10: Monitor API

### Option A: Watch Logs
```bash
# From another terminal
tail -f logs/api.log
```

### Option B: Use Monitoring Dashboard
```bash
# Access Prometheus metrics (if enabled)
http://localhost:8000/metrics
```

### Option C: Simple Monitoring
```bash
# Check API status regularly
watch -n 5 'curl -s http://localhost:8000/health | jq .'
```

---

## 🚀 MVP Deployment Checklist

- [ ] SQLite database initialized (`sqlite3 data/circuit_ai.db ".tables"`)
- [ ] `.env` file created with all required variables
- [ ] JWT_SECRET generated and set
- [ ] CORS_ORIGINS configured for frontend domain
- [ ] Python dependencies installed
- [ ] Model loads without errors (`test_model_loading.py`)
- [ ] Backend API starts successfully
- [ ] Frontend builds successfully
- [ ] Health check endpoint responds
- [ ] File upload endpoint works
- [ ] Analysis endpoint returns results
- [ ] WebSocket connection established
- [ ] Authentication/API keys working
- [ ] CORS headers correct
- [ ] Tests pass locally

---

## 📊 Next Phase: Model Training (Optional)

For better accuracy, train on ElectroCom61 dataset:

```bash
# Check dataset
python scripts/validate_yolo_dataset.py --dataset datasets/electrocom61_full

# Train model (takes 2-8 hours depending on hardware)
python scripts/production_training_v2.py \
  --dataset datasets/electrocom61_full \
  --model-name electrocom61_v2 \
  --export-format torchscript

# Use trained model
# Update YOLO_MODEL_PATH in .env to: models/pcb/electrocom61_v2.pt
```

---

## 🔍 Troubleshooting

### Issue: "Port 8000 already in use"
```bash
# Find and kill process on port 8000
lsof -i :8000
kill -9 <PID>

# Or use different port
uvicorn src.api.v1.main:app --port 8001
```

### Issue: "CORS error in browser"
```bash
# Verify CORS_ORIGINS in .env includes your frontend URL
# Include http:// and exact port, e.g.:
# CORS_ORIGINS=http://localhost:3000,http://localhost:8000
```

### Issue: "Model not found"
```bash
# Verify model path
ls -lh models/yolov8n.pt
ls -lh models/yolo/

# Download if missing
python3 -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"
```

### Issue: "CUDA out of memory"
```bash
# Use CPU instead
# Set in code: device='cpu'
# Or reduce batch size in training

# Check GPU status
nvidia-smi
```

### Issue: "Database locked"
```bash
# Remove lock file if exists
rm -f data/circuit_ai.db-wal
rm -f data/circuit_ai.db-shm

# Reinitialize
sqlite3 data/circuit_ai.db < db/schema_sqlite.sql
```

---

## 📚 Useful Commands

```bash
# Check all Python packages
pip list | grep -E "torch|ultralytics|fastapi"

# Run backend in debug mode
python -m debugpy --listen 5678 -m uvicorn src.api.v1.main:app

# Profile API performance
python -m cProfile -s cumtime scripts/benchmark_api.py

# Backup database
cp data/circuit_ai.db data/circuit_ai.db.backup

# Reset database
rm data/circuit_ai.db
sqlite3 data/circuit_ai.db < db/schema_sqlite.sql
```

---

## 🎉 Success Criteria for MVP

✅ **Database**: SQLite initialized, tables created, can connect  
✅ **Backend**: API running, endpoints responding, CORS configured  
✅ **Frontend**: Next.js app running, can communicate with backend  
✅ **Model**: YOLOv8 loads, can run inference on test images  
✅ **Auth**: API keys work, JWT tokens valid  
✅ **LLM**: At least one LLM provider configured for repair guidance  
✅ **Files**: File upload/download working, validation in place  
✅ **Tests**: Core tests passing  

---

## 📞 Post-Deployment

After MVP deployment:

1. **Monitor**: Watch logs for errors during first 24 hours
2. **Collect Feedback**: Get user feedback on UI/UX
3. **Train Custom Model**: Once you have enough real PCB images
4. **Scale**: Add more inference servers if needed
5. **Upgrade**: Implement Phase 2-3 improvements (error handling, monitoring, etc.)

---

## 📖 Documentation

- API Reference: http://localhost:8000/docs
- Frontend README: `circuit-ai-frontend/README.md`
- Architecture: `docs/ARCHITECTURE.md`
- Database Schema: `db/schema_sqlite.sql`

---

**Ready to deploy? Start with STEP 1 above!**
