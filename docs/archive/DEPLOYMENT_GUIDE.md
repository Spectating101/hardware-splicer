# Circuit.AI - Deployment Guide

**Transform e-waste into educational opportunities through AI-powered PCB analysis**

## 🚀 **Quick Deploy Options (GitHub Student Pack Compatible)**

### **1. Railway (Recommended - Free Tier)**
Railway offers a generous free tier perfect for GitHub Student Pack users.

**Deploy Steps:**
1. Fork this repository to your GitHub account
2. Go to [Railway.app](https://railway.app) and sign in with GitHub
3. Click "New Project" → "Deploy from GitHub repo"
4. Select your forked repository
5. Railway will automatically detect the Dockerfile and deploy
6. Your app will be live at `https://your-app-name.railway.app`

**Benefits:**
- ✅ Free tier with 500 hours/month
- ✅ Automatic HTTPS
- ✅ Custom domains
- ✅ Easy environment variable management
- ✅ Automatic deployments from GitHub

### **2. Render (Free Tier)**
Render provides a free tier with automatic deployments.

**Deploy Steps:**
1. Fork this repository to your GitHub account
2. Go to [Render.com](https://render.com) and sign up with GitHub
3. Click "New" → "Web Service"
4. Connect your GitHub repository
5. Configure:
   - **Name:** circuit-ai
   - **Environment:** Python
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn src.api.main:app --host 0.0.0.0 --port $PORT`
6. Click "Create Web Service"

**Benefits:**
- ✅ Free tier available
- ✅ Automatic HTTPS
- ✅ Custom domains
- ✅ Easy scaling

### **3. Streamlit Cloud (Perfect for UI)**
Deploy the Streamlit interface for a beautiful web app.

**Deploy Steps:**
1. Fork this repository to your GitHub account
2. Go to [Streamlit Cloud](https://streamlit.io/cloud) and sign in with GitHub
3. Click "New app"
4. Select your repository
5. Set the path to: `deploy/streamlit/streamlit_app.py`
6. Click "Deploy"

**Benefits:**
- ✅ Completely free
- ✅ Beautiful UI out of the box
- ✅ Automatic HTTPS
- ✅ Easy sharing

### **4. Vercel (Serverless)**
Deploy the API as serverless functions.

**Deploy Steps:**
1. Fork this repository to your GitHub account
2. Go to [Vercel.com](https://vercel.com) and sign in with GitHub
3. Click "New Project"
4. Import your repository
5. Vercel will auto-detect the Python configuration
6. Deploy

**Benefits:**
- ✅ Generous free tier
- ✅ Serverless architecture
- ✅ Global CDN
- ✅ Automatic HTTPS

### **5. Heroku (Classic Option)**
Deploy to Heroku with one-click deployment.

**Deploy Steps:**
1. Fork this repository to your GitHub account
2. Click the button below to deploy to Heroku:

[![Deploy to Heroku](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy?template=https://github.com/yourusername/circuit-ai)

**Benefits:**
- ✅ Free tier (with sleep)
- ✅ Easy deployment
- ✅ Add-ons ecosystem

## 🐳 **Docker Deployment**

### **Local Docker**
```bash
# Build and run with Docker Compose
docker-compose up --build

# Access the app at:
# API: http://localhost:8000
# UI: http://localhost:7860
```

### **Cloud Docker Platforms**
- **Google Cloud Run** (Free tier available)
- **AWS ECS** (Free tier available)
- **Azure Container Instances** (Free tier available)

## 🔧 **Environment Configuration**

### **Required Environment Variables**
```bash
# Core settings
LLM_ENABLED=false
DEBUG=false
HOST=0.0.0.0
PORT=8000

# Database
DATABASE_URL=sqlite:///./data/circuit_ai.db

# Optional: LLM API Keys (if enabling LLM)
COHERE_API_KEY=your_cohere_key
MISTRAL_API_KEY=your_mistral_key
OPENAI_API_KEY=your_openai_key
```

### **GitHub Student Pack Services**
With your GitHub Student Pack, you get access to:
- **Railway:** $5/month credit
- **Render:** Free tier
- **Heroku:** Free tier
- **Vercel:** Pro plan
- **Streamlit Cloud:** Free tier

## 📊 **Deployment Comparison**

| Platform | Free Tier | Ease | Performance | Features |
|----------|-----------|------|-------------|----------|
| **Railway** | ✅ 500h/month | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | Auto-deploy, HTTPS, Custom domains |
| **Render** | ✅ Available | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | Auto-deploy, HTTPS, Easy scaling |
| **Streamlit Cloud** | ✅ Unlimited | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | Beautiful UI, Easy sharing |
| **Vercel** | ✅ Generous | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Serverless, Global CDN |
| **Heroku** | ⚠️ Sleep mode | ⭐⭐⭐ | ⭐⭐⭐ | Classic, Add-ons |

## 🎯 **Recommended Deployment Strategy**

### **For Maximum Impact:**
1. **Deploy API to Railway** (free tier, reliable)
2. **Deploy UI to Streamlit Cloud** (beautiful interface, free)
3. **Use Railway's custom domain** for professional appearance

### **For Development:**
1. **Use Render** for easy development and testing
2. **Streamlit Cloud** for quick UI iterations

### **For Production:**
1. **Railway** for API (scalable, reliable)
2. **Vercel** for frontend (fast, global)
3. **Custom domain** for branding

## 🚀 **Quick Start Commands**

### **Railway Deployment**
```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and deploy
railway login
railway init
railway up
```

### **Render Deployment**
```bash
# Just push to GitHub and connect to Render
git push origin main
# Then configure in Render dashboard
```

### **Streamlit Cloud**
```bash
# Just push to GitHub and connect to Streamlit Cloud
git push origin main
# Then configure in Streamlit Cloud dashboard
```

## 🔍 **Post-Deployment Checklist**

- [ ] **Health Check:** Visit `/health` endpoint
- [ ] **API Docs:** Visit `/docs` for Swagger UI
- [ ] **Test Upload:** Upload a PCB image
- [ ] **Check Database:** Verify data persistence
- [ ] **Monitor Logs:** Check for errors
- [ ] **Performance:** Test response times
- [ ] **Mobile:** Test on mobile devices

## 🎉 **Your Circuit.AI is Live!**

Once deployed, your Circuit.AI platform will be accessible to users worldwide, helping them:
- **Analyze PCB components** with AI
- **Discover educational projects** for salvaged parts
- **Learn electronics** through hands-on experience
- **Reduce e-waste** through creative reuse

**Share your deployment URL and start transforming e-waste into educational opportunities!**

---

*Circuit.AI - Transforming e-waste into educational opportunities through AI* 🔌
