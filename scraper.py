import argparse
import json
import re
import warnings
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, List, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

@dataclass
class Product:
    id: str
    name: str
    title: str
    description: str
    price: str
    currency: str = "USD"
    image: str = ""
    image_url: str = ""
    url: str = ""
    tags: List[str] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)
    variant_id: str = ""


CURRENCY_SYMBOLS = {
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
    "CAD": "$",
    "AUD": "$",
}


def _requests():
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL.*")
        import requests

    return requests


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = BeautifulSoup(str(value), "html.parser").get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()


def _coerce_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _slug(value: str, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or fallback


def _format_price(amount: Any, currency: str = "USD") -> str:
    if amount in (None, ""):
        return "See site"

    amount_str = str(amount).strip()
    symbol = CURRENCY_SYMBOLS.get(currency.upper(), f"{currency.upper()} ")

    try:
        return f"{symbol}{float(amount_str):.2f}"
    except ValueError:
        return amount_str


def _absolute_url(base_url: str, value: Any) -> str:
    if not value:
        return ""
    if isinstance(value, dict):
        value = value.get("url") or value.get("@id") or value.get("src")
    if not value:
        return ""
    return urljoin(base_url, str(value))


def _first_image(base_url: str, image_value: Any) -> str:
    for image in _coerce_list(image_value):
        image_url = _absolute_url(base_url, image)
        if image_url:
            return image_url
    return ""


def _jsonld_nodes(value: Any) -> Iterable[dict]:
    for item in _coerce_list(value):
        if not isinstance(item, dict):
            continue
        graph = item.get("@graph")
        if graph:
            yield from _jsonld_nodes(graph)
        yield item


def _is_product_node(node: dict) -> bool:
    node_type = node.get("@type")
    return "Product" in _coerce_list(node_type)


def _offer_from_product(product: dict) -> dict:
    offers = _coerce_list(product.get("offers"))
    for offer in offers:
        if isinstance(offer, dict):
            return offer
    return {}


def _meta_content(soup: BeautifulSoup, *names: str) -> str:
    for name in names:
        tag = soup.find("meta", attrs={"property": name}) or soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):
            return tag["content"].strip()
    return ""


def parse_jsonld_products(html: str, source_url: str) -> List[Product]:
    soup = BeautifulSoup(html, "html.parser")
    products: List[Product] = []

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text()
        if not raw:
            continue

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue

        for node in _jsonld_nodes(data):
            if not _is_product_node(node):
                continue

            offer = _offer_from_product(node)
            currency = str(offer.get("priceCurrency") or "USD").upper()
            name = _clean_text(node.get("name")) or "Untitled product"
            product_url = _absolute_url(source_url, offer.get("url") or node.get("url")) or source_url
            image = _first_image(source_url, node.get("image"))
            category = _clean_text(node.get("category"))
            product_id = str(node.get("sku") or node.get("mpn") or _slug(name, f"p{len(products) + 1}"))

            products.append(
                Product(
                    id=product_id,
                    name=name,
                    title=name,
                    description=_clean_text(node.get("description")),
                    price=_format_price(offer.get("price") or offer.get("lowPrice"), currency),
                    currency=currency,
                    image=image,
                    image_url=image,
                    url=product_url,
                    tags=[tag for tag in [category] if tag],
                    categories=[category.lower()] if category else ["products"],
                )
            )

    return products


def parse_opengraph_product(html: str, source_url: str) -> List[Product]:
    soup = BeautifulSoup(html, "html.parser")
    title = _meta_content(soup, "og:title", "twitter:title") or _clean_text(soup.title.string if soup.title else "")
    if not title:
        return []

    description = _meta_content(soup, "og:description", "twitter:description", "description")
    amount = _meta_content(soup, "product:price:amount", "og:price:amount")
    currency = _meta_content(soup, "product:price:currency", "og:price:currency") or "USD"
    image = _absolute_url(source_url, _meta_content(soup, "og:image", "twitter:image"))
    canonical = soup.find("link", rel="canonical")
    product_url = _absolute_url(source_url, canonical.get("href") if canonical else "") or source_url

    return [
        Product(
            id=_slug(title, "p1"),
            name=title,
            title=title,
            description=_clean_text(description),
            price=_format_price(amount, currency),
            currency=currency.upper(),
            image=image,
            image_url=image,
            url=product_url,
            categories=["products"],
        )
    ]


class ShopScraper:
    """
    Best-effort ecommerce scraper.

    It tries Shopify's public products endpoint first, then falls back to
    structured product metadata on the provided page.
    """
    def __init__(self, shop_url: str, session: Optional[Any] = None, timeout: int = 15):
        self.shop_url = shop_url
        self.session = session or _requests().Session()
        self.timeout = timeout

    def scrape(self) -> List[Product]:
        try:
            products = self._scrape_shopify_products()
        except Exception as exc:
            requests = _requests()
            if not isinstance(exc, requests.RequestException):
                raise
            products = []

        if products:
            return products

        response = self.session.get(self.shop_url, timeout=self.timeout)
        response.raise_for_status()
        html = response.text

        products = parse_jsonld_products(html, self.shop_url)
        if products:
            return products

        return parse_opengraph_product(html, self.shop_url)

    def _scrape_shopify_products(self) -> List[Product]:
        parsed = urlparse(self.shop_url)
        if not parsed.scheme or not parsed.netloc:
            return []

        base_url = f"{parsed.scheme}://{parsed.netloc}"
        products_url = urljoin(base_url, "/products.json?limit=250")

        response = self.session.get(products_url, timeout=self.timeout)
        response.raise_for_status()

        try:
            data = response.json()
        except ValueError:
            return []

        shopify_products = data.get("products")
        if not isinstance(shopify_products, list):
            return []

        products: List[Product] = []
        for index, raw_product in enumerate(shopify_products, start=1):
            variants = raw_product.get("variants") or []
            variant = variants[0] if variants else {}
            images = raw_product.get("images") or []
            image = ""
            if raw_product.get("image"):
                image = _absolute_url(base_url, raw_product["image"].get("src"))
            if not image and images:
                image = _absolute_url(base_url, images[0].get("src"))

            title = _clean_text(raw_product.get("title")) or f"Product {index}"
            handle = raw_product.get("handle") or _slug(title, f"product-{index}")
            product_type = _clean_text(raw_product.get("product_type"))
            tags = raw_product.get("tags") or []
            if isinstance(tags, str):
                tags = [tag.strip() for tag in tags.split(",") if tag.strip()]

            products.append(
                Product(
                    id=str(raw_product.get("id") or f"p{index}"),
                    name=title,
                    title=title,
                    description=_clean_text(raw_product.get("body_html")),
                    price=_format_price(variant.get("price"), "USD"),
                    currency="USD",
                    image=image,
                    image_url=image,
                    url=urljoin(base_url, f"/products/{handle}"),
                    tags=tags,
                    categories=[product_type.lower()] if product_type else ["products"],
                    variant_id=str(variant.get("id") or ""),
                )
            )

        return products

def save_products(products: List[Product], filepath: str):
    with open(filepath, "w") as f:
        json.dump([asdict(p) for p in products], f, indent=2)

def load_products(filepath: str) -> List[Product]:
    try:
        with open(filepath, "r") as f:
            data = json.load(f)
            return [Product(**p) for p in data]
    except FileNotFoundError:
        return []


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape an ecommerce link into products.json")
    parser.add_argument("shop_url", help="Shopify store or product page URL")
    parser.add_argument("--output", default="products.json", help="Where to write the product catalog")
    args = parser.parse_args()

    products = ShopScraper(args.shop_url).scrape()
    save_products(products, args.output)
    print(f"Saved {len(products)} products to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
