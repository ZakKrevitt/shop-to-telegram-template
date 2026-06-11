# create-tg-shop

Turn an ecommerce link into a Telegram storefront bot. The bot scrapes a starter product catalog, lets customers browse/search/add to cart in Telegram, then sends checkout back to the merchant's original store.

## Payment model

This template does not route sales through a platform Stripe Connect account, create connected accounts, or collect an application fee.

Checkout works by deep-linking to the source store:

- Shopify products with variant IDs link to `SHOP_URL/cart/{variant_id}:{qty}`
- Other stores link to the product page or configured `SHOP_URL`
- If the merchant's own Shopify checkout uses Stripe, Shopify Payments, PayPal, or another processor, that happens inside the merchant-owned checkout

## Quickstart

```bash
git clone https://github.com/ZakKrevitt/shop-to-telegram-template.git
cd shop-to-telegram-template
python3 -m venv .venv
source .venv/bin/activate
pip install -r REQUIREMENTS.txt
python wizard.py
python bot.py
```

The wizard asks for:

- Ecommerce link
- Telegram bot token from `@BotFather`
- Shop name
- Admin Telegram handle for wholesale inquiries

It writes `.env`, scrapes products into `products.json`, and leaves the bot ready to run.

## One-line installer

```bash
curl -fsSL https://raw.githubusercontent.com/ZakKrevitt/shop-to-telegram-template/main/install.sh | bash
```

## What it sets up

- `wizard.py` - collects the ecommerce link and Telegram config
- `scraper.py` - best-effort Shopify, JSON-LD, and OpenGraph product scraper
- `products.json` - product catalog used by the bot
- `bot.py` - Telegram storefront with categories, product cards, cart, source-store checkout links, search, and wholesale inquiries
- `.env` - local bot/shop configuration

## Environment variables

```bash
BOT_TOKEN=123456:telegram-token
SHOP_URL=https://merchant-shop.com
SHOP_NAME=Merchant Shop
ADMIN_HANDLE=@merchant_admin
BANNER_IMG=/absolute/path/to/banner.jpg
```

`TELEGRAM_BOT_TOKEN` is still accepted for older local installs, but new setup writes `BOT_TOKEN`.

## Scraping manually

```bash
python scraper.py https://merchant-shop.com --output products.json
```

The scraper tries Shopify's public `products.json` endpoint first, then falls back to product metadata on the provided page. If no products are detected, edit `products.json` manually or try a more specific collection/product URL.

## Customizing

- Replace `products.json` with a hand-curated catalog if scraping is incomplete
- Customize Telegram copy/buttons in `bot.py`
- Add persistence for carts if the bot needs multi-device or long-lived sessions
- Add fulfillment/order webhooks in the merchant's own ecommerce platform

## License

MIT
