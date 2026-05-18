import json
from dataclasses import dataclass, asdict, field
from typing import List, Optional

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

class ShopScraper:
    """
    Base scraper class. Override `scrape()` to use Playwright / BeautifulSoup.
    Returns Product dataclasses unified for the bot.
    """
    def __init__(self, shop_url: str):
        self.shop_url = shop_url

    def scrape(self) -> List[Product]:
        # Override with real scraping logic.
        return []

def save_products(products: List[Product], filepath: str):
    with open(filepath, 'w') as f:
        json.dump([asdict(p) for p in products], f, indent=2)

def load_products(filepath: str) -> List[Product]:
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
            return [Product(**p) for p in data]
    except FileNotFoundError:
        return []
