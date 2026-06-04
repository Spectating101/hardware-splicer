# LLM Setup Guide - Free Options

## Option 1: Groq (RECOMMENDED - Fast & Free)

**Why Groq:**
- Completely free tier
- Very fast inference (faster than OpenAI)
- Good models (Llama 3, Mixtral)
- No credit card required

**Steps:**
1. Go to: https://console.groq.com/
2. Click "Sign Up" (can use Google/GitHub)
3. After login, go to "API Keys" section
4. Click "Create API Key"
5. Copy the key (starts with `gsk_...`)
6. Add to `.env` file:
   ```
   LLM_ENABLED=true
   GROQ_API_KEY=gsk_your_key_here
   ```

**Models available:**
- llama-3.1-70b-versatile (best quality)
- llama-3.1-8b-instant (fastest)
- mixtral-8x7b-32768 (good balance)

---

## Option 2: Cohere (Free Tier Alternative)

**Why Cohere:**
- Free tier available
- Good for text generation
- Trial credits included

**Steps:**
1. Go to: https://dashboard.cohere.com/
2. Sign up (email or Google)
3. Go to "API Keys" section
4. Copy your default API key
5. Add to `.env`:
   ```
   LLM_ENABLED=true
   COHERE_API_KEY=your_key_here
   ```

---

## Option 3: Local (Ollama - Completely Free, No API Key)

**Why Ollama:**
- 100% free, no API keys
- Runs locally on your machine
- Complete privacy
- Slower than cloud APIs

**Steps:**
1. Install Ollama: https://ollama.ai/download
2. Run: `ollama pull llama3`
3. Add to `.env`:
   ```
   LLM_ENABLED=true
   LLM_PROVIDER=ollama
   LLM_MODEL=llama3
   ```

**Note:** Requires ~4GB RAM and downloads ~4GB model

---

## What I Recommend For You:

**Start with Groq** because:
- ✅ Free forever (no trial expiration)
- ✅ Fast (you'll see results immediately)
- ✅ No credit card needed
- ✅ Easy setup (2 minutes)
- ✅ Works with your existing code (LiteLLM supports Groq)

Takes literally 2 minutes to get the API key.

---

## After Getting Key:

1. Add key to `.env` file in project root
2. Verify `.env` looks like:
   ```bash
   LLM_ENABLED=true
   GROQ_API_KEY=gsk_your_actual_key_here

   # Keep existing settings
   DATABASE_URL=sqlite:///./data/circuit_ai.db
   ```

3. Test it works:
   ```bash
   source venv/bin/activate
   python -c "import os; from dotenv import load_dotenv; load_dotenv(); print('LLM Key loaded!' if os.getenv('GROQ_API_KEY') else 'Key not found')"
   ```

That's it!
