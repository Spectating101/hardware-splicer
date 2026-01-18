# 🌍 Global Payment Setup Guide
## Works in ANY Country (No Stripe Required!)

**The Problem**: Stripe only works in ~47 countries
**The Solution**: Use global payment processors that work anywhere

---

## ✅ Best Options (Ranked by Ease of Setup)

### Option 1: **Lemonsqueezy** ⭐ RECOMMENDED

**Why**: Easiest to set up, works globally, handles all tax/compliance

**Supported**: Worldwide (they act as merchant of record)

**Setup** (10 minutes):
```bash
1. Sign up: https://lemonsqueezy.com
2. Create 3 products in dashboard:
   - "Repair Guide" - $4.99 one-time
   - "Pro Subscription" - $9.99/month
   - "Expert Session" - $19.99 one-time

3. Get API credentials:
   - Settings → API → Create API Key
   - Copy Store ID from dashboard

4. Configure:
   export LEMONSQUEEZY_API_KEY='your_api_key_here'
   export LEMONSQUEEZY_STORE_ID='your_store_id'
   export LS_VARIANT_GUIDE='variant_id_for_guide'
   export LS_VARIANT_PRO='variant_id_for_pro'
   export LS_VARIANT_EXPERT='variant_id_for_expert'

5. Restart server - Done!
```

**Fees**: 5% + payment processing (~2.9%)
**Payout**: Weekly to your bank account
**Currencies**: Auto-converts to USD/EUR/GBP

---

### Option 2: **Paddle**

**Why**: Very similar to Lemonsqueezy, slightly more established

**Supported**: Worldwide (merchant of record)

**Setup**:
```bash
1. Sign up: https://paddle.com
2. Create products in dashboard
3. Get vendor ID and API key
4. Configure:
   export PADDLE_VENDOR_ID='your_vendor_id'
   export PADDLE_API_KEY='your_api_key'
```

**Fees**: 5% + payment processing
**Payout**: Configurable (weekly/monthly)

---

### Option 3: **PayPal**

**Why**: Available in 200+ countries, everyone has it

**Supported**: Most countries worldwide

**Setup**:
```bash
1. Sign up: https://paypal.com/merchant
2. Go to developer.paypal.com
3. Create REST API app
4. Get Client ID and Secret
5. Configure:
   export PAYPAL_CLIENT_ID='your_client_id'
   export PAYPAL_SECRET='your_secret'
```

**Fees**: 2.9% + $0.30 per transaction
**Payout**: Instant to PayPal balance
**Note**: Customers need PayPal account (can be a barrier)

---

### Option 4: **Cryptocurrency** (Bitcoin, Ethereum, USDT)

**Why**: Works literally anywhere, no restrictions

**Supported**: Global (if you have crypto wallet)

**Setup Option A - Coinbase Commerce** (easiest):
```bash
1. Sign up: https://commerce.coinbase.com
2. Create account (free)
3. Get API key
4. Configure:
   export CRYPTO_API_KEY='your_api_key'
   export CRYPTO_PROVIDER='coinbase'
```

**Setup Option B - BTCPay Server** (self-hosted, free):
```bash
1. Deploy BTCPay Server (docker)
2. Connect your Bitcoin wallet
3. Get API endpoint
4. No fees, fully self-sovereign
```

**Fees**:
- Coinbase Commerce: 1%
- BTCPay: $0 (just blockchain fees)

**Payout**: Instant crypto to your wallet
**Note**: Some customers uncomfortable with crypto

---

### Option 5: **Manual Payments** (Always Works)

**Why**: Zero tech requirements, works anywhere

**Supported**: Literally everywhere

**Setup**:
```bash
# Just configure your bank/PayPal details:
export BANK_ACCOUNT_NAME='Your Name'
export BANK_ACCOUNT_NUMBER='Your account'
export BANK_NAME='Your Bank'
export PAYPAL_EMAIL='your@paypal.com'
export CRYPTO_WALLET_ADDRESS='your_btc_address'  # optional
export BILLING_EMAIL='billing@yourdomain.com'
```

**How it works**:
1. User gets invoice with payment instructions
2. They pay via bank transfer/PayPal/crypto
3. They email you the receipt
4. You manually grant access (or use webhook)

**Fees**: Whatever your bank/PayPal charges
**Payout**: Immediate
**Pro**: Works anywhere, you control everything
**Con**: Manual work, not instant access

---

## 🌏 Regional Recommendations

### **Asia** (India, Southeast Asia, China)
1. **Lemonsqueezy** - Works everywhere
2. **PayPal** - If available in your country
3. **Crypto** - Very popular in Asia
4. **Razorpay** - India only (we can add if needed)

### **Middle East & Africa**
1. **Lemonsqueezy** - Best option
2. **Crypto** - Good adoption
3. **PayPal** - Limited availability
4. **Manual** - Bank transfer fallback

### **Latin America**
1. **Lemonsqueezy** - Handles all compliance
2. **PayPal** - Available in most countries
3. **MercadoPago** - Brazil/Argentina (can add)
4. **Crypto** - Growing adoption

### **Eastern Europe**
1. **Paddle** or **Lemonsqueezy**
2. **PayPal** - Available
3. **Payselection** - Russia/CIS (can add)
4. **Crypto** - High adoption

---

## 🚀 Quick Start (5 Minutes)

**For immediate testing** without any payment processor:

```bash
# Don't set any payment environment variables
# System will use "manual" mode automatically

python api_server.py
```

Then:
1. User gets diagnosis
2. Clicks "Get Full Guide"
3. Sees invoice with your payment details
4. Pays you directly
5. You email them the guide link

This works **right now** with zero setup!

---

## 💡 My Recommendation For You

Since you can't use Stripe, here's what I'd do:

**Phase 1 - Launch This Week** (Manual Mode):
```bash
# Set up manual payments (2 minutes):
export PAYPAL_EMAIL='yourpaypal@email.com'
export BILLING_EMAIL='billing@yourdomain.com'

# Advertise: "Pay via PayPal, get access in 1 hour"
# Process ~10 customers manually to validate demand
```

**Phase 2 - Scale Up** (After first 10 sales):
```bash
# Sign up for Lemonsqueezy (10 minutes):
# - Instant automated payments
# - They handle all tax/compliance
# - Works in your country
# - Customers get instant access

# This is when you go from $0 → $10k/month
```

**Phase 3 - Optimize** (After $10k/month):
```bash
# Add multiple payment options:
# - Lemonsqueezy (primary)
# - PayPal (for people who prefer it)
# - Crypto (for privacy-focused users)

# This is when you go $10k → $100k/month
```

---

## 📊 Cost Comparison

| Provider | Setup Time | Fees | Payout Speed | Works In |
|----------|-----------|------|--------------|----------|
| **Lemonsqueezy** | 10 min | ~7.5% | Weekly | Worldwide |
| **Paddle** | 15 min | ~7% | Weekly | Worldwide |
| **PayPal** | 30 min | ~3.2% | Instant | 200+ countries |
| **Crypto** | 15 min | 1% | Instant | Everywhere |
| **Manual** | 2 min | Bank fees | Instant | Everywhere |

---

## 🔧 Testing Payment Integration

```bash
# 1. Start server with global payment service
python api_server.py

# 2. Test checkout creation
curl -X POST http://localhost:5000/api/payment/create-checkout \
  -H "Content-Type: application/json" \
  -d '{
    "product_type":"guide_onetime",
    "repair_guide":"iPhone Screen Replacement",
    "customer_email":"test@example.com"
  }'

# Response shows which gateway is active:
{
  "payment_method": "manual",  // or "lemonsqueezy", "paypal", etc
  "invoice": {...},
  "session_id": "INV-20260118-12345"
}

# 3. User pays
# 4. You grant access manually or via webhook
```

---

## ❓ FAQ

**Q: Which option should I use?**
A: Start with **Manual** (works immediately), upgrade to **Lemonsqueezy** after 10 sales.

**Q: Is Lemonsqueezy available in my country?**
A: Yes! They're the merchant of record, so they handle compliance. You just receive payouts.

**Q: Can I use multiple payment options?**
A: Yes! The system will detect which gateways are configured and offer all of them.

**Q: What about taxes?**
A: Lemonsqueezy/Paddle handle ALL tax compliance automatically (huge benefit!).
For others, you're responsible for your local taxes.

**Q: Do I need a company/business license?**
A: Not for Lemonsqueezy/Paddle (they're merchant of record).
For PayPal/manual, depends on your country (usually no for small amounts).

---

## 🎯 Action Steps

**Right now** (2 minutes):
```bash
# Enable manual payments:
export PAYPAL_EMAIL='your@email.com'
export BILLING_EMAIL='your@email.com'

# You can start taking payments TODAY
```

**This week** (10 minutes):
```bash
# Sign up for Lemonsqueezy
# Set environment variables
# Test with $1 payment to yourself
# Launch!
```

**Want help?** Tell me:
1. What country you're in
2. Which payment method you prefer
3. I'll give you exact setup steps

---

## 📝 Summary

**You don't need Stripe!** In fact, Lemonsqueezy is actually **easier** than Stripe because they handle all the tax/compliance headaches.

**You can launch TODAY** with manual payments and upgrade to automated later.

**The payment system is ready** - it just needs you to pick a payment gateway and add your API keys.

Ready to set it up? Let me know which option you want to use!
