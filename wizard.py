#!/usr/bin/env python3
"""Configure a shop-to-telegram bot from one ecommerce link."""

import argparse
import sys
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import urlparse

from scraper import ShopScraper, save_products

ROOT = Path(__file__).resolve().parent
DEFAULT_PRODUCTS_FILE = ROOT / "products.json"
DEFAULT_ENV_FILE = ROOT / ".env"


def derive_shop_name(shop_url: str) -> str:
    host = urlparse(shop_url).netloc or shop_url
    host = host.removeprefix("www.")
    name = host.split(".")[0].replace("-", " ").replace("_", " ").strip()
    return name.title() or "My Shop"


def _quote_env_value(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    if any(char.isspace() for char in value) or "#" in value:
        return '"' + value.replace('"', '\\"') + '"'
    return value


def write_env_file(
    env_file: Path,
    *,
    bot_token: str,
    shop_url: str,
    shop_name: str,
    admin_handle: str = "",
) -> None:
    values = {
        "BOT_TOKEN": bot_token,
        "SHOP_URL": shop_url,
        "SHOP_NAME": shop_name,
        "ADMIN_HANDLE": admin_handle,
    }
    lines = [f"{key}={_quote_env_value(value)}" for key, value in values.items() if value]
    env_file.write_text("\n".join(lines) + "\n")


def _prompt(label: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{label}{suffix}: ").strip()
    return value or default


def _print_products_summary(count: int, products_file: Path) -> None:
    if count:
        print(f"Saved {count} products to {products_file}")
        return

    print(f"No products were detected automatically. Created an empty {products_file.name}.")
    print("You can edit products.json manually or rerun scraper.py with a more specific product/collection URL.")


def configure(
    *,
    shop_url: str,
    bot_token: str,
    shop_name: Optional[str] = None,
    admin_handle: str = "",
    products_file: Path = DEFAULT_PRODUCTS_FILE,
    env_file: Path = DEFAULT_ENV_FILE,
    skip_scrape: bool = False,
) -> int:
    shop_name = shop_name or derive_shop_name(shop_url)
    write_env_file(
        env_file,
        bot_token=bot_token,
        shop_url=shop_url,
        shop_name=shop_name,
        admin_handle=admin_handle,
    )

    products = []
    if not skip_scrape:
        print(f"Scraping {shop_url}...")
        try:
            products = ShopScraper(shop_url).scrape()
        except Exception as exc:
            print(f"Scrape failed: {exc}", file=sys.stderr)

    save_products(products, str(products_file))
    _print_products_summary(len(products), products_file)
    print(f"Configured {shop_name}. Start the bot with: python bot.py")
    return len(products)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create a Telegram shop bot from an ecommerce link")
    parser.add_argument("shop_url", nargs="?", help="Ecommerce store, collection, or product URL")
    parser.add_argument("--bot-token", default="", help="Telegram bot token from @BotFather")
    parser.add_argument("--shop-name", default="", help="Display name shown in bot messages")
    parser.add_argument("--admin-handle", default="", help="Telegram username for wholesale inquiries")
    parser.add_argument("--products-file", type=Path, default=DEFAULT_PRODUCTS_FILE)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--skip-scrape", action="store_true", help="Write config without fetching products")
    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    shop_url = args.shop_url or _prompt("Ecommerce link")
    if not shop_url:
        parser.error("shop_url is required")

    bot_token = args.bot_token or _prompt("Telegram bot token")
    shop_name = args.shop_name or _prompt("Shop name", derive_shop_name(shop_url))
    admin_handle = args.admin_handle or _prompt("Admin Telegram handle for inquiries", "@your_username")

    configure(
        shop_url=shop_url,
        bot_token=bot_token,
        shop_name=shop_name,
        admin_handle=admin_handle,
        products_file=args.products_file,
        env_file=args.env_file,
        skip_scrape=args.skip_scrape,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
