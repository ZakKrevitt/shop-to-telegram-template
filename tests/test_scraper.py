import json

from scraper import ShopScraper, parse_jsonld_products, parse_opengraph_product, scrape_site_sections


class FakeResponse:
    def __init__(self, *, text="", json_data=None, status_code=200):
        self.text = text
        self._json_data = json_data
        self.status_code = status_code

    def json(self):
        if isinstance(self._json_data, Exception):
            raise self._json_data
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, responses):
        self.responses = responses
        self.urls = []

    def get(self, url, timeout):
        self.urls.append(url)
        response = self.responses[url]
        if isinstance(response, Exception):
            raise response
        return response


def test_scrapes_shopify_products_endpoint():
    products_json = {
        "products": [
            {
                "id": 101,
                "title": "Canvas Tote",
                "handle": "canvas-tote",
                "body_html": "<p>Heavy canvas tote.</p>",
                "product_type": "Bags",
                "tags": "canvas, carry",
                "image": {"src": "//cdn.example/tote.jpg"},
                "images": [{"id": 1, "src": "//cdn.example/tote.jpg"}],
                "options": [{"name": "Size", "values": ["Small", "Large"]}],
                "variants": [
                    {"id": 555, "title": "Small", "option1": "Small", "price": "24.50", "available": True, "image_id": 1},
                    {"id": 556, "title": "Large", "option1": "Large", "price": "29.50", "available": False},
                ],
            }
        ]
    }
    session = FakeSession(
        {
            "https://shop.example/products.json?limit=250": FakeResponse(json_data=products_json),
        }
    )

    products = ShopScraper("https://shop.example/collections/all", session=session).scrape()

    assert len(products) == 1
    assert products[0].title == "Canvas Tote"
    assert products[0].price == "$24.50"
    assert products[0].variant_id == "555"
    assert products[0].url == "https://shop.example/products/canvas-tote"
    assert products[0].categories == ["bags"]
    assert products[0].category_label == "Bags"
    assert products[0].images == ["https://cdn.example/tote.jpg"]
    assert products[0].options == [{"name": "Size", "values": ["Small", "Large"]}]
    assert products[0].variants[0]["title"] == "Small"
    assert products[0].variants[0]["available"] is True
    assert products[0].variants[1]["available"] is False


def test_jsonld_product_fallback_extracts_product_metadata():
    product_json = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": "Ceramic Mug",
        "description": "Thrown by hand.",
        "sku": "mug-1",
        "image": ["/images/mug.jpg"],
        "category": "Home",
        "offers": {
            "@type": "Offer",
            "price": "18",
            "priceCurrency": "EUR",
            "url": "/products/mug",
        },
    }
    html = f'<script type="application/ld+json">{json.dumps(product_json)}</script>'

    products = parse_jsonld_products(html, "https://maker.example/products/mug")

    assert len(products) == 1
    assert products[0].id == "mug-1"
    assert products[0].price == "€18.00"
    assert products[0].image == "https://maker.example/images/mug.jpg"
    assert products[0].url == "https://maker.example/products/mug"


def test_opengraph_fallback_creates_single_product():
    html = """
    <html>
      <head>
        <title>Fallback Product</title>
        <meta property="og:title" content="Fallback Product">
        <meta property="og:description" content="Useful thing">
        <meta property="product:price:amount" content="12.25">
        <meta property="product:price:currency" content="USD">
        <meta property="og:image" content="/fallback.jpg">
        <link rel="canonical" href="/products/fallback">
      </head>
    </html>
    """

    products = parse_opengraph_product(html, "https://store.example/products/fallback")

    assert len(products) == 1
    assert products[0].title == "Fallback Product"
    assert products[0].price == "$12.25"
    assert products[0].image == "https://store.example/fallback.jpg"


def test_scrape_site_sections_from_sitemaps():
    sitemap = """
    <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <sitemap><loc>https://shop.example/sitemap_pages_1.xml</loc></sitemap>
      <sitemap><loc>https://shop.example/sitemap_collections_1.xml</loc></sitemap>
    </sitemapindex>
    """
    pages = """
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://shop.example/pages/about-us</loc></url>
      <url><loc>https://shop.example/pages/faq</loc></url>
    </urlset>
    """
    collections = """
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://shop.example/collections/set-setting</loc></url>
    </urlset>
    """
    session = FakeSession(
        {
            "https://shop.example/sitemap.xml": FakeResponse(text=sitemap),
            "https://shop.example/sitemap_pages_1.xml": FakeResponse(text=pages),
            "https://shop.example/sitemap_collections_1.xml": FakeResponse(text=collections),
        }
    )

    sections = scrape_site_sections("https://shop.example", session=session)

    assert sections == [
        {"title": "About", "url": "https://shop.example/pages/about-us"},
        {"title": "FAQ", "url": "https://shop.example/pages/faq"},
    ]
