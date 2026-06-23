import bot
from scraper import Product


def test_admin_handle_is_optional(monkeypatch):
    monkeypatch.setattr(bot, "ADMIN_HANDLE", "")
    assert bot._has_admin_handle() is False

    monkeypatch.setattr(bot, "ADMIN_HANDLE", "@merchant")
    assert bot._has_admin_handle() is True


def test_checkout_url_uses_shopify_cart_when_variant_ids_exist(monkeypatch):
    monkeypatch.setattr(bot, "SHOP_URL", "https://shop.example/")

    checkout_url = bot._checkout_url_for_cart(
        [
            {"variant_id": "111", "qty": 2, "url": "https://shop.example/products/a"},
            {"variant_id": "222", "qty": 1, "url": "https://shop.example/products/b"},
        ]
    )

    assert checkout_url == "https://shop.example/cart/111:2,222:1"


def test_no_restricted_filter_by_default(monkeypatch):
    monkeypatch.setattr(bot, "RESTRICTED_KEYWORDS", set())
    product = Product(id="1", name="Anything", title="Anything", description="x", price="$1")
    assert bot._is_restricted_product(product) is False


def test_restricted_filter_is_config_driven(monkeypatch):
    monkeypatch.setattr(bot, "RESTRICTED_KEYWORDS", {"gift card"})
    product = Product(
        id="1",
        name="Digital Gift Card",
        title="Digital Gift Card",
        description="A redeemable gift card.",
        price="$25.00",
    )
    assert bot._is_restricted_product(product) is True


def test_category_is_derived_from_product_taxonomy():
    product = Product(
        id="3",
        name="Canvas Tote",
        title="Canvas Tote",
        description="Heavy canvas tote.",
        price="$24.50",
        categories=["Bags"],
    )
    assert bot._category_for_product(product) == "bags"


def test_uncategorized_product_falls_into_shop_bucket():
    product = Product(
        id="3b",
        name="Mystery Item",
        title="Mystery Item",
        description="No category here.",
        price="$10.00",
        categories=["products"],
    )
    assert bot._category_for_product(product) == "shop"


def test_category_label_falls_back_to_prettified_slug():
    assert bot._category_label("home-goods") == "🏷️ Home Goods"


def test_product_card_text_separates_name_price_description_and_options():
    product = Product(
        id="4",
        name="Ceramic Mug - 350ml",
        title="Ceramic Mug - 350ml",
        description="Hand-thrown stoneware mug for everyday use.",
        price="$20.00",
        variant_id="111",
        variants=[
            {
                "id": "111",
                "title": "350ml",
                "price": "$20.00",
                "available": True,
                "options": ["350ml"],
            }
        ],
    )

    text = bot._product_card_text(product)

    assert text.startswith("<b>Ceramic Mug - 350ml</b>\n\n")
    assert "<b>Price</b>\n$20.00" in text
    assert "<b>Description</b>\nHand-thrown stoneware mug" in text
    assert "<b>Options</b>\n• 350ml — $20.00" in text
