# shop-to-telegram-template

A Python template for turning any online shop into a Telegram storefront bot — scrape products, let users browse and search, add to cart, and check out, all inside Telegram.

---

## What it does

- Scrapes (or loads) product data from any shop URL
- Serves products as interactive Telegram messages with inline buttons
- Lets users search, browse, add to cart, and initiate checkout
- Stores product data as JSON for easy editing or re-use

Built as a reusable template — swap in your own scraper, plug in your shop URL, and you have a working Telegram store in minutes.

---

## Project structure

```
.
├── bot.py           # Core bot logic: ShopEngine, CartManager, message formatting
├── scraper.py       # ShopScraper base class + Product dataclass
├── products.json    # Scraped product data (JSON — edit or regenerate)
├── REQUIREMENTS.txt # Python dependencies
└── shop-to-telegram/  # Extended bot implementation (Telegram framework integration)
```

---

## How it works

1. `scraper.py` defines a `ShopScraper` class and `Product` dataclass. The base class returns mock data — replace the `scrape()` method with real Playwright or BeautifulSoup logic to pull products from any shop.

2. `products.json` stores the scraped product catalog. The bot loads from this file at startup.

3. `bot.py` contains:
   - `ShopEngine` — searches products, looks up by ID
   - `CartManager` — per-user in-memory cart (user_id → product_id → quantity)
   - Inline keyboard markup helpers for product cards and cart actions
   - Framework-agnostic message formatting (plug into python-telegram-bot or any other lib)

---

## Quickstart

### 1. Install dependencies

```bash
pip install -r REQUIREMENTS.txt
playwright install chromium  # only needed if using Playwright for scraping
```

### 2. Set your bot token

```bash
export TELEGRAM_BOT_TOKEN=your_token_here
```

Get a token from [@BotFather](https://t.me/BotFather) on Telegram.

### 3. Scrape your shop (or edit products.json directly)

Edit `scraper.py` and point `ShopScraper` at your shop URL, then run:

```bash
python scraper.py
```

Or manually populate `products.json` with your product data.

### 4. Run the bot

```bash
python bot.py
```

---

## Product schema

Each product in `products.json` follows this shape:

```json
{
  "id": "p1",
  "name": "Product Name",
  "description": "Short description",
  "price": 89.00,
  "currency": "USD",
  "image_url": "https://...",
  "url": "https://yourshop.com/products/...",
  "tags": ["tag1", "tag2"]
}
```

---

## Customizing

- **New shop**: subclass `ShopScraper` and implement `scrape()` using Playwright or BeautifulSoup
- **Payment**: wire the `checkout` callback to Stripe, Shopify, or your payment provider
- **Persistent carts**: replace the in-memory `CartManager` with Redis or a database
- **Product images**: `bot.py` includes `format_product_caption()` — pair it with `sendPhoto` for rich product cards

---

## Dependencies

| Package | Purpose |
|---|---|
| python-telegram-bot | Telegram Bot API wrapper |
| requests | HTTP requests |
| beautifulsoup4 | HTML scraping |
| playwright | Headless browser scraping |

---

## License

MIT
