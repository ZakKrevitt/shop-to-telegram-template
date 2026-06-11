# SPECIFICATION: Shop-to-Telegram Agent

## Objective
Enable a user to enter an existing ecommerce link and create a fully functional Telegram storefront that sends checkout back to the merchant's original store.

## High-Level Architecture
1. **Scraper (`scraper.py`)**: Extracts product data (Title, Price, Description, Images, Categories, Shopify Variant IDs) from the provided URL using Shopify products JSON, JSON-LD, or OpenGraph metadata.
2. **Knowledge Base**: Stores products for semantic search (using local FAISS or simple embedding matching).
3. **Bot Engine (`bot.py`)**:
   - **TUI**: Elegant Telegram interface using custom keyboard/inline buttons.
   - **Semantic Search**: Natural language "I want something for..." handler.
   - **Cart System**: Interactive in-bot cart tracking.
   - **Checkout**: Deep-linking directly to the source store's product page or Shopify cart checkout. No Stripe Connect account, application fee, or platform-owned payment routing.
4. **Wizard (`wizard.py`)**: Interactive CLI to collect:
   - Ecommerce URL
   - Telegram Bot Token
   - Admin DMs / Controls

## Success Criteria
- Agent can run `python wizard.py` to configure the instance.
- Bot starts and correctly displays indexed products.
- Cart mechanics work end-to-end.
- Checkout links hand off to the merchant-owned ecommerce checkout.
- Verifiable by `pytest`.
