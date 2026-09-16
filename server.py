#!/usr/bin/env python3
"""EVEZ Commerce: public catalog plus optional Stripe Checkout.

Payments remain disabled unless STRIPE_SECRET_KEY is explicitly configured.
"""
import os
import time
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

try:
    import stripe
except ImportError:  # catalog-only mode remains runnable
    stripe = None

app = FastAPI(title="EVEZ Commerce", version="1.1.0")

PRODUCTS = [
    {"id": "clawbreak-api", "name": "ClawBreak API Access", "price": 29.99, "interval": "month", "description": "Adversarial AI chat and task routing."},
    {"id": "cognition-api", "name": "Cognition API Access", "price": 49.99, "interval": "month", "description": "AI-output forensics and risk scoring."},
    {"id": "research-agent", "name": "Research Agent", "price": 19.99, "interval": "month", "description": "Structured research and evidence-pack generation."},
    {"id": "digital-twin", "name": "Digital Twin Access", "price": 39.99, "interval": "month", "description": "Personal knowledge and workflow assistant."},
    {"id": "mesh-network", "name": "Mesh Network Seat", "price": 25.00, "interval": "month", "description": "Agent coordination and diagnostics."},
    {"id": "guard-security", "name": "Guard Security Monitor", "price": 14.99, "interval": "month", "description": "Service health and abuse monitoring."},
]
PRODUCT_BY_ID = {product["id"]: product for product in PRODUCTS}
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:8904")
if stripe and STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY


class CheckoutRequest(BaseModel):
    product_id: str
    email: Optional[str] = None
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None


@app.get("/health")
def health():
    return {
        "status": "ok",
        "version": app.version,
        "service": "evez-commerce",
        "payments": "enabled" if stripe and STRIPE_SECRET_KEY else "disabled",
        "ts": int(time.time()),
    }


@app.get("/")
def root():
    return {
        "service": "EVEZ Commerce",
        "version": app.version,
        "endpoints": ["/health", "/products", "/products/{id}", "/checkout", "/webhooks/stripe"],
    }


@app.get("/products")
def products():
    return {"products": PRODUCTS, "count": len(PRODUCTS), "mrr_potential": round(sum(p["price"] for p in PRODUCTS), 2)}


@app.get("/products/{product_id}")
def product(product_id: str):
    product = PRODUCT_BY_ID.get(product_id)
    if not product:
        raise HTTPException(404, "product not found")
    return product


@app.post("/checkout")
def checkout(request: CheckoutRequest):
    product = PRODUCT_BY_ID.get(request.product_id)
    if not product:
        raise HTTPException(404, "product not found")
    if not stripe or not STRIPE_SECRET_KEY:
        raise HTTPException(503, "payments are not configured; catalog mode is active")
    mode = "subscription" if product["interval"] == "month" else "payment"
    params = {
        "mode": mode,
        "line_items": [{
            "price_data": {
                "currency": "usd",
                "product_data": {"name": product["name"], "description": product["description"]},
                "unit_amount": round(product["price"] * 100),
                **({"recurring": {"interval": product["interval"]}} if mode == "subscription" else {}),
            },
            "quantity": 1,
        }],
        "success_url": request.success_url or f"{PUBLIC_BASE_URL}/success?session_id={{CHECKOUT_SESSION_ID}}",
        "cancel_url": request.cancel_url or f"{PUBLIC_BASE_URL}/cancel",
        "metadata": {"product_id": product["id"]},
    }
    if request.email:
        params["customer_email"] = str(request.email)
    session = stripe.checkout.Session.create(**params)
    return {"checkout_url": session.url, "session_id": session.id, "product_id": product["id"]}


@app.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    if not stripe or not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(503, "Stripe webhooks are not configured")
    payload = await request.body()
    signature = request.headers.get("stripe-signature")
    if not signature:
        raise HTTPException(400, "missing Stripe signature")
    try:
        event = stripe.Webhook.construct_event(payload, signature, STRIPE_WEBHOOK_SECRET)
    except ValueError as exc:
        raise HTTPException(400, "invalid payload") from exc
    except stripe.error.SignatureVerificationError as exc:
        raise HTTPException(400, "invalid signature") from exc
    # Payment fulfillment must be implemented per product; never grant access merely
    # because a client called this endpoint. The event is verified by Stripe first.
    return {"received": True, "event_id": event["id"], "type": event["type"]}


@app.get("/success")
def success(session_id: Optional[str] = None):
    return {"status": "payment_received", "session_id": session_id, "message": "Thank you. Fulfillment will follow after webhook verification."}


@app.get("/cancel")
def cancel():
    return {"status": "cancelled", "message": "No charge was created."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", "8904")))
