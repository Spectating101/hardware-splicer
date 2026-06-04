#!/bin/bash
# Quick start script for Taiwan payment setup
# Works immediately with just your PayPal email

echo "🇹🇼 Circuit-AI Payment System - Taiwan Edition"
echo "=============================================="
echo ""

# Check if environment variables are set
if [ -z "$PAYPAL_EMAIL" ]; then
    echo "⚠️  PAYPAL_EMAIL not set"
    echo ""
    echo "Quick setup:"
    echo "  export PAYPAL_EMAIL='your@paypal.com'"
    echo "  export BILLING_EMAIL='your@email.com'"
    echo ""
    echo "Then run this script again, or start manually."
    echo ""

    # Offer to set it now
    read -p "Enter your PayPal email (or press Enter to skip): " paypal_email
    if [ ! -z "$paypal_email" ]; then
        export PAYPAL_EMAIL="$paypal_email"
        export BILLING_EMAIL="${BILLING_EMAIL:-$paypal_email}"
        echo "✅ PayPal email set: $PAYPAL_EMAIL"
    fi
fi

echo ""
echo "Payment Methods Configured:"
echo ""

# Check PayPal
if [ ! -z "$PAYPAL_CLIENT_ID" ]; then
    echo "  ✅ PayPal (Automated) - Credit cards, PayPal balance"
elif [ ! -z "$PAYPAL_EMAIL" ]; then
    echo "  ✅ PayPal (Manual invoices) - $PAYPAL_EMAIL"
else
    echo "  ❌ PayPal - Not configured"
fi

# Check Wise
if [ ! -z "$WISE_API_TOKEN" ]; then
    echo "  ✅ Wise - Bank transfers (USD, EUR, GBP, etc.)"
else
    echo "  ❌ Wise - Not configured (optional, low fees)"
fi

# Check Crypto
if [ ! -z "$CRYPTO_API_KEY" ]; then
    echo "  ✅ Cryptocurrency - Bitcoin, Ethereum, USDT"
else
    echo "  ❌ Crypto - Not configured (optional, 1% fees)"
fi

# Check ECPay
if [ ! -z "$ECPAY_MERCHANT_ID" ]; then
    echo "  ✅ ECPay 綠界 - Taiwan credit cards, ATM, 7-11"
else
    echo "  ❌ ECPay - Not configured (optional, Taiwan only)"
fi

echo ""
echo "=============================================="
echo ""

# Start the server
if [ -d ".venv_molina" ]; then
    echo "Starting Circuit-AI API server..."
    source .venv_molina/bin/activate
    python api_server.py
else
    echo "⚠️  Virtual environment not found"
    echo "Running with system Python..."
    python3 api_server.py
fi
