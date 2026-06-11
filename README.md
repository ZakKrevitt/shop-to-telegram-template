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
- Optional admin Telegram handle for wholesale inquiries

It writes `.env`, scrapes products into `products.json`, scrapes website section links into `sections.json`, and leaves the bot ready to run.

## One-line installer

```bash
curl -fsSL https://raw.githubusercontent.com/ZakKrevitt/shop-to-telegram-template/main/install.sh | bash
```

## One-shot Railway deploy

For each new client, create a Telegram bot with `@BotFather`, get the client's ecommerce link, then run:

```bash
python scripts/deploy_client.py \
  --shop-url "https://merchant-shop.com" \
  --project-name "merchant-shop-bot" \
  --shop-name "Merchant Shop"
```

The script prompts for the bot token securely. For automation, pass `--bot-token` or set `BOT_TOKEN` in the shell environment.

The deploy script:

- Copies the template into a temporary client build directory
- Scrapes `products.json` and `sections.json` from the ecommerce link
- Creates a new Railway project and bot service
- Stores `BOT_TOKEN`, `SHOP_URL`, `SHOP_NAME`, and optional `ADMIN_HANDLE` as Railway variables
- Deploys the bot with `railway up --detach`

The bot token is never committed to git. Railway runs the service as an always-on worker using `railway.json`; no public domain is required because the bot connects outbound to Telegram.

Prerequisites:

- Railway CLI installed and logged in with `railway login`
- A Telegram bot token from `@BotFather`
- The ecommerce link to scrape

Use `--dry-run` to print the Railway commands without creating a project.

## What it sets up

- `wizard.py` - collects the ecommerce link and Telegram config
- `scraper.py` - best-effort Shopify, JSON-LD, and OpenGraph product scraper
- `products.json` - product catalog used by the bot
- `sections.json` - optional website section links surfaced in the bot
- `bot.py` - Telegram storefront with curated categories, product cards, images, variants, cart, source-store checkout links, per-user language settings, search, and wholesale inquiries
- `assets/start-banner.png` - default start-screen banner image
- `.env` - local bot/shop configuration
- `railway.json` - always-on Railway worker config
- `scripts/deploy_client.py` - one-command per-client Railway deployment

## Environment variables

```bash
BOT_TOKEN=123456:telegram-token
SHOP_URL=https://merchant-shop.com
SHOP_NAME=Merchant Shop
ADMIN_HANDLE=@merchant_admin
BANNER_IMG=/absolute/path/to/banner.jpg
DEFAULT_LANGUAGE=en
```

`ADMIN_HANDLE` can be omitted; the bot hides wholesale inquiry actions when it is not set. `BANNER_IMG` is optional and defaults to `assets/start-banner.png`. `DEFAULT_LANGUAGE` can be `en` or `de`; users can still adjust their own language from the bot menu. `TELEGRAM_BOT_TOKEN` is still accepted for older local installs, but new setup writes `BOT_TOKEN`.

## Scraping manually

```bash
python scraper.py https://merchant-shop.com --output products.json --sections-output sections.json
```

The scraper tries Shopify's public `products.json` endpoint first, then falls back to product metadata on the provided page. If no products are detected, edit `products.json` manually or try a more specific collection/product URL.

## Safety guardrails

The template does not rename restricted products to bypass platform rules. It keeps the scraped source catalog auditable, then filters restricted/research-compound keyword matches out of Telegram category menus, search, product detail, variant selection, cart, and checkout callbacks. If any restricted products are detected, the broad start-menu store link is hidden; product-specific source-store links remain available only for visible products.

## Optional semantic search

The hosted default uses lightweight keyword search. To enable semantic search locally or in a custom Railway build, install the optional packages and set `ENABLE_SEMANTIC_SEARCH=true`:

```bash
pip install -r requirements-semantic.txt
```

## Customizing

- Replace `products.json` with a hand-curated catalog if scraping is incomplete
- Customize Telegram copy/buttons in `bot.py`
- Add persistence for carts if the bot needs multi-device or long-lived sessions
- Add fulfillment/order webhooks in the merchant's own ecommerce platform

## License

MIT
