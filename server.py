#!/usr/bin/env python3
"""EVEZ Commerce control plane.

Catalog is always available. Stripe Checkout and webhook processing fail closed
unless the configured key, webhook secret, and COMMERCE_MODE agree.
"""
import hashlib
import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

try:
    import stripe
except ImportError:
    stripe = None

BASE = Path(os.getenv("COMMERCE_BASE", Path(__file__).resolve().parent))
CATALOG_PATH = Path(os.getenv("CATALOG_PATH", BASE / "catalog.json"))
DB_PATH = Path(os.getenv("COMMERCE_DB", BASE / "commerce.db"))
COMMERCE_MODE = os.getenv("COMMERCE_MODE", "catalog").lower()
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:8904").rstrip("/")

with CATALOG_PATH.open(encoding="utf-8") as catalog_file:
    CATALOG = json.load(catalog_file)
PRODUCTS = CATALOG["products"]
PRODUCT_BY_ID = {product["id"]: product for product in PRODUCTS}

if stripe and STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY


def configured_stripe_mode() -> str:
    if not STRIPE_SECRET_KEY:
        return "unconfigured"
    if STRIPE_SECRET_KEY.startswith("sk_live_"):
        return "live"
    if STRIPE_SECRET_KEY.startswith("sk_test_"):
        return "test"
    return "unknown"


def stripe_ready() -> bool:
    key_mode = configured_stripe_mode()
    if not stripe or key_mode in {"unconfigured", "unknown"}:
        return False
    if COMMERCE_MODE not in {"test", "live"} or COMMERCE_MODE != key_mode:
        return False
    return bool(STRIPE_WEBHOOK_SECRET)


def db() -> sqlite3.Connection:
    connection = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("""CREATE TABLE IF NOT EXISTS stripe_events (
        event_id TEXT PRIMARY KEY,
        event_type TEXT NOT NULL,
        payload_sha256 TEXT NOT NULL,
        received_at TEXT NOT NULL,
        processed INTEGER NOT NULL DEFAULT 0
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS fulfillment_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id TEXT NOT NULL UNIQUE,
        product_id TEXT,
        customer_email TEXT,
        status TEXT NOT NULL,
        reason TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )""")
    connection.commit()
    return connection


DB = db()
app = FastAPI(title="EVEZ Commerce", version="1.2.0")


class CheckoutRequest(BaseModel):
    product_id: str
    email: Optional[str] = None
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None


@app.get("/health")
def health():
    key_mode = configured_stripe_mode()
    return {
        "status": "ok",
        "version": app.version,
        "service": "evez-commerce",
        "commerce_mode": COMMERCE_MODE,
        "stripe_key_mode": key_mode,
        "stripe_ready": stripe_ready(),
        "fulfillment": "manual_review_until_adapter_verified",
        "product_count": len(PRODUCTS),
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
    return {
        "currency": CATALOG["currency"],
        "products": PRODUCTS,
        "count": len(PRODUCTS),
        "mrr_potential": round(sum(product["price_cents"] for product in PRODUCTS) / 100, 2),
    }


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
    if not stripe_ready():
        raise HTTPException(503, "Stripe is not configured for the selected commerce mode")
    params = {
        "mode": "subscription" if product["interval"] == "month" else "payment",
        "line_items": [{"price_data": {"currency": CATALOG["currency"], "product_data": {"name": product["name"], "description": product["description"]}, "unit_amount": product["price_cents"], "recurring": {"interval": product["interval"]}}, "quantity": 1}],
        "success_url": request.success_url or f"{PUBLIC_BASE_URL}/success?session_id={{CHECKOUT_SESSION_ID}}",
        "cancel_url": request.cancel_url or f"{PUBLIC_BASE_URL}/cancel",
        "metadata": {"product_id": product["id"], "commerce_mode": COMMERCE_MODE},
    }
    if request.email:
        params["customer_email"] = request.email
    session = stripe.checkout.Session.create(**params)
    return {"checkout_url": session.url, "session_id": session.id, "product_id": product["id"], "mode": COMMERCE_MODE}


def enqueue_fulfillment(event_id: str, event_type: str, event_object: dict) -> None:
    metadata = event_object.get("metadata") or {}
    product_id = metadata.get("product_id") or metadata.get("evez_product_id")
    customer_details = event_object.get("customer_details") or {}
    email = customer_details.get("email") or event_object.get("customer_email")
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    DB.execute("""INSERT OR IGNORE INTO fulfillment_queue
        (event_id, product_id, customer_email, status, reason, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)""", (event_id, product_id, email, "manual_review", f"verified {event_type}; no adapter enabled", now, now))


@app.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    if not stripe_ready():
        raise HTTPException(503, "Stripe webhook processing is not configured for the selected commerce mode")
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

    event_id = event["id"]
    event_type = event["type"]
    digest = hashlib.sha256(payload).hexdigest()
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    inserted = DB.execute("INSERT OR IGNORE INTO stripe_events (event_id, event_type, payload_sha256, received_at) VALUES (?, ?, ?, ?)", (event_id, event_type, digest, now)).rowcount
    if inserted:
        event_object = event.get("data", {}).get("object", {})
        if event_type in {"checkout.session.completed", "invoice.paid", "customer.subscription.updated", "customer.subscription.deleted", "charge.refunded", "invoice.payment_failed"}:
            enqueue_fulfillment(event_id, event_type, event_object)
        DB.execute("UPDATE stripe_events SET processed = 1 WHERE event_id = ?", (event_id,))
        DB.commit()
    return {"received": True, "event_id": event_id, "type": event_type, "duplicate": not bool(inserted)}


@app.get("/success")
def success(session_id: Optional[str] = None):
    return {"status": "payment_received", "session_id": session_id, "message": "Payment confirmation is processed by the verified Stripe webhook."}


@app.get("/cancel")
def cancel():
    return {"status": "cancelled", "message": "No charge was created."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", "8904")))
