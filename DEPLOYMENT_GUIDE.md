# Circuit-AI Deployment Guide

**Quick Start:** Deploy to Railway in 5 minutes. Zero configuration needed.

---

## Option 1: Railway Deployment (RECOMMENDED)

**Why Railway:**
- $5 free credit/month (covers ~500 hours)
- Zero configuration deployment
- Automatic HTTPS
- Git integration
- Free tier perfect for MVP

### Step-by-Step Deployment:

#### 1. Install Railway CLI
```bash
# macOS/Linux
curl -fsSL https://railway.app/install.sh | sh

# Or use npm
npm i -g @railway/cli
```

#### 2. Login to Railway
```bash
railway login
```

#### 3. Deploy Circuit-AI
```bash
cd /path/to/Circuit-AI
railway init
# Select: "Create a new project"
# Enter project name: circuit-ai

railway up
# Railway will detect Python, install dependencies, and deploy
```

#### 4. Set Environment Variables (Optional)
```bash
# Production mode
railway variables set DEBUG=False
railway variables set FLASK_ENV=production

# Add LLM keys if needed (for enhanced features)
railway variables set CEREBRAS_API_KEY=your_key_here
railway variables set OPENAI_API_KEY=your_key_here

# Add pricing service keys (optional)
railway variables set DIGIKEY_API_KEY=your_key_here
```

#### 5. Get Your URL
```bash
railway domain
# Example output: circuit-ai-production.up.railway.app
```

**Done!** Your API is live at `https://your-subdomain.up.railway.app`

---

## Option 2: Heroku Deployment

**Cost:** $7/month (with GitHub Student Pack, first app free)

### Deployment Steps:

```bash
# 1. Create Heroku app
heroku create circuit-ai-production

# 2. Set config
heroku config:set DEBUG=False
heroku config:set FLASK_ENV=production

# 3. Deploy
git push heroku master

# 4. Open
heroku open
```

---

## Option 3: Vercel (Frontend Only)

If you want to deploy just the landing page separately:

```bash
# 1. Install Vercel CLI
npm i -g vercel

# 2. Deploy static site
cd static
vercel --prod

# Note: API server needs separate deployment (Railway/Heroku)
```

---

## Environment Variables Reference

### Required (None!)
Circuit-AI works out of the box with zero configuration.

### Optional (Enhanced Features):

| Variable | Purpose | Default |
|----------|---------|---------|
| `PORT` | Server port | `5000` |
| `DEBUG` | Debug mode | `True` (dev), `False` (prod) |
| `FLASK_ENV` | Environment | `development` |
| `CEREBRAS_API_KEY` | LLM for code generation | Falls back to local |
| `OPENAI_API_KEY` | Alternative LLM | Falls back to local |
| `DIGIKEY_API_KEY` | Real-time pricing | Falls back to estimates |
| `STRIPE_SECRET_KEY` | Payment processing | Not required for free tier |
| `REDIS_URL` | Caching | Uses in-memory cache |
| `DATABASE_URL` | Persistence | SQLite (local file) |

---

## Post-Deployment Checklist

### 1. Test Core Endpoints

```bash
# Health check
curl https://your-url.railway.app/api/health

# Component list
curl https://your-url.railway.app/api/components

# Quick validation test
curl -X POST https://your-url.railway.app/api/validate \
  -H "Content-Type: application/json" \
  -d '{"components": [{"type": "LED", "pins": {"anode": "13", "cathode": "GND"}}]}'
```

### 2. Test Landing Page

```bash
# Open in browser
open https://your-url.railway.app

# Should show beautiful landing page with pricing
```

### 3. Monitor Usage (Railway Dashboard)

- Go to: https://railway.app/dashboard
- Check: CPU, Memory, Network usage
- Free tier limits: 500 hours/month, $5 credit

---

## Troubleshooting

### Issue: "Module not found" error

**Fix:** Make sure all dependencies are in `requirements.txt`
```bash
# Rebuild
railway up --detach
railway logs
```

### Issue: Port binding error

**Fix:** Railway sets `PORT` automatically. Make sure `api_server.py` uses:
```python
import os
port = int(os.environ.get('PORT', 5000))
app.run(host='0.0.0.0', port=port)
```

This is already configured in the latest version.

### Issue: Static files not loading

**Fix:** Verify static folder configuration:
```python
app = Flask(__name__, static_folder='static', static_url_path='/static')
```

Already configured in the latest version.

### Issue: Deployment takes too long

**Cause:** PyTorch and YOLOv8 are large packages (~2GB)

**Fix:** This is normal. First deployment takes 5-10 minutes. Subsequent deployments are cached and take <2 minutes.

---

## Cost Optimization

### Free Tier Strategy (Recommended for Launch)

**Railway Free Tier:**
- $5 credit/month
- 500 execution hours
- Perfect for: 0-100 users

**Expected costs:**
- Months 1-2: $0/month (within free tier)
- Month 3: $0-10/month (if you get traction)

### When to Upgrade

Upgrade to Railway Pro ($20/month) when:
- You exceed 500 hours/month (>100 active users)
- You need custom domains
- You hit $5 credit limit

**ROI:** Upgrade only when revenue > $100/month (5 paid users minimum)

---

## Scaling Strategy

### Phase 1: Launch (0-100 users)
- **Platform:** Railway Free
- **Cost:** $0/month
- **DB:** SQLite (local file)
- **Cache:** In-memory

### Phase 2: Growth (100-1,000 users)
- **Platform:** Railway Pro ($20/month)
- **Cost:** $20-50/month
- **DB:** Supabase Free or Railway Postgres
- **Cache:** Railway Redis

### Phase 3: Scale (1,000+ users)
- **Platform:** Railway Pro + CDN
- **Cost:** $50-200/month
- **DB:** Supabase Pro ($25/month)
- **Cache:** Railway Redis ($10/month)
- **CDN:** Cloudflare (free)

---

## Custom Domain Setup

### Railway Custom Domain

```bash
# 1. Buy domain (Namecheap $1/year for .xyz)
# 2. Add domain in Railway dashboard
railway domain

# 3. Add DNS records (in Namecheap):
# A record: @ -> Railway IP
# CNAME: www -> your-app.up.railway.app

# 4. SSL is automatic (Railway handles it)
```

### Example: circuit-ai.xyz

- `circuit-ai.xyz` → Landing page
- `api.circuit-ai.xyz` → API server
- `docs.circuit-ai.xyz` → Documentation

---

## Monitoring & Analytics

### Built-in Monitoring (Railway Dashboard)

- **Metrics:** CPU, Memory, Network, Response Time
- **Logs:** Real-time logs with search
- **Alerts:** Email alerts for downtime

### Optional: Add Sentry (Error Tracking)

```bash
# 1. Sign up at sentry.io (free tier: 5K errors/month)
# 2. Get DSN
# 3. Set environment variable
railway variables set SENTRY_DSN=your_dsn_here

# 4. Circuit-AI will automatically report errors (if configured)
```

---

## Security Checklist

### Production Security:

- [ ] Set `DEBUG=False`
- [ ] Set `FLASK_ENV=production`
- [ ] Use HTTPS (Railway does this automatically)
- [ ] Don't commit `.env` file (use `.env.example` only)
- [ ] Rotate API keys quarterly
- [ ] Enable Railway access logs
- [ ] Set up rate limiting (built-in)

### API Key Security:

```bash
# Never commit these:
CEREBRAS_API_KEY=xxx
OPENAI_API_KEY=xxx
STRIPE_SECRET_KEY=xxx

# Store in Railway secrets:
railway variables set CEREBRAS_API_KEY=xxx --secret
```

---

## Backup Strategy

### Database Backups (When using Postgres)

```bash
# Railway auto-backups every 24 hours
# To manual backup:
railway pg:dump > backup.sql
```

### Code Backups

```bash
# Always push to GitHub
git push origin master

# Tag releases
git tag -a v0.4.0 -m "Launch version"
git push --tags
```

---

## CI/CD (Continuous Deployment)

### Automatic Deployment on Git Push

Railway automatically deploys when you push to master:

```bash
# Make changes
git add .
git commit -m "feat: Add new feature"
git push origin master

# Railway automatically:
# 1. Detects push
# 2. Builds new version
# 3. Runs tests (if configured)
# 4. Deploys to production
# 5. Sends notification

# Check deployment status:
railway status
```

### Rollback Strategy

```bash
# If deployment breaks:
railway rollback

# Or deploy specific commit:
railway up --detach <commit-hash>
```

---

## Launch Day Checklist

### Pre-Launch (Night Before):

- [ ] Deploy to Railway
- [ ] Test all endpoints (health, validate, recipes)
- [ ] Test landing page in browser
- [ ] Verify pricing display is correct
- [ ] Check mobile responsiveness
- [ ] Set up error monitoring (Sentry)
- [ ] Prepare social media posts

### Launch Day:

- [ ] Post on Reddit (r/arduino, r/PrintedCircuitBoard)
- [ ] Post on HackerNews
- [ ] Tweet about launch
- [ ] Email existing users (if any)
- [ ] Monitor Railway dashboard for errors
- [ ] Respond to comments/questions

### Post-Launch (First Week):

- [ ] Monitor error logs daily
- [ ] Track user signups
- [ ] Collect feedback
- [ ] Fix critical bugs ASAP
- [ ] Iterate on landing page copy based on feedback

---

## Support & Resources

**Railway Docs:** https://docs.railway.app
**Circuit-AI Docs:** See README.md
**Issues:** https://github.com/user/circuit-ai/issues

**Cost Calculator:** https://railway.app/pricing

**Community:**
- Railway Discord: https://discord.gg/railway
- Circuit-AI Discussions: GitHub Discussions (coming soon)

---

## Quick Commands Reference

```bash
# Deploy
railway up

# View logs
railway logs

# Set environment variable
railway variables set KEY=value

# Get deployment URL
railway domain

# Open in browser
railway open

# Check status
railway status

# Rollback
railway rollback

# SSH into container (debugging)
railway run bash
```

---

**Ready to launch?** Run `railway up` and you're live in 5 minutes. 🚀
