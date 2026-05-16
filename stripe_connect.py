"""Stripe Connect helpers for create-tg-shop.

This module is intentionally framework-agnostic so the Telegram bot, a future
hosted SaaS backend, or a Stripe Marketplace app can all call the same logic.

Install dependency:
    pip install stripe

Required environment variables:
    STRIPE_SECRET_KEY=sk_test_...
    TG_SHOP_PLATFORM_FEE_BPS=500  # 500 = 5%
    TG_SHOP_SUCCESS_URL=https://your-domain.com/success?session_id={CHECKOUT_SESSION_ID}
    TG_SHOP_CANCEL_URL=https://your-domain.com/cancel
"""

import os
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

import stripe

from scraper import Product

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")


@dataclass
class CartLineItem:
    product: Product
    quantity: int


def dollars_to_cents(amount: float) -> int:
    return int(round(amount * 100))


def get_platform_fee_bps() -> int:
    """Return platform fee in basis points. 500 bps = 5%."""
    return int(os.getenv("TG_SHOP_PLATFORM_FEE_BPS", "500"))


def calculate_platform_fee_amount(amount_cents: int, fee_bps: Optional[int] = None) -> int:
    """Calculate application fee amount in cents."""
    bps = get_platform_fee_bps() if fee_bps is None else fee_bps
    return int(round(amount_cents * (bps / 10_000)))


def build_cart_line_items(cart: Dict[str, int], products: Iterable[Product]) -> List[CartLineItem]:
    """Convert a cart dict into line items using the current product catalog."""
    product_lookup = {product.id: product for product in products}
    line_items: List[CartLineItem] = []

    for product_id, quantity in cart.items():
        product = product_lookup.get(product_id)
        if not product or quantity <= 0:
            continue
        line_items.append(CartLineItem(product=product, quantity=quantity))

    return line_items


def create_connect_onboarding_link(
    connected_account_id: str,
    refresh_url: str,
    return_url: str,
) -> str:
    """Create a Stripe Connect onboarding link for an Express/Custom account."""
    account_link = stripe.AccountLink.create(
        account=connected_account_id,
        refresh_url=refresh_url,
        return_url=return_url,
        type="account_onboarding",
    )
    return account_link.url


def create_express_connected_account(email: Optional[str] = None) -> str:
    """Create an Express connected account and return its Stripe account ID.

    Use this if you want your hosted SaaS to create seller accounts. If you want
    sellers to bring an existing Stripe account, use Stripe OAuth instead.
    """
    account = stripe.Account.create(
        type="express",
        email=email,
        capabilities={
            "card_payments": {"requested": True},
            "transfers": {"requested": True},
        },
    )
    return account.id


def create_checkout_session_for_connected_account(
    cart: Dict[str, int],
    products: Iterable[Product],
    connected_account_id: str,
    customer_telegram_id: Optional[int] = None,
) -> str:
    """Create a Stripe-hosted Checkout Session with a platform fee.

    This uses destination charges:
    customer pays through your platform integration, funds are routed to the
    seller's connected Stripe account, and your platform keeps an application fee.
    """
    line_items = build_cart_line_items(cart, products)
    if not line_items:
        raise ValueError("Cannot create checkout session for an empty cart.")

    currency = line_items[0].product.currency.lower()
    total_amount_cents = 0
    stripe_line_items = []

    for item in line_items:
        product = item.product
        if product.currency.lower() != currency:
            raise ValueError("All products in a checkout session must use the same currency.")

        unit_amount = dollars_to_cents(product.price)
        total_amount_cents += unit_amount * item.quantity

        stripe_line_items.append(
            {
                "price_data": {
                    "currency": currency,
                    "product_data": {
                        "name": product.name,
                        "description": product.description[:500],
                        "images": [product.image_url] if product.image_url else [],
                        "metadata": {
                            "tg_shop_product_id": product.id,
                            "source_url": product.url,
                        },
                    },
                    "unit_amount": unit_amount,
                },
                "quantity": item.quantity,
            }
        )

    application_fee_amount = calculate_platform_fee_amount(total_amount_cents)

    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=stripe_line_items,
        success_url=os.getenv(
            "TG_SHOP_SUCCESS_URL",
            "https://example.com/success?session_id={CHECKOUT_SESSION_ID}",
        ),
        cancel_url=os.getenv("TG_SHOP_CANCEL_URL", "https://example.com/cancel"),
        payment_intent_data={
            "application_fee_amount": application_fee_amount,
            "transfer_data": {"destination": connected_account_id},
            "metadata": {
                "customer_telegram_id": str(customer_telegram_id or ""),
                "platform": "create-tg-shop",
            },
        },
        metadata={
            "customer_telegram_id": str(customer_telegram_id or ""),
            "connected_account_id": connected_account_id,
            "platform_fee_bps": str(get_platform_fee_bps()),
        },
    )

    return session.url
