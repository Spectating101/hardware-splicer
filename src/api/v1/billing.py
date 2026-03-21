"""
Circuit.AI Billing Integration

Stripe integration for subscription management and billing.
"""

import stripe
from fastapi import APIRouter, HTTPException, Depends, Request, status
from pydantic import BaseModel
import os
from loguru import logger

from .auth import get_current_user
from .models import SuccessResponse

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
stripe_webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

router = APIRouter(prefix="/billing", tags=["billing"])

# Subscription plans
SUBSCRIPTION_PLANS = {
    "free": {
        "name": "Free",
        "price_id": None,
        "requests_per_minute": 10,
        "requests_per_hour": 100,
        "requests_per_month": 1000,
        "price": 0,
        "currency": "usd"
    },
    "pro": {
        "name": "Pro",
        "price_id": os.getenv("STRIPE_PRO_PRICE_ID"),
        "requests_per_minute": 60,
        "requests_per_hour": 1000,
        "requests_per_month": 10000,
        "price": 99,
        "currency": "usd"
    },
    "enterprise": {
        "name": "Enterprise",
        "price_id": os.getenv("STRIPE_ENTERPRISE_PRICE_ID"),
        "requests_per_minute": 300,
        "requests_per_hour": 5000,
        "requests_per_month": 50000,
        "price": 999,
        "currency": "usd"
    }
}

class CreateCheckoutSessionRequest(BaseModel):
    plan: str
    success_url: str
    cancel_url: str

class CreatePortalSessionRequest(BaseModel):
    return_url: str

@router.post("/create-checkout-session", response_model=SuccessResponse)
async def create_checkout_session(
    request: CreateCheckoutSessionRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Create a Stripe checkout session for subscription.
    """
    try:
        if request.plan not in SUBSCRIPTION_PLANS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid plan"
            )
        
        plan = SUBSCRIPTION_PLANS[request.plan]
        
        if plan["price_id"] is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Free plan does not require checkout"
            )
        
        # Create or retrieve Stripe customer
        customer = await get_or_create_customer(current_user["user_id"])
        
        # Create checkout session
        checkout_session = stripe.checkout.Session.create(
            customer=customer.id,
            payment_method_types=['card'],
            line_items=[{
                'price': plan["price_id"],
                'quantity': 1,
            }],
            mode='subscription',
            success_url=request.success_url,
            cancel_url=request.cancel_url,
            metadata={
                'user_id': current_user["user_id"],
                'plan': request.plan
            }
        )
        
        return SuccessResponse(
            success=True,
            data={
                "checkout_url": checkout_session.url,
                "session_id": checkout_session.id
            }
        )
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Payment processing error"
        )
    except Exception as e:
        logger.error(f"Error creating checkout session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create checkout session"
        )

@router.post("/create-portal-session", response_model=SuccessResponse)
async def create_portal_session(
    request: CreatePortalSessionRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Create a Stripe customer portal session for subscription management.
    """
    try:
        customer = await get_or_create_customer(current_user["user_id"])
        
        portal_session = stripe.billing_portal.Session.create(
            customer=customer.id,
            return_url=request.return_url,
        )
        
        return SuccessResponse(
            success=True,
            data={
                "portal_url": portal_session.url
            }
        )
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Payment processing error"
        )
    except Exception as e:
        logger.error(f"Error creating portal session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create portal session"
        )

@router.get("/plans", response_model=SuccessResponse)
async def get_subscription_plans():
    """
    Get available subscription plans.
    """
    return SuccessResponse(
        success=True,
        data={
            "plans": SUBSCRIPTION_PLANS
        }
    )

@router.get("/subscription", response_model=SuccessResponse)
async def get_user_subscription(
    current_user: dict = Depends(get_current_user)
):
    """
    Get user's current subscription status.
    """
    try:
        customer = await get_or_create_customer(current_user["user_id"])
        
        # Get active subscriptions
        subscriptions = stripe.Subscription.list(
            customer=customer.id,
            status='active'
        )
        
        current_plan = "free"
        subscription_data = None
        
        if subscriptions.data:
            subscription = subscriptions.data[0]
            # Map Stripe price to plan
            for plan_name, plan_data in SUBSCRIPTION_PLANS.items():
                if plan_data["price_id"] == subscription.items.data[0].price.id:
                    current_plan = plan_name
                    break
            
            subscription_data = {
                "id": subscription.id,
                "status": subscription.status,
                "current_period_start": subscription.current_period_start,
                "current_period_end": subscription.current_period_end,
                "cancel_at_period_end": subscription.cancel_at_period_end
            }
        
        return SuccessResponse(
            success=True,
            data={
                "current_plan": current_plan,
                "subscription": subscription_data,
                "plan_limits": SUBSCRIPTION_PLANS[current_plan]
            }
        )
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve subscription"
        )
    except Exception as e:
        logger.error(f"Error getting subscription: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve subscription"
        )

@router.post("/webhook")
async def stripe_webhook(request: Request):
    """
    Handle Stripe webhook events.
    """
    try:
        payload = await request.body()
        sig_header = request.headers.get('stripe-signature')
        
        if not stripe_webhook_secret:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Webhook secret not configured"
            )
        
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, stripe_webhook_secret
            )
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid payload"
            )
        except stripe.error.SignatureVerificationError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid signature"
            )
        
        # Handle the event
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            await handle_checkout_completed(session)
        elif event['type'] == 'customer.subscription.updated':
            subscription = event['data']['object']
            await handle_subscription_updated(subscription)
        elif event['type'] == 'customer.subscription.deleted':
            subscription = event['data']['object']
            await handle_subscription_deleted(subscription)
        elif event['type'] == 'invoice.payment_failed':
            invoice = event['data']['object']
            await handle_payment_failed(invoice)
        
        return {"status": "success"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook processing failed"
        )

async def get_or_create_customer(user_id: str):
    """
    Get or create a Stripe customer for the user.
    """
    # In production, store customer_id in database
    # For now, create a new customer each time (not ideal)
    try:
        customer = stripe.Customer.create(
            metadata={'user_id': user_id}
        )
        return customer
    except stripe.error.StripeError as e:
        logger.error(f"Error creating customer: {e}")
        raise

async def handle_checkout_completed(session):
    """
    Handle successful checkout completion.
    """
    user_id = session['metadata']['user_id']
    plan = session['metadata']['plan']
    
    logger.info(f"Checkout completed for user {user_id}, plan {plan}")
    
    # In production, update user's plan in database
    # For now, just log the event

async def handle_subscription_updated(subscription):
    """
    Handle subscription updates.
    """
    customer_id = subscription['customer']
    logger.info(f"Subscription updated for customer {customer_id}")
    
    # In production, update user's plan in database

async def handle_subscription_deleted(subscription):
    """
    Handle subscription cancellation.
    """
    customer_id = subscription['customer']
    logger.info(f"Subscription cancelled for customer {customer_id}")
    
    # In production, downgrade user to free plan

async def handle_payment_failed(invoice):
    """
    Handle failed payment.
    """
    customer_id = invoice['customer']
    logger.warning(f"Payment failed for customer {customer_id}")
    
    # In production, send notification and potentially suspend account
