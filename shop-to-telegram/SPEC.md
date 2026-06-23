# SPECIFICATION: Shop-to-Telegram Agent

## Objective
Let a user enter an existing ecommerce link (plus a Telegram bot token) and get a
fully functional, hosted Telegram storefront that sends checkout back to the
merchant's original store. Nothing is hard-coded to a specific shop or vertical.

## High-Level Architecture
1. **Scraper (`scraper.py`)**: Extracts product data (title, price, description,
   images, categories, Shopify variant IDs, options/variants) from the provided
   URL using Shopify `products.json`, then JSON-LD, then OpenGraph metadata.
   Categories come from the store's own taxonomy (`product_type` → tags), never a
   fixed vertical list.
2. **Bot Engine (`bot.py`)**:
   - **UI**: Telegram inline-keyboard storefront — banner start screen, dynamic
     category grid, product cards, variant/quantity selectors, site sections,
     language switcher.
   - **Catalog bootstrap**: on boot, if `products.json` is empty and `SHOP_URL`
     is set, the bot scrapes the store itself — so a deploy needs only env vars.
   - **Search**: keyword by default; optional semantic search (FAISS).
   - **Cart**: interactive in-bot cart.
   - **Checkout**: deep-links to the source store (`/cart/{variant}:{qty}` for
     Shopify, else the product page). No Stripe Connect, application fee, or
     platform-owned payment routing.
   - **Config-driven**: name, tagline, badges, banner, default language, and an
     optional compliance keyword filter are all environment variables.
3. **Wizard (`wizard.py`)**: Interactive CLI to collect ecommerce URL, bot token,
   shop name, and optional admin handle; writes `.env` and scrapes the catalog.
4. **Provisioning**:
   - **Self-serve (front-end + API)**: a serverless function provisions a Railway
     service straight from this GitHub repo via the Railway GraphQL API, setting
     `BOT_TOKEN` / `SHOP_URL` / `SHOP_NAME`. The bot scrapes on boot.
   - **CLI (`scripts/deploy_client.py`)**: one-command client provisioning that
     creates a Railway project/service, scrapes the catalog into the build,
     stores secrets as service variables, and runs the bot as an always-on worker.

## Success Criteria
- `python wizard.py` configures a local instance; `python bot.py` runs it.
- The bot renders scraped products with working categories, cart, and checkout.
- Checkout links hand off to the merchant-owned ecommerce checkout.
- A new client bot can be created and hosted on Railway from just a bot token +
  ecommerce link, with no shop-specific code changes.
- Verifiable by `pytest`.
