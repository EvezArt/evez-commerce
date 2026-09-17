# EVEZ Commerce

EVEZ Commerce is the small control plane behind the EVEZ catalog. It keeps a normalized product registry, exposes a public catalog, creates Stripe Checkout Sessions when explicitly configured, verifies Stripe webhook signatures, deduplicates events, and queues fulfillment for manual review until a product-specific adapter has been tested.

## Product registry

The canonical catalog is [`catalog.json`](catalog.json). It is shared by the API and should be copied into the landing-page build as data rather than retyped in multiple places.

## Run locally

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
COMMERCE_MODE=catalog python server.py
```

Catalog mode requires no payment credentials and serves on `http://127.0.0.1:8904` by default.

## Stripe modes

The service fails closed unless the selected mode agrees with the secret-key prefix:

- `COMMERCE_MODE=catalog`: catalog only; checkout and webhooks return HTTP 503.
- `COMMERCE_MODE=test` with `sk_test_...` and a test webhook secret: test Checkout and webhooks.
- `COMMERCE_MODE=live` with `sk_live_...` and a live webhook secret: live Checkout and webhooks.

Never place keys in Git or client-side code. Set `PUBLIC_BASE_URL` to the HTTPS origin used in Checkout redirects.

```bash
COMMERCE_MODE=test \
STRIPE_SECRET_KEY=sk_test_... \
STRIPE_WEBHOOK_SECRET=whsec_... \
PUBLIC_BASE_URL=https://catalog.example \
python server.py
```

## API

- `GET /health` reports the selected mode, detected key mode, Stripe readiness, and fulfillment state without exposing secrets.
- `GET /products` returns the normalized catalog.
- `POST /checkout` accepts `{ "product_id": "cognition-api", "email": "buyer@example.com" }`.
- `POST /webhooks/stripe` verifies `Stripe-Signature`, writes an idempotent event ledger, and queues recognized events for fulfillment review.

## Fulfillment boundary

The webhook handler deliberately does not grant access automatically. Each product needs a verified adapter and a tested revocation/refund path before its queue status can move from `manual_review` to `provisioned`. This prevents false fulfillment from client redirects, duplicate webhooks, or unsupported product claims.

## Low-cost operation

Keep deterministic work in the service or a small worker: catalog validation, Stripe reconciliation once or twice daily, UTM generation, link checks, and performance checks. Use OpenClaw judgment only for exception review, positioning decisions, and weekly campaign synthesis. Do not poll Stripe every few minutes or regenerate the whole catalog on every run.
