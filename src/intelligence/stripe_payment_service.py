#!/usr/bin/env python3
"""
Stripe Payment Service for Circuit-AI Repair Diagnostics
Handles one-time purchases ($4.99) and subscriptions ($9.99/month)
"""

import os
import json
from typing import Dict, Optional
from datetime import datetime, timedelta

# Stripe integration (install with: pip install stripe)
try:
    import stripe
    STRIPE_AVAILABLE = True
except ImportError:
    STRIPE_AVAILABLE = False
    print("⚠️  Stripe not installed. Install with: pip install stripe")


class StripePaymentService:
    """Manages Stripe payments for repair guide purchases"""

    def __init__(self):
        """Initialize Stripe with API keys"""
        # Get from environment variables (set these in production)
        self.stripe_api_key = os.getenv('STRIPE_SECRET_KEY', 'sk_test_PLACEHOLDER')
        self.stripe_publishable_key = os.getenv('STRIPE_PUBLISHABLE_KEY', 'pk_test_PLACEHOLDER')

        # Check if we have real API keys or just placeholders
        self.is_configured = (
            STRIPE_AVAILABLE and
            not self.stripe_api_key.endswith('PLACEHOLDER') and
            not self.stripe_publishable_key.endswith('PLACEHOLDER')
        )

        if self.is_configured:
            stripe.api_key = self.stripe_api_key

        # Pricing configuration
        self.prices = {
            'guide_onetime': {
                'amount': 499,  # $4.99 in cents
                'currency': 'usd',
                'name': 'Full Repair Guide',
                'description': 'Complete step-by-step repair guide with photos and videos'
            },
            'pro_monthly': {
                'amount': 999,  # $9.99 in cents
                'currency': 'usd',
                'name': 'Circuit-AI Pro',
                'description': 'Unlimited repair guides + expert chat support',
                'interval': 'month'
            },
            'expert_session': {
                'amount': 1999,  # $19.99 in cents
                'currency': 'usd',
                'name': 'Live Expert Diagnosis',
                'description': '30-minute live video session with repair expert'
            }
        }

        # Simple in-memory purchase tracking (replace with database in production)
        self.purchases = {}
        self.subscriptions = {}

    def create_checkout_session(
        self,
        product_type: str,
        repair_guide: str,
        success_url: str,
        cancel_url: str,
        customer_email: Optional[str] = None
    ) -> Dict:
        """
        Create a Stripe checkout session

        Args:
            product_type: 'guide_onetime', 'pro_monthly', or 'expert_session'
            repair_guide: Name of the repair guide being purchased
            success_url: URL to redirect after successful payment
            cancel_url: URL to redirect if payment cancelled
            customer_email: Optional customer email

        Returns:
            Dict with checkout session URL and session ID
        """
        if not self.is_configured:
            return {
                'test_mode': True,
                'message': 'Payment would process in production. Test mode active.',
                'checkout_url': '/static/payment-success.html',
                'session_id': 'test_session_' + str(hash(repair_guide))[:16],
                'publishable_key': 'pk_test_DEMO'
            }

        if product_type not in self.prices:
            return {'error': f'Invalid product type: {product_type}'}

        price_info = self.prices[product_type]

        try:
            # Create checkout session
            if product_type == 'pro_monthly':
                # Subscription checkout
                session = stripe.checkout.Session.create(
                    payment_method_types=['card'],
                    line_items=[{
                        'price_data': {
                            'currency': price_info['currency'],
                            'product_data': {
                                'name': price_info['name'],
                                'description': price_info['description'],
                            },
                            'unit_amount': price_info['amount'],
                            'recurring': {
                                'interval': price_info['interval']
                            }
                        },
                        'quantity': 1,
                    }],
                    mode='subscription',
                    success_url=success_url + '?session_id={CHECKOUT_SESSION_ID}',
                    cancel_url=cancel_url,
                    customer_email=customer_email,
                    metadata={'repair_guide': repair_guide}
                )
            else:
                # One-time payment
                session = stripe.checkout.Session.create(
                    payment_method_types=['card'],
                    line_items=[{
                        'price_data': {
                            'currency': price_info['currency'],
                            'product_data': {
                                'name': f"{price_info['name']}: {repair_guide}",
                                'description': price_info['description'],
                            },
                            'unit_amount': price_info['amount'],
                        },
                        'quantity': 1,
                    }],
                    mode='payment',
                    success_url=success_url + '?session_id={CHECKOUT_SESSION_ID}',
                    cancel_url=cancel_url,
                    customer_email=customer_email,
                    metadata={'repair_guide': repair_guide, 'product_type': product_type}
                )

            return {
                'checkout_url': session.url,
                'session_id': session.id,
                'publishable_key': self.stripe_publishable_key
            }

        except Exception as e:
            return {'error': str(e)}

    def verify_payment(self, session_id: str) -> Dict:
        """
        Verify a payment was successful

        Args:
            session_id: Stripe checkout session ID

        Returns:
            Dict with payment status and purchased content
        """
        if not self.is_configured:
            # Test mode - simulate successful payment
            return {
                'status': 'paid',
                'test_mode': True,
                'repair_guide': 'iPhone Screen Replacement',
                'amount': 499,
                'customer_email': 'test@example.com',
                'access_granted': True,
                'purchase_id': f'test_purchase_{session_id}'
            }

        try:
            session = stripe.checkout.Session.retrieve(session_id)

            if session.payment_status == 'paid':
                # Grant access to repair guide
                repair_guide = session.metadata.get('repair_guide', 'Unknown')
                customer_email = session.customer_details.email if session.customer_details else None

                # Store purchase (use database in production)
                purchase_id = f"purchase_{session_id}"
                self.purchases[purchase_id] = {
                    'session_id': session_id,
                    'repair_guide': repair_guide,
                    'customer_email': customer_email,
                    'amount': session.amount_total,
                    'currency': session.currency,
                    'timestamp': datetime.now().isoformat(),
                    'access_expires': None  # One-time purchases don't expire
                }

                return {
                    'status': 'paid',
                    'repair_guide': repair_guide,
                    'customer_email': customer_email,
                    'amount': session.amount_total,
                    'access_granted': True,
                    'purchase_id': purchase_id
                }
            else:
                return {
                    'status': session.payment_status,
                    'access_granted': False
                }

        except Exception as e:
            return {'error': str(e), 'access_granted': False}

    def check_access(self, user_identifier: str, repair_guide: str) -> Dict:
        """
        Check if a user has access to a repair guide

        Args:
            user_identifier: Email or session ID
            repair_guide: Name of the repair guide

        Returns:
            Dict with access status
        """
        # Check purchases
        for purchase_id, purchase in self.purchases.items():
            if (purchase.get('customer_email') == user_identifier or
                purchase.get('session_id') == user_identifier):
                if purchase['repair_guide'] == repair_guide:
                    return {
                        'has_access': True,
                        'type': 'one_time_purchase',
                        'purchase_id': purchase_id
                    }

        # Check subscriptions
        for sub_id, subscription in self.subscriptions.items():
            if (subscription.get('customer_email') == user_identifier and
                subscription.get('status') == 'active'):
                # Pro subscribers have access to all guides
                return {
                    'has_access': True,
                    'type': 'pro_subscription',
                    'subscription_id': sub_id
                }

        return {
            'has_access': False,
            'message': 'Purchase required',
            'price': '$4.99 one-time or $9.99/month Pro'
        }

    def handle_webhook(self, payload: str, sig_header: str) -> Dict:
        """
        Handle Stripe webhook events (payment confirmations, subscription updates)

        Args:
            payload: Raw webhook payload
            sig_header: Stripe signature header

        Returns:
            Dict with processing status
        """
        if not self.is_configured:
            return {'error': 'Stripe not configured', 'test_mode': True}

        webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET', '')

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )

            # Handle different event types
            if event['type'] == 'checkout.session.completed':
                session = event['data']['object']

                # Grant access based on payment
                if session.mode == 'subscription':
                    # Handle subscription
                    subscription_id = session.subscription
                    self.subscriptions[subscription_id] = {
                        'customer_email': session.customer_details.email,
                        'status': 'active',
                        'started_at': datetime.now().isoformat()
                    }

                return {'status': 'processed', 'event_type': event['type']}

            elif event['type'] == 'customer.subscription.deleted':
                # Handle subscription cancellation
                subscription = event['data']['object']
                if subscription.id in self.subscriptions:
                    self.subscriptions[subscription.id]['status'] = 'cancelled'

                return {'status': 'processed', 'event_type': event['type']}

            return {'status': 'ignored', 'event_type': event['type']}

        except Exception as e:
            return {'error': str(e)}

    def get_analytics(self) -> Dict:
        """Get revenue analytics"""
        total_revenue = sum(p.get('amount', 0) for p in self.purchases.values()) / 100
        total_purchases = len(self.purchases)
        active_subscriptions = sum(1 for s in self.subscriptions.values() if s.get('status') == 'active')

        return {
            'total_revenue': f'${total_revenue:.2f}',
            'total_purchases': total_purchases,
            'active_subscriptions': active_subscriptions,
            'mrr': f'${active_subscriptions * 9.99:.2f}',  # Monthly Recurring Revenue
            'avg_order_value': f'${total_revenue / max(total_purchases, 1):.2f}'
        }


if __name__ == '__main__':
    # Test the payment service
    service = StripePaymentService()

    print("💳 Stripe Payment Service - Test Mode")
    print("=" * 60)

    # Test checkout session creation
    print("\n1. Creating checkout session for iPhone Screen guide...")
    checkout = service.create_checkout_session(
        product_type='guide_onetime',
        repair_guide='iPhone Screen Replacement',
        success_url='http://localhost:5000/payment-success',
        cancel_url='http://localhost:5000/payment-cancelled',
        customer_email='test@example.com'
    )
    print(json.dumps(checkout, indent=2))

    # Test payment verification (test mode)
    print("\n2. Verifying test payment...")
    verification = service.verify_payment('test_session_123')
    print(json.dumps(verification, indent=2))

    # Test access check
    print("\n3. Checking access for test user...")
    access = service.check_access('test@example.com', 'iPhone Screen Replacement')
    print(json.dumps(access, indent=2))

    # Test analytics
    print("\n4. Revenue analytics...")
    analytics = service.get_analytics()
    print(json.dumps(analytics, indent=2))

    print("\n" + "=" * 60)
    print("✅ Payment service ready!")
    print("\nTo use in production:")
    print("1. Install Stripe: pip install stripe")
    print("2. Set environment variables:")
    print("   export STRIPE_SECRET_KEY='sk_live_...'")
    print("   export STRIPE_PUBLISHABLE_KEY='pk_live_...'")
    print("   export STRIPE_WEBHOOK_SECRET='whsec_...'")
