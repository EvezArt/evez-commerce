# EVEZ Commerce

A small, installable commerce service for EVEZ digital products. It exposes a public product catalog immediately and enables Stripe Checkout only when payment credentials are explicitly configured.

## Products

| Product | Price | Delivery status |
|---|---:|---|
| ClawBreak API Access | $29.99/month | Configure fulfillment target |
| Cognition API Access | $49.99/month | Configure fulfillment target |
| Research Agent | $19.99/month | Configure fulfillment target |
| Digital Twin Access | $39.99/month | Configure fulfillment target |
| Mesh Network Seat | $25.00/month | Configure fulfillment target |
| Guard Security Monitor | $14.99/month | Configure fulfillment target |

## Run locally

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python server.py
```

The service listens on `http://127.0.0.1:8904` by default. For a public deployment, put it behind HTTPS and an access-controlled reverse proxy.

## API

```bash
curl http://localhost:8904/health
curl http://localhost:8904/products
curl http://localhost:8904/products/cognition-api
```

`POST /checkout` accepts `{ "product_id": "cognition-api", "email": "buyer@example.com" }`. It returns HTTP 503 in catalog-only mode and creates a Stripe Checkout Session only when both `STRIPE_SECRET_KEY` and the `stripe` package are configured.

`POST /webhooks/stripe` verifies `Stripe-Signature` using `STRIPE_WEBHOOK_SECRET`. It acknowledges verified events but deliberately does not grant access automatically until product-specific fulfillment is configured.

## Payment configuration

Set these environment variables only on the server, never in Git:

```bash
export STRIPE_SECRET_KEY=sk_test_or_sk_live_...
export STRIPE_WEBHOOK_SECRET=whsec_...
export PUBLIC_BASE_URL=https://your-domain.example
python server.py
```

Use Stripe test mode first. Do not accept live payments until the product fulfillment behavior, refund path, support contact, and privacy notice have been verified.

## Safety and operational notes

Catalog mode is safe to deploy without payment credentials. The service does not claim that a payment succeeded based on a client redirect; payment confirmation must come from a verified Stripe webhook. Add authentication, rate limiting, persistent order records, and fulfillment handlers before treating it as production-ready.
