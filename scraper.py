import json
from dataclasses import dataclass, asdict
from typing import List, Optional

@dataclass
class Product:
    id: str
    name: str
    description: str
    price: float
    currency: str
    image_url: str
    url: str
    tags: List[str]

class ShopScraper:
    """
    Base scraper class. In a real-world scenario, this would use 
    Playwright or BeautifulSoup to extract data from a URL.
    """
    def __init__(self, shop_url: str):
        self.shop_url = shop_url

    def scrape(self) -> List[Product]:
        # Implementation for real scraping would go here.
        # Returning mock data for now.
        return [
            Product(
                id="p1",
                name="Minimalist Desk Lamp",
                description="Elegant LED lamp with adjustable brightness and warm color temperature. Perfect for late-night coding.",
                price=89.00,
                currency="USD",
                image_url="https://images.unsplash.com/photo-1534073828943-f801091bb18c",
                url=f"{self.shop_url}/products/lamp",
                tags=["lighting", "minimalist", "office"]
            ),
            Product(
                id="p2",
                name="Ergonomic Walnut Stand",
                description="Hand-crafted walnut wood laptop stand. Improves posture and reclaim desk space.",
                price=120.00,
                currency="USD",
                image_url="https://images.unsplash.com/photo-1527443224154-c4a3942d3acf",
                url=f"{self.shop_url}/products/stand",
                tags=["accessories", "wood", "ergonomic"]
            ),
            Product(
                id="p3",
                name="Mechanical Keyboard",
                description="Compact 65% layout with hot-swappable switches and PBT keycaps. Tactile and satisfying.",
                price=150.00,
                currency="USD",
                image_url="https://images.unsplash.com/photo-1511467687858-23d96c32e4ae",
                url=f"{self.shop_url}/products/keyboard",
                tags=["tech", "peripheral", "keyboard"]
            )
        ]

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
