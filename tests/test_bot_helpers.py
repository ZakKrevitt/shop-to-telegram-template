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


def test_restricted_products_are_filtered_not_renamed():
    product = Product(
        id="1",
        name="1Fe-LSD Legal Tab",
        title="1Fe-LSD Legal Tab",
        description="Research compound",
        price="€10.00",
    )

    assert bot._is_restricted_product(product) is True


def test_books_with_restricted_terms_are_allowed_as_media():
    product = Product(
        id="2",
        name="Albert Hofmann Book",
        title="Albert Hofmann Book",
        description="A book about LSD history.",
        price="€20.00",
        categories=["books-media"],
    )

    assert bot._is_restricted_product(product) is False


def test_german_category_alias_maps_to_english_label():
    product = Product(
        id="3",
        name="Kanna Extract",
        title="Kanna Extract",
        description="Botanical extract.",
        price="€10.00",
        categories=["Pflanzenextrakt"],
    )

    assert bot._category_for_product(product) == "botanical-extracts"
    assert bot._category_label("botanical-extracts", "en") == "🌿 Botanical Extracts"


def test_product_card_text_separates_name_price_description_and_options():
    product = Product(
        id="4",
        name="CBD Oil - 5% Liquid Extract",
        title="CBD Oil - 5% Liquid Extract",
        description="Premium hemp-derived extract designed for everyday balance.",
        price="€20.00",
        variant_id="111",
        variants=[
            {
                "id": "111",
                "title": "10ml",
                "price": "€20.00",
                "available": True,
                "options": ["10ml"],
            }
        ],
    )

    text = bot._product_card_text(product)

    assert text.startswith("<b>CBD Oil - 5% Liquid Extract</b>\n\n")
    assert "<b>Price</b>\n€20.00" in text
    assert "<b>Description</b>\nPremium hemp-derived extract" in text
    assert "<b>Options</b>\n• 10ml — €20.00" in text
