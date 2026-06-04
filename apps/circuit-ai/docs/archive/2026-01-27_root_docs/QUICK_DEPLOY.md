# Quick Deployment Guide

## After Training Completes

### 1. Deploy Trained Model
```bash
source venv/bin/activate
python scripts/deploy_model.py
```

This will:
- Copy trained model to `models/pcb/production_model.pt`
- Backup existing model
- Validate deployment

### 2. Add LLM API Key (When Ready)
Edit `.env`:
```bash
LLM_ENABLED=true
GROQ_API_KEY=your_key_here  # or COHERE_API_KEY
```

### 3. Test Full System
```bash
python scripts/test_full_pipeline.py
```

Should show:
- ✅ Database connection
- ✅ Production model loaded
- ✅ Detection working
- ✅ Full pipeline (if LLM configured)

### 4. Start Backend
```bash
python scripts/start_enhanced_system.py
```

Backend will run on: http://localhost:8000

### 5. Start Frontend
```bash
cd circuit-ai-frontend
npm run dev
```

Frontend will run on: http://localhost:3000

### 6. Test with Real Image

Upload a PCB image at: http://localhost:3000/analyze

---

## Production Deployment (Railway/Render)

### Railway
```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Deploy
railway up
```

### Render
1. Push to GitHub
2. Connect repo at render.com
3. Set environment variables
4. Deploy

---

## Troubleshooting

**Model not detecting:**
- Check model is deployed: `ls -lh models/pcb/production_model.pt`
- Verify classes match dataset: 61 classes expected

**LLM not working:**
- Verify API key in .env: `cat .env | grep LLM`
- Check LLM_ENABLED=true

**Database empty:**
- Re-run: `python scripts/populate_component_db.py`
- Verify: `sqlite3 data/circuit_ai.db "SELECT COUNT(*) FROM components;"`

---

## What You've Built

✅ **Trained model** - 61 PCB component classes
✅ **Component database** - 61 components with descriptions
✅ **Full API** - FastAPI backend with auth/billing/metrics
✅ **Modern frontend** - Next.js with real-time updates
✅ **Deployment ready** - Docker + cloud configs

**Missing only:** LLM API key for educational content generation

---

## Next Steps

1. Get Groq API key (2 min): https://console.groq.com
2. Test with real PCB images
3. Create demo video/gif
4. Deploy to Railway/Render for live demo
5. Add to portfolio
