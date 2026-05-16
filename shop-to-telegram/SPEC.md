# SPECIFICATION: Shop-to-Telegram Agent

## Objective
Enable a user to show this repository to an AI agent (Hermes, Claude Code, Codex) and have that agent deploy a fully functional Telegram storefront based on an existing online shop URL.

## High-Level Architecture
1. **Scraper (`scraper.py`)**: Uses Firecrawl or similar to extract product data (Title, Price, Description, Images, Categories) from the provided URL.
2. **Knowledge Base**: Stores products for semantic search (using local FAISS or simple embedding matching).
3. **Bot Engine (`bot.py`)**:
   - **TUI**: Elegant Telegram interface using custom keyboard/inline buttons.
   - **Semantic Search**: Natural language "I want something for..." handler.
   - **Cart System**: Interactive in-bot cart tracking.
   - **Checkout**: Deep-linking directly to the source store's checkout page or a DM to admin.
4. **Wizard (`wizard.py`)**: Interactive CLI to collect:
   - Store URL
   - Telegram Bot Token
   - AI Provider Preference (Nous, OpenAI, Anthropic)
   - Admin DMs / Controls

## Success Criteria
- Agent can run `python wizard.py` to configure the instance.
- Bot starts and correctly displays indexed products.
- Cart mechanics work end-to-end.
- Verifiable by `pytest`.
