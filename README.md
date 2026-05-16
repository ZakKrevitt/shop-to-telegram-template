# create-tg-shop

Turn any online shop into a Telegram storefront bot — scrape products, let users browse, add to cart, and checkout, all inside Telegram.

## Quickstart

**Python (pip):**
```bash
pip install create-tg-shop
create-tg-shop
```

**Node (npx) — no install needed:**
```bash
npx create-tg-shop
```

The wizard scaffolds a project, asks for your Telegram bot token and shop URL, installs dependencies, and gets you running in under a minute.

## What it sets up

- `bot.py` — ShopEngine + CartManager + Telegram message formatting
- `scraper.py` — base scraper class (plug in Playwright or BeautifulSoup)
- `products.json` — product catalog (edit directly or regenerate via scraper)
- `stripe_connect.py` — Stripe Connect monetization helpers
- `.env` — your bot token and shop config

## Stripe Connect Monetization

This template now includes a starter Stripe Connect integration.

The intended model is:

1. Merchants connect their own Stripe account
2. Buyers checkout through Stripe-hosted Checkout
3. Funds go directly to the merchant
4. Your platform automatically keeps a fee

This uses Stripe Connect destination charges + application fees.

### Install

```bash
pip install stripe
```

### Environment Variables

```bash
STRIPE_SECRET_KEY=sk_test_...
TG_SHOP_PLATFORM_FEE_BPS=500
TG_SHOP_SUCCESS_URL=https://your-domain.com/success?session_id={CHECKOUT_SESSION_ID}
TG_SHOP_CANCEL_URL=https://your-domain.com/cancel
```

`500` basis points = 5% platform fee.

### Example Usage

```python
from bot import ShopEngine
from stripe_connect import create_checkout_session_for_connected_account

engine = ShopEngine("products.json")

checkout_url = create_checkout_session_for_connected_account(
    cart={"p1": 1, "p2": 2},
    products=engine.products,
    connected_account_id="acct_123",
    customer_telegram_id=123456789,
)

print(checkout_url)
```

## Future Direction

This repo can evolve into:

- Telegram-native commerce platform
- Hosted SaaS for creators and small brands
- Stripe Marketplace App
- AI-powered social commerce layer
- Multi-provider payment platform

## Customizing

- Implement `ShopScraper.scrape()` to pull real products from your shop
- Wire Telegram callbacks into a real bot framework
- Add Stripe OAuth onboarding flow
- Add persistent carts via Redis/Postgres
- Add webhook handling for refunds and order fulfillment

## License

MIT
