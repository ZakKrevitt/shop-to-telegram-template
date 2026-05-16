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
- `.env` — your bot token and shop config

## Customizing

- Implement `ShopScraper.scrape()` to pull real products from your shop
- Wire the checkout callback to Stripe, Shopify, or your payment provider
- Swap CartManager for Redis/database for persistent carts

## License

MIT
