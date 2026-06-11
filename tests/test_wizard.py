import json

from wizard import configure, derive_shop_name, write_env_file


def test_derive_shop_name_from_ecommerce_url():
    assert derive_shop_name("https://www.cool-maker-shop.com/products/mug") == "Cool Maker Shop"


def test_write_env_file_uses_bot_token_without_stripe_settings(tmp_path):
    env_file = tmp_path / ".env"

    write_env_file(
        env_file,
        bot_token="123:abc",
        shop_url="https://shop.example",
        shop_name="Shop Example",
        admin_handle="@merchant",
    )

    text = env_file.read_text()
    assert "BOT_TOKEN=123:abc" in text
    assert 'SHOP_NAME="Shop Example"' in text
    assert "STRIPE" not in text
    assert "TG_SHOP_PLATFORM_FEE_BPS" not in text
    assert "TELEGRAM_BOT_TOKEN" not in text


def test_configure_can_skip_scrape_and_write_empty_catalog(tmp_path):
    env_file = tmp_path / ".env"
    products_file = tmp_path / "products.json"
    sections_file = tmp_path / "sections.json"

    count = configure(
        shop_url="https://shop.example",
        bot_token="123:abc",
        shop_name="Shop Example",
        admin_handle="@merchant",
        products_file=products_file,
        sections_file=sections_file,
        env_file=env_file,
        skip_scrape=True,
    )

    assert count == 0
    assert json.loads(products_file.read_text()) == []
    assert json.loads(sections_file.read_text()) == []
    assert "SHOP_URL=https://shop.example" in env_file.read_text()
