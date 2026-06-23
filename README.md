# shop-to-telegram-template

Turn any ecommerce link into a Telegram storefront bot. The bot scrapes a
product catalog, lets customers browse by category, search, and add to a cart
inside Telegram, then hands checkout back to the merchant's own store.

Nothing in this template is tied to a specific shop or product vertical —
categories, copy, and branding are all derived from the store or set via
environment variables. Point it at a clothing shop, an electronics store, or a
coffee roaster and it adapts.

## How it works

```
ecommerce URL ──▶ scraper.py ──▶ products.json / sections.json ──▶ bot.py ──▶ Telegram
                                                                        │
                                                       checkout deep-link back to store
```

- **Scraper** tries Shopify's public `/products.json` endpoint first (richest
  data: variants, images, options), then falls back to JSON-LD and OpenGraph
  product metadata on the page.
- **Categories** are derived from the store's own taxonomy (Shopify
  `product_type`, then tags) — no hard-coded verticals.
- **Checkout** deep-links to the source store. Shopify carts use
  `SHOP_URL/cart/{variant_id}:{qty}`; other stores link to the product page.
  Payment happens entirely inside the merchant's own checkout — no platform
  Stripe account, connected accounts, or application fees.

## Bot features

- Start screen with banner image, dynamic category grid, "All Items", cart,
  site sections, language switcher, and an "Open Store" link
- Product cards with image, price, description, and variant options
- Variant + quantity selectors feeding an in-bot cart
- Multi-language UI (English, German, Spanish, Portuguese, Dutch)
- Keyword search out of the box; optional semantic search
- Optional wholesale inquiry flow (enabled only when `ADMIN_HANDLE` is set)
- Optional compliance keyword filter for regulated stores

## Quickstart (local)

```bash
git clone https://github.com/ZakKrevitt/shop-to-telegram-template.git
cd shop-to-telegram-template
python3 -m venv .venv
source .venv/bin/activate
pip install -r REQUIREMENTS.txt
python wizard.py        # asks for ecommerce link + bot token, then scrapes
python bot.py
```

The wizard writes `.env`, scrapes `products.json` and `sections.json`, and
leaves the bot ready to run. See `.env.example` for every supported variable.

## Deploy on Railway

There are two ways to get a hosted, always-on bot.

### A. Self-serve via the deploy API (no local CLI)

The bot **scrapes its catalog on boot** when `products.json` is empty and
`SHOP_URL` is set. That means you can create a Railway service straight from
this GitHub repo with just two variables and it comes up populated:

| Variable | Value |
| --- | --- |
| `BOT_TOKEN` | token from `@BotFather` |
| `SHOP_URL` | the store to mirror |
| `SHOP_NAME` | (optional) display name |

This is what the companion self-serve front-end automates: a user submits a bot
token + store URL, and a serverless function provisions a Railway service from
this repo via the Railway GraphQL API.

### B. One-shot CLI deploy

```bash
python scripts/deploy_client.py \
  --shop-url "https://merchant-shop.com" \
  --project-name "merchant-shop-bot" \
  --shop-name "Merchant Shop"
```

The script copies the template into a temp build, scrapes the catalog, creates
a Railway project + service, stores the variables, and runs `railway up`. The
bot token is read securely and never committed. Use `--dry-run` to preview the
Railway commands. Requires the Railway CLI logged in (`railway login`).

## Repository layout

| Path | Purpose |
| --- | --- |
| `bot.py` | Telegram storefront (menus, cards, cart, search, languages) |
| `scraper.py` | Shopify / JSON-LD / OpenGraph product + section scraper |
| `wizard.py` | Interactive local setup (writes `.env`, scrapes catalog) |
| `scripts/deploy_client.py` | One-command per-client Railway deploy |
| `products.json` | Product catalog the bot serves (sample shipped) |
| `sections.json` | Info-page links shown in "Site Sections" |
| `assets/start-banner.png` | Default start-screen banner |
| `railway.json` / `Dockerfile` | Always-on Railway worker config |
| `.env.example` | All supported environment variables |

## Environment variables

Required: `BOT_TOKEN`, `SHOP_URL`. Recommended: `SHOP_NAME`. Everything else is
optional — see `.env.example`:

- `ADMIN_HANDLE` — enables the wholesale inquiry flow (hidden when unset)
- `SHOP_TAGLINE` — overrides the welcome blurb on the start screen
- `SHOP_BADGES` — a trust-badge strip under the welcome text
- `BANNER_IMG` — path or URL to the start banner (defaults to the bundled image)
- `DEFAULT_LANGUAGE` — `en` | `de` | `es` | `pt` | `nl` (users can change it in-bot)
- `ENABLE_SEMANTIC_SEARCH` — `1` to use sentence-transformers + FAISS
- `RESTRICTED_KEYWORDS` — comma-separated terms to hide from the bot (regulated stores)

## Scraping manually

```bash
python scraper.py https://merchant-shop.com --output products.json --sections-output sections.json
```

If no products are detected, edit `products.json` by hand or try a more specific
collection/product URL.

## Optional semantic search

The default uses lightweight keyword search. To enable semantic search, install
the optional packages and set `ENABLE_SEMANTIC_SEARCH=1`:

```bash
pip install -r requirements-semantic.txt
```

## Compliance filter (optional)

For regulated stores, set `RESTRICTED_KEYWORDS` to a comma-separated list. Any
product whose title, description, tags, or categories match a keyword is hidden
from category menus, search, product detail, cart, and checkout. When the filter
hides anything, the broad start-menu store link is suppressed. The catalog in
`products.json` stays auditable — products are filtered, never renamed.

## Tests

```bash
python -m pytest
python -m compileall bot.py scraper.py wizard.py scripts/deploy_client.py
```

## License

MIT
