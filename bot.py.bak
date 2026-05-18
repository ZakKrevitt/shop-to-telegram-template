import os
import json
from typing import Dict, List, Optional
from scraper import Product, load_products

# --- Core Logic ---

class CartManager:
    def __init__(self):
        self.carts: Dict[int, Dict[str, int]] = {} # user_id -> {product_id -> quantity}

    def add_to_cart(self, user_id: int, product_id: str):
        if user_id not in self.carts:
            self.carts[user_id] = {}
        self.carts[user_id][product_id] = self.carts[user_id].get(product_id, 0) + 1

    def get_cart(self, user_id: int) -> Dict[str, int]:
        return self.carts.get(user_id, {})

    def clear_cart(self, user_id: int):
        self.carts[user_id] = {}

class ShopEngine:
    def __init__(self, products_path: str):
        self.products = load_products(products_path)
        self.cart_manager = CartManager()

    def search(self, query: str) -> List[Product]:
        if not query:
            return self.products
        
        query = query.lower()
        results = []
        for p in self.products:
            if (query in p.name.lower() or 
                query in p.description.lower() or 
                any(query in t.lower() for t in p.tags)):
                results.append(p)
        return results

    def get_product_by_id(self, product_id: str) -> Optional[Product]:
        for p in self.products:
            if p.id == product_id:
                return p
        return None

# --- Mock Telegram Markup Helpers ---

def get_product_markup(product: Product):
    """
    Returns a representation of an InlineKeyboardMarkup for a product card.
    """
    return [
        [{"text": f"Add to Cart - ${product.price}", "callback_data": f"add_{product.id}"}],
        [{"text": "View on Site", "url": product.url}]
    ]

def get_cart_markup():
    return [
        [{"text": "🛒 View Cart", "callback_data": "view_cart"}],
        [{"text": "💳 Checkout", "callback_data": "checkout"}]
    ]

# --- Main Bot Flow Logic (Framework Agnostic) ---

def format_product_caption(product: Product) -> str:
    return (
        f"<b>{product.name}</b>\n\n"
        f"{product.description}\n\n"
        f"Price: {product.currency} {product.price}\n"
        f"Tags: {', '.join(product.tags)}"
    )

if __name__ == "__main__":
    # Example usage / Sanity check
    engine = ShopEngine("/root/shop-to-telegram/products.json")
    print(f"Loaded {len(engine.products)} products.")
    
    search_results = engine.search("lamp")
    for p in search_results:
        print(f"Search Result: {p.name}")
        print(format_product_caption(p))
        print("Markup:", get_product_markup(p))
