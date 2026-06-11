import bot


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
