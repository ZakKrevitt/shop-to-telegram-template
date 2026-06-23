"""
Best-effort ecommerce scraper for the shop-to-telegram template.

Given any store URL it tries, in order:
  1. Shopify's public /products.json endpoint (richest data: variants, images, options)
  2. JSON-LD Product metadata on the page
  3. OpenGraph product metadata on the page

Categories are derived from the store's own data (Shopify product_type, then
tags, then JSON-LD category) — never from a hard-coded vertical. This keeps the
template generic across any kind of shop.
"""

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
    category_label: str = ""
    variant_id: str = ""
    images: List[str] = field(default_factory=list)
    options: List[dict] = field(default_factory=list)
    variants: List[dict] = field(default_factory=list)


CURRENCY_SYMBOLS = {
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
    "CAD": "$",
    "AUD": "$",
}


# Common ecommerce info pages, surfaced in the bot's "Site Sections" menu.
# Each entry is (display label, [url-substrings to match in the sitemap]).
SECTION_RULES = [
    ("About", ["about-us", "about", "our-story", "story"]),
    ("FAQ", ["faqs", "faq", "help-center", "help"]),
    ("Shipping", ["shipping", "delivery"]),
    ("Returns", ["returns", "refund-policy", "refunds", "return-policy"]),
    ("Contact", ["contact-us", "contact"]),
    ("Privacy", ["privacy-policy", "privacy"]),
    ("Terms", ["terms-of-service", "terms-and-conditions", "terms"]),
    ("Blog", ["blogs/news", "blog", "journal", "news"]),
]


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
    slug = re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")
    return slug or fallback


def _label(value: str, fallback: str = "Shop") -> str:
    text = re.sub(r"[-_]+", " ", str(value or "").strip())
    text = re.sub(r"\s+", " ", text).strip()
    return text.title() if text else fallback


def _format_price(amount: Any, currency: str = "USD") -> str:
    if amount in (None, ""):
        return "See site"

    amount_str = str(amount).strip()
    symbol = CURRENCY_SYMBOLS.get(currency.upper(), f"{currency.upper()} ")

    try:
        return f"{symbol}{float(amount_str):.2f}"
    except ValueError:
        return amount_str


def infer_product_category(
    title: str = "",
    description: str = "",
    tags: Optional[List[str]] = None,
    product_type: str = "",
    fallback_label: str = "Shop",
) -> tuple:
    """Return (slug, label) for a product using the store's own taxonomy.

    Preference order: explicit product type, then the first tag, then a single
    catch-all bucket. No vertical-specific keyword guessing.
    """
    if product_type and _slug(product_type, "") not in ("", "products"):
        return _slug(product_type, "shop"), _label(product_type, fallback_label)

    for tag in tags or []:
        slug = _slug(tag, "")
        if slug and slug != "products":
            return slug, _label(tag, fallback_label)

    return "shop", fallback_label


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


def _image_urls(base_url: str, images: Any) -> List[str]:
    urls: List[str] = []
    for image in _coerce_list(images):
        image_url = _absolute_url(base_url, image)
        if image_url and image_url not in urls:
            urls.append(image_url)
    return urls


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
            slug, label = infer_product_category(product_type=category)
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
                    categories=[slug],
                    category_label=label,
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
            categories=["shop"],
            category_label="Shop",
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
        currency = self._detect_shopify_currency(base_url)
        shop_label = _label(parsed.netloc.removeprefix("www.").split(".")[0])
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
            variant = next((v for v in variants if v.get("available")), variants[0] if variants else {})
            raw_images = raw_product.get("images") or []
            image_urls = [_absolute_url(base_url, image.get("src")) for image in raw_images if image.get("src")]
            image_lookup = {
                str(image.get("id")): _absolute_url(base_url, image.get("src"))
                for image in raw_images
                if image.get("id") and image.get("src")
            }
            image = ""
            if raw_product.get("image"):
                image = _absolute_url(base_url, raw_product["image"].get("src"))
            if not image and image_urls:
                image = image_urls[0]

            title = _clean_text(raw_product.get("title")) or f"Product {index}"
            handle = raw_product.get("handle") or _slug(title, f"product-{index}")
            product_type = _clean_text(raw_product.get("product_type"))
            tags = raw_product.get("tags") or []
            if isinstance(tags, str):
                tags = [tag.strip() for tag in tags.split(",") if tag.strip()]
            description = _clean_text(raw_product.get("body_html"))
            options = [
                {
                    "name": _clean_text(option.get("name")),
                    "values": [_clean_text(value) for value in option.get("values", []) if _clean_text(value)],
                }
                for option in raw_product.get("options", [])
                if option.get("values")
            ]
            variant_rows = []
            for raw_variant in variants:
                option_values = [
                    _clean_text(raw_variant.get(f"option{i}"))
                    for i in range(1, 4)
                    if _clean_text(raw_variant.get(f"option{i}"))
                ]
                variant_image = image_lookup.get(str(raw_variant.get("image_id")), "")
                variant_rows.append(
                    {
                        "id": str(raw_variant.get("id") or ""),
                        "title": _clean_text(raw_variant.get("title")) or "Default",
                        "price": _format_price(raw_variant.get("price"), currency),
                        "available": bool(raw_variant.get("available", True)),
                        "options": option_values,
                        "image": variant_image,
                    }
                )

            slug, label = infer_product_category(
                tags=tags, product_type=product_type, fallback_label=shop_label
            )

            products.append(
                Product(
                    id=str(raw_product.get("id") or f"p{index}"),
                    name=title,
                    title=title,
                    description=description,
                    price=_format_price(variant.get("price"), currency),
                    currency=currency,
                    image=image,
                    image_url=image,
                    url=urljoin(base_url, f"/products/{handle}"),
                    tags=tags,
                    categories=[slug],
                    category_label=label,
                    variant_id=str(variant.get("id") or ""),
                    images=image_urls,
                    options=options,
                    variants=variant_rows,
                )
            )

        return products

    def _detect_shopify_currency(self, base_url: str) -> str:
        try:
            response = self.session.get(base_url, timeout=self.timeout)
            response.raise_for_status()
        except Exception:
            return "USD"

        html = response.text
        patterns = [
            r"Shopify\.currency\s*=\s*\{[^}]*[\"']active[\"']\s*:\s*[\"']([A-Z]{3})[\"']",
            r"[\"']currencyCode[\"']\s*:\s*[\"']([A-Z]{3})[\"']",
            r"[\"']currency[\"']\s*:\s*[\"']([A-Z]{3})[\"']",
            r"currency\s*=\s*[\"']([A-Z]{3})[\"']",
        ]
        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                return match.group(1).upper()

        if "€" in html:
            return "EUR"
        if "£" in html:
            return "GBP"
        return "USD"


def scrape_site_sections(shop_url: str, session: Optional[Any] = None, timeout: int = 15) -> List[dict]:
    session = session or _requests().Session()
    parsed = urlparse(shop_url)
    if not parsed.scheme or not parsed.netloc:
        return []

    base_url = f"{parsed.scheme}://{parsed.netloc}"
    try:
        sitemap_response = session.get(urljoin(base_url, "/sitemap.xml"), timeout=timeout)
        sitemap_response.raise_for_status()
    except Exception:
        return []

    section_urls: List[str] = []
    for match in re.findall(r"<loc>(.*?)</loc>", sitemap_response.text):
        loc = match.replace("&amp;", "&")
        if "sitemap_pages" in loc:
            try:
                response = session.get(loc, timeout=timeout)
                response.raise_for_status()
            except Exception:
                continue
            section_urls.extend(url.replace("&amp;", "&") for url in re.findall(r"<loc>(.*?)</loc>", response.text))

    sections: List[dict] = []
    seen_labels = set()
    for label, needles in SECTION_RULES:
        for section_url in section_urls:
            lower_url = section_url.lower()
            if not any(needle in lower_url for needle in needles):
                continue
            if label in seen_labels:
                break
            sections.append({"title": label, "url": section_url})
            seen_labels.add(label)
            break

    return sections


def save_products(products: List[Product], filepath: str):
    with open(filepath, "w") as f:
        json.dump([asdict(p) for p in products], f, indent=2)


def save_site_sections(sections: List[dict], filepath: str):
    with open(filepath, "w") as f:
        json.dump(sections, f, indent=2)


def load_products(filepath: str) -> List[Product]:
    try:
        with open(filepath, "r") as f:
            data = json.load(f)
            return [Product(**{k: v for k, v in p.items() if k in Product.__dataclass_fields__}) for p in data]
    except FileNotFoundError:
        return []


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape an ecommerce link into products.json")
    parser.add_argument("shop_url", help="Shopify store or product page URL")
    parser.add_argument("--output", default="products.json", help="Where to write the product catalog")
    parser.add_argument("--sections-output", default="", help="Optional file for website section links")
    args = parser.parse_args()

    products = ShopScraper(args.shop_url).scrape()
    save_products(products, args.output)
    print(f"Saved {len(products)} products to {args.output}")
    if args.sections_output:
        sections = scrape_site_sections(args.shop_url)
        save_site_sections(sections, args.sections_output)
        print(f"Saved {len(sections)} sections to {args.sections_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
