# OpenClaw Commerce Workflows

These workflows keep OpenClaw valuable without turning it into an expensive polling loop. Deterministic work belongs in the commerce service or a small worker; OpenClaw is reserved for judgment, exception review, and weekly prioritization.

## Event workflows

### `stripe.webhook.received`

1. Receive the normalized event from `POST /webhooks/stripe`.
2. Let the commerce service verify the Stripe signature and deduplicate the event.
3. Read the fulfillment queue item. Never treat a browser redirect as payment proof.
4. If a tested product adapter exists, provision or revoke access idempotently. Otherwise keep `manual_review` and notify the operator.
5. Record the product, event type, customer identifier, campaign attribution, and outcome without storing card data.

### `catalog.changed`

1. Validate `catalog.json` and product IDs.
2. Regenerate affected static product pages.
3. Run broken-link, accessibility, and performance checks.
4. Create a review artifact rather than auto-publishing an unreviewed visual or pricing change.

### `campaign.requested`

1. Select a product and audience from `campaigns.json`.
2. Generate channel variants only from approved angle, audience, price, and CTA facts.
3. Generate UTM links with `utm.py`.
4. Put drafts into a review queue. Public posting remains draft-first.

## Schedules

- **Daily:** reconcile Stripe state once or twice; surface payment failures, refunds, duplicate events, and unfulfilled queue items.
- **Weekly:** summarize checkout starts, completed payments, refunds, and retention by product and channel; recommend a small test backlog.
- **On demand:** build pages, validate links, and run a performance trace after a material change.

Avoid minute-level Stripe polling, hourly full-catalog regeneration, repeated model introspection, automatic paid ads, and automatic spending on image generation.

## Safety gates

- `COMMERCE_MODE` must match the Stripe key prefix (`test` with `sk_test_`, `live` with `sk_live_`).
- Live launch requires a confirmed live account and a verified webhook secret.
- A product cannot be marked provisionable without a tested adapter and refund/revocation path.
- A page cannot expose a test-mode link.
- Refunds, price changes, account ownership changes, and billing changes require operator confirmation.

## Success measures

Measure qualified landing-page clicks, checkout starts, completed payments, refunds, support load, and paid retention by product and channel. Prefer the smallest set of products and campaigns that demonstrate paid demand; pause the rest rather than increasing spend blindly.
