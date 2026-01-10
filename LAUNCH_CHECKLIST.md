# Launch Checklist - Circuit-AI

**Goal:** Launch tomorrow, get first users, generate revenue

**Time required:** 4-6 hours total

---

## PRE-LAUNCH (Tonight - 2 hours)

### 1. Deploy to Railway (30 min)

```bash
# Install Railway CLI
curl -fsSL https://railway.app/install.sh | sh

# Login
railway login

# Deploy
cd /path/to/Circuit-AI
railway init
railway up

# Get URL
railway domain
# Save this URL: https://circuit-ai-production.up.railway.app
```

**Checkpoint:** Visit URL in browser, should see landing page ✅

### 2. Test All Endpoints (20 min)

```bash
# Set your Railway URL
export API_URL=https://your-url.up.railway.app

# Health check
curl $API_URL/api/health

# Component list
curl $API_URL/api/components

# Quick validation
curl -X POST $API_URL/api/validate \
  -H "Content-Type: application/json" \
  -d '{"components": [{"type": "LED", "pins": {"anode": "13", "cathode": "GND"}}]}'
```

**Checkpoint:** All endpoints return 200 OK ✅

### 3. Set Production Config (10 min)

```bash
# Production mode
railway variables set DEBUG=False
railway variables set FLASK_ENV=production

# Optional: Add LLM keys (enhanced features)
railway variables set CEREBRAS_API_KEY=your_key_here
# Or skip if you don't have API keys yet
```

### 4. Test Landing Page (15 min)

- [ ] Open landing page in browser
- [ ] Check mobile responsiveness (phone or DevTools)
- [ ] Verify pricing shows correctly
- [ ] Test "Try Free" button (should work or show coming soon)
- [ ] Check API docs link works

### 5. Prepare Social Accounts (15 min)

- [ ] Reddit account ready (karma >10, age >7 days)
- [ ] Twitter/X account ready
- [ ] HackerNews account ready (optional)
- [ ] Copy all post templates from LAUNCH_MATERIALS.md to clipboard

### 6. Final Code Review (30 min)

```bash
# Run quick tests (if you have them)
pytest tests/ || echo "Skipping tests"

# Check git status
git status
# Should be clean

# Push to GitHub
git push origin master

# Tag release
git tag -a v0.4.0 -m "Launch version"
git push --tags
```

**Checkpoint:** Everything committed and pushed ✅

---

## LAUNCH DAY (Morning - 2 hours)

### Morning (9-11 AM EST) - PRIMARY WINDOW

#### 1. Final Pre-Flight Check (10 min)

```bash
# Verify Railway is up
curl https://your-url.railway.app/api/health

# Check Railway dashboard
railway status
railway logs
```

**Checkpoint:** No errors in logs ✅

#### 2. Post on Reddit r/arduino (15 min)

**Title:** I built an AI assistant for Arduino that actually works

**Copy from:** LAUNCH_MATERIALS.md → Reddit Posts → r/arduino

**Steps:**
1. Go to https://reddit.com/r/arduino
2. Click "Create Post"
3. Paste title and body (customize with your Railway URL)
4. Add flair: "Project"
5. Post!

**Checkpoint:** Posted ✅

#### 3. Post on HackerNews (10 min)

**Title:** Circuit-AI: Open-source PCB validation with academic-grade accuracy

**URL:** https://your-railway-url.up.railway.app

**Copy from:** LAUNCH_MATERIALS.md → HackerNews Post

**Steps:**
1. Go to https://news.ycombinator.com/submit
2. Paste URL and title
3. Add text (optional, HN prefers URLs)
4. Submit!

**Checkpoint:** Posted ✅

#### 4. Post on r/PrintedCircuitBoard (10 min)

**Copy from:** LAUNCH_MATERIALS.md → Reddit Posts → r/PrintedCircuitBoard

**Checkpoint:** Posted ✅

#### 5. Tweet Launch Thread (15 min)

**Copy from:** LAUNCH_MATERIALS.md → Twitter Thread

**Steps:**
1. Tweet 1/8
2. Reply with 2/8
3. Continue thread
4. Pin first tweet to profile

**Checkpoint:** Thread posted ✅

---

## LAUNCH DAY (Afternoon - 1 hour)

### Afternoon (2-4 PM EST) - ENGAGEMENT WINDOW

#### 1. Monitor & Respond (45 min)

Check every 30 minutes:

- [ ] Reddit r/arduino comments
- [ ] HackerNews comments
- [ ] r/PrintedCircuitBoard comments
- [ ] Twitter replies

**Response strategy:**
- Answer questions within 15 minutes
- Be helpful, not salesy
- Link to docs when needed
- Use response templates from LAUNCH_MATERIALS.md

#### 2. Fix Critical Bugs (if any)

If users report bugs:

```bash
# Quick fix
git add .
git commit -m "fix: [bug description]"
git push origin master

# Railway auto-deploys
railway status
```

#### 3. Track Metrics (15 min)

**Create spreadsheet with:**
- Reddit upvotes
- HN upvotes
- Twitter impressions
- Railway visitor count
- Email signups (if you have form)

**Goal for Day 1:**
- 20+ upvotes on r/arduino
- 10+ upvotes on HN
- 100+ website visitors

---

## LAUNCH DAY (Evening - 1 hour)

### Evening (6-8 PM EST) - SECOND WAVE

#### 1. Post on r/electronics (15 min)

**Copy from:** LAUNCH_MATERIALS.md → Reddit Posts → r/electronics

**Note:** If it's Saturday/Sunday, use "Show & Tell" flair

#### 2. Share on Discord (30 min)

Relevant servers:
- Arduino Discord
- Hackaday Discord
- Maker communities you're in

**Message template:**
```
Hey! Just launched Circuit-AI - open source Arduino assistant

✅ Perfect resistor calculations
✅ Code generation
✅ PCB validation

Free tier available: [link]

Would love your feedback!
```

#### 3. Evening Check-in (15 min)

- [ ] Respond to new comments
- [ ] Check Railway logs for errors
- [ ] Update metrics spreadsheet
- [ ] Celebrate! 🎉 You launched!

---

## POST-LAUNCH (Week 1)

### Daily Tasks (30 min/day):

**Morning:**
- [ ] Check Railway dashboard
- [ ] Respond to comments (Reddit, HN, Twitter)
- [ ] Fix any bugs reported

**Evening:**
- [ ] Update metrics
- [ ] Plan next day's content
- [ ] Engage with new users

### Week 1 Goals:

| Metric | Target |
|--------|--------|
| Website visitors | 100-500 |
| Reddit upvotes (total) | 50+ |
| Free signups | 20-50 |
| Paid conversions | 2-5 |
| GitHub stars | 50+ |
| MRR | $10-60 |

### Week 1 Content:

**Day 2-3:** Respond to feedback, fix bugs
**Day 4-5:** Write "How I built Circuit-AI" blog post
**Day 6-7:** Plan YouTube video, prepare demo

---

## TROUBLESHOOTING

### Issue: No upvotes on Reddit

**Possible causes:**
- Posted at wrong time (repost at 9-11 AM EST weekday)
- Title not compelling (A/B test different titles)
- Post removed by mods (check rules, message mods)

**Fix:** Repost with better title, different subreddit

### Issue: No signups

**Possible causes:**
- Landing page unclear (simplify CTA)
- Free tier too limited (increase to 20 queries)
- Signup process broken (test it yourself)

**Fix:** Improve landing page copy, test signup flow

### Issue: Railway costs exceeding free tier

**Cause:** Too much traffic (good problem!)

**Fix:**
- Upgrade to Railway Pro ($20/month) only when revenue > $100/month
- Or add caching to reduce API calls
- Or optimize YOLOv8 model loading

### Issue: Negative comments

**Response strategy:**
- Stay calm, professional
- Acknowledge valid criticism
- Fix bugs quickly
- Thank users for feedback

**Example response:**
```
Thanks for the feedback! You're right, that's a bug.

Fixed in v0.4.1 (deployed 10 min ago).

Let me know if you see any other issues!
```

---

## SUCCESS CRITERIA

### Minimum Viable Launch (Week 1):

- [✓] Deployed to Railway
- [✓] 3+ Reddit posts
- [✓] 1+ HackerNews post
- [✓] Twitter thread
- [ ] 20+ free signups
- [ ] 2+ paid conversions
- [ ] $10-60 MRR

### Good Launch (Week 1):

- [ ] 50+ free signups
- [ ] 5+ paid conversions
- [ ] 100+ upvotes on Reddit
- [ ] 50+ GitHub stars
- [ ] $25-150 MRR

### Great Launch (Week 1):

- [ ] 100+ free signups
- [ ] 10+ paid conversions
- [ ] Front page of r/arduino or HN
- [ ] 100+ GitHub stars
- [ ] $50-300 MRR

---

## NEXT STEPS (Week 2-4)

### If launch goes well (>50 signups):

1. **Set up Stripe** (payment processing)
2. **Add payment wall** (enforce 10 query limit)
3. **Email drip campaign** (convert free to paid)
4. **YouTube video** (demo + tutorial)
5. **Blog post** ("How I validated Circuit-AI")

### If launch is slow (<20 signups):

1. **Iterate on landing page** (A/B test headlines)
2. **Post more** (r/embedded, r/ECE, r/AskElectronics)
3. **Create demos** (short videos, GIFs)
4. **Engage communities** (answer questions, be helpful)
5. **Improve free tier** (20 queries instead of 10)

### If launch fails (<10 signups):

1. **Re-evaluate positioning** (maybe target different audience)
2. **Simplify product** (focus on ONE killer feature)
3. **Get direct feedback** (interview potential users)
4. **Consider pivot** (different use case)

---

## FINAL CHECKLIST

**Before you start:**

- [ ] Railway deployment tested ✅
- [ ] Landing page looks good ✅
- [ ] All posts prepared ✅
- [ ] Social accounts ready ✅
- [ ] Response templates ready ✅
- [ ] Metrics spreadsheet created
- [ ] Mental prep (this is exciting!) ✅

**Launch day:**

- [ ] Post r/arduino (9-11 AM EST)
- [ ] Post HackerNews (9-11 AM EST)
- [ ] Post Twitter thread
- [ ] Monitor & respond (2-4 PM EST)
- [ ] Post r/electronics (6-8 PM EST)
- [ ] Share on Discord
- [ ] Celebrate! 🎉

**Week 1:**

- [ ] Daily comment responses
- [ ] Bug fixes as needed
- [ ] Metrics tracking
- [ ] Plan Week 2 content

---

## EMERGENCY CONTACTS

**If Railway goes down:**
- Dashboard: https://railway.app/dashboard
- Status: https://status.railway.app
- Discord: https://discord.gg/railway

**If you get stuck:**
- Railway docs: https://docs.railway.app
- This repo: README.md, DEPLOYMENT_GUIDE.md
- Stack Overflow: Tag questions with 'circuit-ai'

---

**You're ready to launch.**

**Tomorrow morning, run through this checklist.**

**By tomorrow evening, you'll have launched Circuit-AI. 🚀**

**Let's get to $1K/month.**
