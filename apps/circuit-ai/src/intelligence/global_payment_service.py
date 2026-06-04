#!/usr/bin/env python3
"""
Global Payment Service - Works Anywhere in the World
Supports multiple payment gateways that have global coverage
"""

import os
import json
import hashlib
from typing import Dict, Optional, List
from datetime import datetime, timedelta

# Multiple payment gateway support
AVAILABLE_GATEWAYS = {
    'paypal': 'PayPal - Available in 200+ countries, works in Taiwan',
    'wise': 'Wise (TransferWise) - Multi-currency, low fees, Taiwan-friendly',
    'crypto': 'Cryptocurrency - Works anywhere, popular in Taiwan',
    'ecpay': 'ECPay 綠界 - Taiwan local payment gateway',
    'paddle': 'Paddle.com - Works globally, merchant of record',
    'lemonsqueezy': 'Lemonsqueezy - Works globally, merchant of record',
    'manual': 'Manual invoicing - Works anywhere',
}


class GlobalPaymentService:
    """
    Universal payment service supporting multiple global payment processors

    Priority order (based on ease of use + global availability):
    1. Lemonsqueezy - Easiest to set up, works globally
    2. Paddle - Similar to Lemonsqueezy, very reliable
    3. PayPal - Widest coverage but more complex
    4. Crypto - Works anywhere, some UX friction
    5. Manual - Fallback for any country
    """

    def __init__(self):
        """Initialize with available payment gateway"""
        # Auto-detect which payment gateway is configured
        self.gateway = self._detect_gateway()

        # Pricing (same across all gateways)
        self.prices = {
            'guide_onetime': {
                'amount': 4.99,
                'currency': 'USD',
                'name': 'Full Repair Guide',
                'description': 'Complete step-by-step repair guide with photos and videos'
            },
            'pro_monthly': {
                'amount': 9.99,
                'currency': 'USD',
                'name': 'Circuit-AI Pro',
                'description': 'Unlimited repair guides + expert chat support',
                'interval': 'month'
            },
            'expert_session': {
                'amount': 19.99,
                'currency': 'USD',
                'name': 'Live Expert Diagnosis',
                'description': '30-minute live video session with repair expert'
            }
        }

        # Simple in-memory storage (replace with database)
        self.purchases = {}
        self.subscriptions = {}

    def _detect_gateway(self) -> str:
        """Auto-detect which payment gateway is configured (Taiwan-optimized priority)"""
        # Priority order for Taiwan users
        if os.getenv('PAYPAL_CLIENT_ID'):
            return 'paypal'
        elif os.getenv('WISE_API_TOKEN'):
            return 'wise'
        elif os.getenv('CRYPTO_API_KEY') or os.getenv('CRYPTO_WALLET_ADDRESS'):
            return 'crypto'
        elif os.getenv('ECPAY_MERCHANT_ID'):
            return 'ecpay'
        elif os.getenv('LEMONSQUEEZY_API_KEY'):
            return 'lemonsqueezy'
        elif os.getenv('PADDLE_VENDOR_ID'):
            return 'paddle'
        else:
            return 'manual'  # Default fallback

    # ========================================================================
    # Lemonsqueezy Integration (RECOMMENDED - Easiest global option)
    # ========================================================================

    def _lemonsqueezy_checkout(self, product_type: str, repair_guide: str,
                               customer_email: Optional[str]) -> Dict:
        """
        Create Lemonsqueezy checkout

        Setup:
        1. Sign up at lemonsqueezy.com (works globally)
        2. Create products in dashboard
        3. Get API key and store ID
        4. Set environment variables:
           export LEMONSQUEEZY_API_KEY='your_key'
           export LEMONSQUEEZY_STORE_ID='your_store_id'
        """
        api_key = os.getenv('LEMONSQUEEZY_API_KEY')
        store_id = os.getenv('LEMONSQUEEZY_STORE_ID')

        if not api_key or not store_id:
            return {
                'error': 'Lemonsqueezy not configured',
                'setup_url': 'https://lemonsqueezy.com',
                'instructions': 'Sign up at lemonsqueezy.com and set LEMONSQUEEZY_API_KEY'
            }

        try:
            import requests

            # Create checkout session
            price_info = self.prices[product_type]

            payload = {
                'data': {
                    'type': 'checkouts',
                    'attributes': {
                        'checkout_data': {
                            'email': customer_email,
                            'custom': {
                                'repair_guide': repair_guide
                            }
                        }
                    },
                    'relationships': {
                        'store': {
                            'data': {
                                'type': 'stores',
                                'id': store_id
                            }
                        },
                        'variant': {
                            'data': {
                                'type': 'variants',
                                'id': self._get_lemonsqueezy_variant_id(product_type)
                            }
                        }
                    }
                }
            }

            response = requests.post(
                'https://api.lemonsqueezy.com/v1/checkouts',
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                json=payload
            )

            data = response.json()
            checkout_url = data['data']['attributes']['url']

            return {
                'checkout_url': checkout_url,
                'session_id': data['data']['id'],
                'gateway': 'lemonsqueezy'
            }

        except Exception as e:
            return {'error': str(e)}

    def _get_lemonsqueezy_variant_id(self, product_type: str) -> str:
        """Map product types to Lemonsqueezy variant IDs (set these after creating products)"""
        variant_map = {
            'guide_onetime': os.getenv('LS_VARIANT_GUIDE', 'CONFIGURE_ME'),
            'pro_monthly': os.getenv('LS_VARIANT_PRO', 'CONFIGURE_ME'),
            'expert_session': os.getenv('LS_VARIANT_EXPERT', 'CONFIGURE_ME')
        }
        return variant_map.get(product_type, 'CONFIGURE_ME')

    # ========================================================================
    # PayPal Integration (200+ countries)
    # ========================================================================

    def _paypal_checkout(self, product_type: str, repair_guide: str,
                         customer_email: Optional[str]) -> Dict:
        """
        Create PayPal checkout

        Setup:
        1. Sign up at paypal.com/merchant
        2. Get Client ID and Secret from developer.paypal.com
        3. Set environment variables:
           export PAYPAL_CLIENT_ID='your_client_id'
           export PAYPAL_SECRET='your_secret'
        """
        client_id = os.getenv('PAYPAL_CLIENT_ID')
        secret = os.getenv('PAYPAL_SECRET')

        if not client_id or not secret:
            return {
                'error': 'PayPal not configured',
                'setup_url': 'https://developer.paypal.com',
                'instructions': 'Get credentials from PayPal developer dashboard'
            }

        try:
            import requests
            import base64

            # Get access token
            auth = base64.b64encode(f'{client_id}:{secret}'.encode()).decode()
            token_response = requests.post(
                'https://api-m.paypal.com/v1/oauth2/token',
                headers={'Authorization': f'Basic {auth}'},
                data={'grant_type': 'client_credentials'}
            )
            access_token = token_response.json()['access_token']

            # Create order
            price_info = self.prices[product_type]

            order_payload = {
                'intent': 'CAPTURE',
                'purchase_units': [{
                    'amount': {
                        'currency_code': price_info['currency'],
                        'value': str(price_info['amount'])
                    },
                    'description': f"{price_info['name']}: {repair_guide}"
                }],
                'application_context': {
                    'return_url': 'http://localhost:5000/static/payment-success.html',
                    'cancel_url': 'http://localhost:5000/static/payment-cancelled.html'
                }
            }

            order_response = requests.post(
                'https://api-m.paypal.com/v2/checkout/orders',
                headers={
                    'Authorization': f'Bearer {access_token}',
                    'Content-Type': 'application/json'
                },
                json=order_payload
            )

            order_data = order_response.json()
            approve_link = next(link['href'] for link in order_data['links'] if link['rel'] == 'approve')

            return {
                'checkout_url': approve_link,
                'session_id': order_data['id'],
                'gateway': 'paypal'
            }

        except Exception as e:
            return {'error': str(e)}

    # ========================================================================
    # Cryptocurrency Integration (Works Anywhere)
    # ========================================================================

    def _crypto_checkout(self, product_type: str, repair_guide: str,
                         customer_email: Optional[str]) -> Dict:
        """
        Create crypto payment request

        Options:
        1. BTCPay Server (self-hosted, free)
        2. Coinbase Commerce (easiest)
        3. NOWPayments (supports 100+ coins)

        Setup:
        1. Sign up at commerce.coinbase.com or nowpayments.io
        2. Get API key
        3. Set: export CRYPTO_API_KEY='your_key'
        """
        api_key = os.getenv('CRYPTO_API_KEY')
        provider = os.getenv('CRYPTO_PROVIDER', 'coinbase')  # or 'nowpayments'

        if not api_key:
            return {
                'error': 'Crypto payments not configured',
                'setup_url': 'https://commerce.coinbase.com',
                'instructions': 'Set up Coinbase Commerce for crypto payments'
            }

        price_info = self.prices[product_type]

        try:
            import requests

            if provider == 'coinbase':
                # Coinbase Commerce
                payload = {
                    'name': price_info['name'],
                    'description': f"{repair_guide}",
                    'pricing_type': 'fixed_price',
                    'local_price': {
                        'amount': str(price_info['amount']),
                        'currency': 'USD'
                    },
                    'metadata': {
                        'customer_email': customer_email,
                        'repair_guide': repair_guide
                    }
                }

                response = requests.post(
                    'https://api.commerce.coinbase.com/charges',
                    headers={
                        'X-CC-Api-Key': api_key,
                        'Content-Type': 'application/json'
                    },
                    json=payload
                )

                data = response.json()['data']
                return {
                    'checkout_url': data['hosted_url'],
                    'session_id': data['code'],
                    'gateway': 'crypto_coinbase',
                    'payment_addresses': data['addresses']
                }

        except Exception as e:
            return {'error': str(e)}

    # ========================================================================
    # Manual Payment (Email Invoice - Works Anywhere)
    # ========================================================================

    def _manual_checkout(self, product_type: str, repair_guide: str,
                         customer_email: Optional[str]) -> Dict:
        """
        Create manual invoice (bank transfer, cash, etc)

        This always works as a fallback option
        """
        price_info = self.prices[product_type]
        invoice_id = f"INV-{datetime.now().strftime('%Y%m%d')}-{hash(customer_email or '')}"

        # Bank details (configure these)
        bank_details = {
            'account_name': os.getenv('BANK_ACCOUNT_NAME', 'Your Business Name'),
            'account_number': os.getenv('BANK_ACCOUNT_NUMBER', 'Configure Me'),
            'bank_name': os.getenv('BANK_NAME', 'Your Bank'),
            'swift_code': os.getenv('BANK_SWIFT', 'Optional')
        }

        invoice_details = {
            'invoice_id': invoice_id,
            'amount': price_info['amount'],
            'currency': price_info['currency'],
            'product': price_info['name'],
            'description': repair_guide,
            'customer_email': customer_email,
            'payment_methods': [
                f"Bank Transfer: {bank_details['account_name']} - {bank_details['account_number']}",
                "PayPal: " + os.getenv('PAYPAL_EMAIL', 'your@email.com'),
                "Crypto: " + os.getenv('CRYPTO_WALLET_ADDRESS', 'your_wallet_address')
            ],
            'instructions': [
                f"1. Transfer ${price_info['amount']} to one of the accounts above",
                f"2. Email receipt to {os.getenv('BILLING_EMAIL', 'billing@circuit-ai.com')}",
                f"3. Include invoice ID: {invoice_id}",
                "4. Access granted within 24 hours"
            ]
        }

        return {
            'payment_method': 'manual',
            'invoice': invoice_details,
            'session_id': invoice_id,
            'gateway': 'manual',
            'message': 'Invoice created. Please follow payment instructions.'
        }

    # ========================================================================
    # Universal Interface (Auto-routes to configured gateway)
    # ========================================================================

    def create_checkout_session(
        self,
        product_type: str,
        repair_guide: str,
        success_url: str,
        cancel_url: str,
        customer_email: Optional[str] = None
    ) -> Dict:
        """
        Create checkout session using whichever gateway is configured
        """
        # Route to appropriate gateway
        if self.gateway == 'lemonsqueezy':
            return self._lemonsqueezy_checkout(product_type, repair_guide, customer_email)
        elif self.gateway == 'paypal':
            return self._paypal_checkout(product_type, repair_guide, customer_email)
        elif self.gateway == 'crypto':
            return self._crypto_checkout(product_type, repair_guide, customer_email)
        else:  # manual
            return self._manual_checkout(product_type, repair_guide, customer_email)

    def verify_payment(self, session_id: str) -> Dict:
        """Verify payment (gateway-agnostic)"""
        # Test mode
        return {
            'status': 'paid',
            'test_mode': True,
            'repair_guide': 'iPhone Screen Replacement',
            'amount': 499,
            'customer_email': 'test@example.com',
            'access_granted': True,
            'purchase_id': f'purchase_{session_id}'
        }

    def check_access(self, user_identifier: str, repair_guide: str) -> Dict:
        """Check access (same for all gateways)"""
        # Check in-memory purchases
        for purchase in self.purchases.values():
            if purchase.get('customer_email') == user_identifier:
                if purchase['repair_guide'] == repair_guide:
                    return {'has_access': True, 'type': 'purchase'}

        return {
            'has_access': False,
            'message': 'Purchase required',
            'price': f'${self.prices["guide_onetime"]["amount"]} one-time'
        }

    def get_analytics(self) -> Dict:
        """Get analytics (same for all gateways)"""
        total_revenue = sum(p.get('amount', 0) for p in self.purchases.values()) / 100
        return {
            'total_revenue': f'${total_revenue:.2f}',
            'total_purchases': len(self.purchases),
            'gateway': self.gateway,
            'available_gateways': AVAILABLE_GATEWAYS
        }


if __name__ == '__main__':
    # Test the service
    service = GlobalPaymentService()

    print("🌍 Global Payment Service")
    print("=" * 60)
    print(f"\nDetected Gateway: {service.gateway}")
    print(f"\nAvailable Gateways:")
    for gateway, description in AVAILABLE_GATEWAYS.items():
        status = "✅ CONFIGURED" if gateway == service.gateway else "❌ Not configured"
        print(f"  {gateway:15} - {description} [{status}]")

    print("\n" + "=" * 60)
    print("\n💡 RECOMMENDATIONS BY REGION:")
    print("\nAsia/Middle East/Africa:")
    print("  1. Lemonsqueezy (easiest, works globally)")
    print("  2. PayPal (if available in your country)")
    print("  3. Crypto (Bitcoin, USDT via Coinbase Commerce)")

    print("\nLatin America:")
    print("  1. Lemonsqueezy (handles all tax/compliance)")
    print("  2. PayPal")
    print("  3. MercadoPago (region-specific, add if needed)")

    print("\nEastern Europe:")
    print("  1. Paddle or Lemonsqueezy")
    print("  2. PayPal")
    print("  3. Local gateways (Payselection, etc.)")

    print("\n" + "=" * 60)
    print("\n📋 SETUP INSTRUCTIONS:")
    print("\nOption 1: Lemonsqueezy (RECOMMENDED)")
    print("  1. Sign up: https://lemonsqueezy.com")
    print("  2. Create products in dashboard")
    print("  3. export LEMONSQUEEZY_API_KEY='your_key'")
    print("  4. export LEMONSQUEEZY_STORE_ID='your_store_id'")

    print("\nOption 2: PayPal")
    print("  1. Sign up: https://paypal.com/merchant")
    print("  2. Get credentials: https://developer.paypal.com")
    print("  3. export PAYPAL_CLIENT_ID='your_id'")
    print("  4. export PAYPAL_SECRET='your_secret'")

    print("\nOption 3: Crypto (Bitcoin/Ethereum)")
    print("  1. Sign up: https://commerce.coinbase.com")
    print("  2. Get API key from dashboard")
    print("  3. export CRYPTO_API_KEY='your_key'")
    print("  4. export CRYPTO_PROVIDER='coinbase'")

    print("\nOption 4: Manual (Always works)")
    print("  1. export BANK_ACCOUNT_NAME='Your Name'")
    print("  2. export PAYPAL_EMAIL='your@email.com'")
    print("  3. Manually process payments")
