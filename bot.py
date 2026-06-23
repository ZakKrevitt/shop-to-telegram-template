"""
🛍️ Shop-to-Telegram bot template
=================================
Drop-in Telegram storefront for any ecommerce site: banner start screen,
auto-derived category menus, product cards with images and variants, an
in-bot cart, multi-language UI, keyword/semantic search, and an optional
wholesale inquiry flow. Checkout hands off to the merchant's own store.

Configuration is entirely environment-driven — nothing in this file is tied
to a specific shop or product vertical.

Usage:
  1. pip install -r REQUIREMENTS.txt
  2. Set BOT_TOKEN and SHOP_URL (or run python wizard.py)
  3. Create products.json with scraper.py, or let the bot scrape on boot
  4. python3 bot.py
"""

import html, os, json, logging, re, urllib.parse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler, PicklePersistence, filters
)
from scraper import load_products


def _load_env_file(filepath: str) -> None:
    if not os.path.exists(filepath):
        return

    with open(filepath) as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key.strip(), value)


_load_env_file(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

# ── CONFIG ──────────────────────────────────────────────────────────
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN        = os.environ.get("BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN")
ADMIN_HANDLE = os.environ.get("ADMIN_HANDLE", "")
SHOP_NAME    = os.environ.get("SHOP_NAME", "Your Shop")
SHOP_URL     = os.environ.get("SHOP_URL", "https://your-shop.com")
SHOP_TAGLINE = os.environ.get("SHOP_TAGLINE", "")   # overrides the welcome blurb
SHOP_BADGES  = os.environ.get("SHOP_BADGES", "")    # e.g. "🚚 Free shipping  ·  💳 Cards accepted"
DEFAULT_BANNER_IMG = os.path.join(ROOT_DIR, "assets", "start-banner.png")
BANNER_IMG   = os.environ.get("BANNER_IMG") or DEFAULT_BANNER_IMG
DEFAULT_LANGUAGE = os.environ.get("DEFAULT_LANGUAGE", "en").lower()
ENABLE_SEMANTIC_SEARCH = os.environ.get("ENABLE_SEMANTIC_SEARCH", "").lower() in {"1", "true", "yes", "on"}
# Optional compliance filter — comma-separated keywords hidden from the bot.
# Empty by default; set RESTRICTED_KEYWORDS for regulated stores.
RESTRICTED_KEYWORDS = {kw.strip().lower() for kw in os.environ.get("RESTRICTED_KEYWORDS", "").split(",") if kw.strip()}
PERSIST_FILE = os.path.join(ROOT_DIR, "bot_persistence.pickle")
PRODUCTS_FILE = os.path.join(ROOT_DIR, "products.json")
SECTIONS_FILE = os.path.join(ROOT_DIR, "sections.json")

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)


# ── LOAD CATALOG ────────────────────────────────────────────────────
def _shop_host() -> str:
    try:
        return urllib.parse.urlparse(SHOP_URL).netloc.lower().removeprefix("www.")
    except Exception:
        return ""


def _catalog_matches_shop(catalog: list) -> bool:
    """True if the catalog's product URLs belong to the configured SHOP_URL.

    Used to tell a real (already-scraped) catalog apart from the bundled
    sample products, so a fresh deploy scrapes the actual store instead of
    serving the demo items.
    """
    host = _shop_host()
    if not host:
        return True
    for product in catalog:
        p_host = urllib.parse.urlparse(getattr(product, "url", "") or "").netloc.lower().removeprefix("www.")
        if p_host and (p_host == host or p_host.endswith("." + host) or host.endswith("." + p_host)):
            return True
    return False


def _bootstrap_catalog() -> list:
    """Return the catalog, scraping SHOP_URL on boot when needed.

    A deploy ships sample products.json; when SHOP_URL points at a real store
    whose products aren't in that file yet, scrape it. This lets a fresh deploy
    come up with only BOT_TOKEN + SHOP_URL set, no local wizard step.
    """
    existing = load_products(PRODUCTS_FILE)
    placeholder = (not SHOP_URL) or "your-shop.com" in SHOP_URL
    if placeholder:
        return existing
    if existing and _catalog_matches_shop(existing):
        return existing

    logging.info("Scraping %s on boot...", SHOP_URL)
    try:
        from scraper import ShopScraper, save_products, save_site_sections, scrape_site_sections

        scraped = ShopScraper(SHOP_URL).scrape()
        if scraped:
            save_products(scraped, PRODUCTS_FILE)
            try:
                save_site_sections(scrape_site_sections(SHOP_URL), SECTIONS_FILE)
            except Exception:
                pass
            logging.info("Boot scrape complete: %d products.", len(scraped))
            return scraped
        logging.warning("Boot scrape found no products for %s.", SHOP_URL)
        return []
    except Exception as exc:
        logging.warning("Boot scrape failed (%s).", exc)
        return existing if _catalog_matches_shop(existing) else []


products = _bootstrap_catalog()
if not products:
    logging.warning("No products loaded! Set SHOP_URL or populate products.json")


def _load_site_sections(filepath: str) -> list:
    try:
        with open(filepath, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        return []

    return [
        {"title": str(section.get("title", "")).strip(), "url": str(section.get("url", "")).strip()}
        for section in data
        if section.get("title") and section.get("url")
    ]


SITE_SECTIONS = _load_site_sections(SECTIONS_FILE)

LANGUAGE_OPTIONS = {
    "en": "English",
    "de": "Deutsch",
    "es": "Español",
    "pt": "Português",
    "nl": "Nederlands",
}

TEXT = {
    "en": {
        "welcome": "Browse the catalog below, or just type what you're looking for.",
        "empty_catalog": "The catalog is empty right now.",
        "all_items": "🗺️ All Items",
        "view_cart": "🛒 View Cart",
        "site_sections": "📖 Site Sections",
        "settings": "⚙️ Settings",
        "language": "🌐 Language",
        "open_store": "🌐 Open Store",
        "back": "⬅️ Back",
        "back_to_shop": "⬅️ Back to Shop",
        "cancel": "⬅️ Cancel",
        "no_items": "No items found.",
        "tap_to_view": "Tap to view:",
        "sections_title": "{shop_name} sections",
        "no_sections": "No site sections are configured yet.",
        "restricted": "This item is not available through the Telegram bot.",
        "checkout_site": "🌐 Checkout on Site",
        "checkout_site_count": "🌐 Checkout on Site ({count} items)",
        "choose_option": "🛒 Choose Option",
        "add_to_cart": "🛒 Add to Cart",
        "sold_out": "Sold Out",
        "view_online": "🌐 View Online",
        "wholesale": "🏢 Wholesale",
        "share": "📤 Share",
        "price": "Price",
        "description": "Description",
        "options": "Options:",
        "more_on_site": "+{count} more on the website",
        "choose_option_for": "Choose an option for {product}:",
        "select_quantity": "{product}\n{option}\n\nSelect quantity:",
        "option_sold_out": "That option is sold out.",
        "not_available_alert": "This item is not available in the bot.",
        "cart_empty": "Your cart is empty.",
        "cart_title": "🛒 *Your Cart — {shop_name}*\n━━━━━━━━━━━━━━",
        "total": "💰 *Total: {amount}*",
        "clear_cart": "🪟 Clear Cart",
        "cart_cleared": "Cart cleared!",
        "added": "Added {qty}x! 🛒",
        "nothing_found": "Nothing found. Try browsing categories.",
        "settings_title": "Settings",
        "choose_language": "Choose language:",
        "language_saved": "Language set to {language}.",
        "wholesale_not_configured": "Wholesale inquiries are not configured for this shop.",
        "wholesale_title": "🏢 *Wholesale: {product}*\n\nSelect quantity range:",
        "location_prompt": "🌍 *Where are you located?*",
        "submit_inquiry": "📤 Submit Inquiry",
        "review": "📋 *Review:*\n📦 {product}\n🔢 {qty}\n📍 {location}\n\nReady to submit?",
        "cancelled": "Cancelled.",
    },
    "de": {
        "welcome": "Stöbere unten im Katalog oder tippe einfach, wonach du suchst.",
        "empty_catalog": "Der Katalog ist im Moment leer.",
        "all_items": "🗺️ Alle Artikel",
        "view_cart": "🛒 Warenkorb",
        "site_sections": "📖 Website-Bereiche",
        "settings": "⚙️ Einstellungen",
        "language": "🌐 Sprache",
        "open_store": "🌐 Store öffnen",
        "back": "⬅️ Zurück",
        "back_to_shop": "⬅️ Zurück zum Shop",
        "cancel": "⬅️ Abbrechen",
        "no_items": "Keine Artikel gefunden.",
        "tap_to_view": "Zum Ansehen tippen:",
        "sections_title": "{shop_name} Bereiche",
        "no_sections": "Es sind noch keine Website-Bereiche konfiguriert.",
        "restricted": "Dieser Artikel ist nicht über den Telegram-Bot verfügbar.",
        "checkout_site": "🌐 Checkout auf der Website",
        "checkout_site_count": "🌐 Checkout auf der Website ({count} Artikel)",
        "choose_option": "🛒 Option wählen",
        "add_to_cart": "🛒 In den Warenkorb",
        "sold_out": "Ausverkauft",
        "view_online": "🌐 Online ansehen",
        "wholesale": "🏢 Wholesale",
        "share": "📤 Teilen",
        "price": "Preis",
        "description": "Beschreibung",
        "options": "Optionen:",
        "more_on_site": "+{count} weitere auf der Website",
        "choose_option_for": "Wähle eine Option für {product}:",
        "select_quantity": "{product}\n{option}\n\nMenge auswählen:",
        "option_sold_out": "Diese Option ist ausverkauft.",
        "not_available_alert": "Dieser Artikel ist im Bot nicht verfügbar.",
        "cart_empty": "Dein Warenkorb ist leer.",
        "cart_title": "🛒 *Dein Warenkorb — {shop_name}*\n━━━━━━━━━━━━━━",
        "total": "💰 *Gesamt: {amount}*",
        "clear_cart": "🪟 Warenkorb leeren",
        "cart_cleared": "Warenkorb geleert!",
        "added": "{qty}x hinzugefügt! 🛒",
        "nothing_found": "Nichts gefunden. Versuche es über die Kategorien.",
        "settings_title": "Einstellungen",
        "choose_language": "Sprache wählen:",
        "language_saved": "Sprache auf {language} gesetzt.",
        "wholesale_not_configured": "Wholesale-Anfragen sind für diesen Shop nicht konfiguriert.",
        "wholesale_title": "🏢 *Wholesale: {product}*\n\nMengenbereich auswählen:",
        "location_prompt": "🌍 *Wo bist du?*",
        "submit_inquiry": "📤 Anfrage senden",
        "review": "📋 *Prüfen:*\n📦 {product}\n🔢 {qty}\n📍 {location}\n\nBereit zum Senden?",
        "cancelled": "Abgebrochen.",
    },
    "es": {
        "welcome": "Explora el catálogo abajo o escribe lo que buscas.",
        "empty_catalog": "El catálogo está vacío por ahora.",
        "all_items": "🗺️ Todos los artículos",
        "view_cart": "🛒 Ver carrito",
        "site_sections": "📖 Secciones del sitio",
        "settings": "⚙️ Ajustes",
        "language": "🌐 Idioma",
        "open_store": "🌐 Abrir tienda",
        "back": "⬅️ Atrás",
        "back_to_shop": "⬅️ Volver a la tienda",
        "cancel": "⬅️ Cancelar",
        "no_items": "No se encontraron artículos.",
        "tap_to_view": "Toca para ver:",
        "sections_title": "Secciones de {shop_name}",
        "no_sections": "Aún no hay secciones del sitio configuradas.",
        "restricted": "Este artículo no está disponible a través del bot de Telegram.",
        "checkout_site": "🌐 Pagar en el sitio",
        "checkout_site_count": "🌐 Pagar en el sitio ({count} artículos)",
        "choose_option": "🛒 Elegir opción",
        "add_to_cart": "🛒 Añadir al carrito",
        "sold_out": "Agotado",
        "view_online": "🌐 Ver en línea",
        "wholesale": "🏢 Mayorista",
        "share": "📤 Compartir",
        "price": "Precio",
        "description": "Descripción",
        "options": "Opciones:",
        "more_on_site": "+{count} más en el sitio web",
        "choose_option_for": "Elige una opción para {product}:",
        "select_quantity": "{product}\n{option}\n\nSelecciona la cantidad:",
        "option_sold_out": "Esa opción está agotada.",
        "not_available_alert": "Este artículo no está disponible en el bot.",
        "cart_empty": "Tu carrito está vacío.",
        "cart_title": "🛒 *Tu carrito — {shop_name}*\n━━━━━━━━━━━━━━",
        "total": "💰 *Total: {amount}*",
        "clear_cart": "🪟 Vaciar carrito",
        "cart_cleared": "¡Carrito vaciado!",
        "added": "¡{qty}x añadido! 🛒",
        "nothing_found": "No se encontró nada. Prueba a explorar las categorías.",
        "settings_title": "Ajustes",
        "choose_language": "Elige idioma:",
        "language_saved": "Idioma configurado en {language}.",
        "wholesale_not_configured": "Las consultas de mayorista no están configuradas para esta tienda.",
        "wholesale_title": "🏢 *Mayorista: {product}*\n\nSelecciona el rango de cantidad:",
        "location_prompt": "🌍 *¿Dónde te encuentras?*",
        "submit_inquiry": "📤 Enviar consulta",
        "review": "📋 *Revisar:*\n📦 {product}\n🔢 {qty}\n📍 {location}\n\n¿Listo para enviar?",
        "cancelled": "Cancelado.",
    },
    "pt": {
        "welcome": "Explora o catálogo abaixo ou escreve o que procuras.",
        "empty_catalog": "O catálogo está vazio de momento.",
        "all_items": "🗺️ Todos os artigos",
        "view_cart": "🛒 Ver carrinho",
        "site_sections": "📖 Secções do site",
        "settings": "⚙️ Definições",
        "language": "🌐 Idioma",
        "open_store": "🌐 Abrir loja",
        "back": "⬅️ Voltar",
        "back_to_shop": "⬅️ Voltar à loja",
        "cancel": "⬅️ Cancelar",
        "no_items": "Nenhum artigo encontrado.",
        "tap_to_view": "Toca para ver:",
        "sections_title": "Secções de {shop_name}",
        "no_sections": "Ainda não há secções do site configuradas.",
        "restricted": "Este artigo não está disponível através do bot do Telegram.",
        "checkout_site": "🌐 Finalizar no site",
        "checkout_site_count": "🌐 Finalizar no site ({count} artigos)",
        "choose_option": "🛒 Escolher opção",
        "add_to_cart": "🛒 Adicionar ao carrinho",
        "sold_out": "Esgotado",
        "view_online": "🌐 Ver online",
        "wholesale": "🏢 Grossista",
        "share": "📤 Partilhar",
        "price": "Preço",
        "description": "Descrição",
        "options": "Opções:",
        "more_on_site": "+{count} mais no site",
        "choose_option_for": "Escolhe uma opção para {product}:",
        "select_quantity": "{product}\n{option}\n\nSeleciona a quantidade:",
        "option_sold_out": "Essa opção está esgotada.",
        "not_available_alert": "Este artigo não está disponível no bot.",
        "cart_empty": "O teu carrinho está vazio.",
        "cart_title": "🛒 *O teu carrinho — {shop_name}*\n━━━━━━━━━━━━━━",
        "total": "💰 *Total: {amount}*",
        "clear_cart": "🪟 Esvaziar carrinho",
        "cart_cleared": "Carrinho esvaziado!",
        "added": "{qty}x adicionado! 🛒",
        "nothing_found": "Nada encontrado. Tenta explorar as categorias.",
        "settings_title": "Definições",
        "choose_language": "Escolhe o idioma:",
        "language_saved": "Idioma definido para {language}.",
        "wholesale_not_configured": "As consultas de grossista não estão configuradas para esta loja.",
        "wholesale_title": "🏢 *Grossista: {product}*\n\nSeleciona o intervalo de quantidade:",
        "location_prompt": "🌍 *Onde te encontras?*",
        "submit_inquiry": "📤 Enviar consulta",
        "review": "📋 *Rever:*\n📦 {product}\n🔢 {qty}\n📍 {location}\n\nPronto para enviar?",
        "cancelled": "Cancelado.",
    },
    "nl": {
        "welcome": "Blader hieronder door de catalogus of typ gewoon waar je naar op zoek bent.",
        "empty_catalog": "De catalogus is op dit moment leeg.",
        "all_items": "🗺️ Alle artikelen",
        "view_cart": "🛒 Winkelwagen bekijken",
        "site_sections": "📖 Sitesecties",
        "settings": "⚙️ Instellingen",
        "language": "🌐 Taal",
        "open_store": "🌐 Winkel openen",
        "back": "⬅️ Terug",
        "back_to_shop": "⬅️ Terug naar de winkel",
        "cancel": "⬅️ Annuleren",
        "no_items": "Geen artikelen gevonden.",
        "tap_to_view": "Tik om te bekijken:",
        "sections_title": "{shop_name} secties",
        "no_sections": "Er zijn nog geen sitesecties geconfigureerd.",
        "restricted": "Dit artikel is niet beschikbaar via de Telegram-bot.",
        "checkout_site": "🌐 Afrekenen op de site",
        "checkout_site_count": "🌐 Afrekenen op de site ({count} artikelen)",
        "choose_option": "🛒 Optie kiezen",
        "add_to_cart": "🛒 In winkelwagen",
        "sold_out": "Uitverkocht",
        "view_online": "🌐 Online bekijken",
        "wholesale": "🏢 Groothandel",
        "share": "📤 Delen",
        "price": "Prijs",
        "description": "Beschrijving",
        "options": "Opties:",
        "more_on_site": "+{count} meer op de website",
        "choose_option_for": "Kies een optie voor {product}:",
        "select_quantity": "{product}\n{option}\n\nSelecteer aantal:",
        "option_sold_out": "Die optie is uitverkocht.",
        "not_available_alert": "Dit artikel is niet beschikbaar in de bot.",
        "cart_empty": "Je winkelwagen is leeg.",
        "cart_title": "🛒 *Jouw winkelwagen — {shop_name}*\n━━━━━━━━━━━━━━",
        "total": "💰 *Totaal: {amount}*",
        "clear_cart": "🪟 Winkelwagen legen",
        "cart_cleared": "Winkelwagen geleegd!",
        "added": "{qty}x toegevoegd! 🛒",
        "nothing_found": "Niets gevonden. Probeer door categorieën te bladeren.",
        "settings_title": "Instellingen",
        "choose_language": "Kies taal:",
        "language_saved": "Taal ingesteld op {language}.",
        "wholesale_not_configured": "Groothandelaanvragen zijn niet geconfigureerd voor deze winkel.",
        "wholesale_title": "🏢 *Groothandel: {product}*\n\nSelecteer hoeveelheidsbereik:",
        "location_prompt": "🌍 *Waar bevind je je?*",
        "submit_inquiry": "📤 Aanvraag verzenden",
        "review": "📋 *Controleren:*\n📦 {product}\n🔢 {qty}\n📍 {location}\n\nKlaar om te verzenden?",
        "cancelled": "Geannuleerd.",
    },
}


def _product_text(product) -> str:
    return " ".join(
        [
            product.title or "",
            product.description or "",
            " ".join(product.tags or []),
            " ".join(product.categories or []),
        ]
    ).lower()


def _is_restricted_product(product) -> bool:
    if not RESTRICTED_KEYWORDS:
        return False
    return any(keyword in _product_text(product) for keyword in RESTRICTED_KEYWORDS)


def _normalize_category(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")


def _category_for_product(product) -> str:
    for cat in (product.categories or []):
        slug = _normalize_category(cat)
        if slug and slug != "products":
            return slug
    return "shop"


VISIBLE_PRODUCT_INDEXES = [idx for idx, product in enumerate(products) if not _is_restricted_product(product)]
HAS_RESTRICTED_PRODUCTS = len(VISIBLE_PRODUCT_INDEXES) < len(products)

# Derive category slugs + display labels from the visible catalog itself.
CATEGORY_LABELS = {}
CAT_NAMES = {}
for idx in VISIBLE_PRODUCT_INDEXES:
    cat = _category_for_product(products[idx])
    if cat not in CATEGORY_LABELS:
        CATEGORY_LABELS[cat] = getattr(products[idx], "category_label", "") or cat.replace("-", " ").title()
    CAT_NAMES.setdefault(cat, cat)

# ── SEMANTIC SEARCH ─────────────────────────────────────────────────
_model = None
_index = None
np = None
if products and ENABLE_SEMANTIC_SEARCH:
    print("Building semantic index...")
    try:
        from sentence_transformers import SentenceTransformer
        import faiss
        import numpy as np

        _model = SentenceTransformer("all-MiniLM-L6-v2")
        _descriptions = [f"{p.title} {p.description}" for p in products]
        _embeddings = _model.encode(_descriptions)
        _dimension = _embeddings.shape[1]
        _index = faiss.IndexFlatL2(_dimension)
        _index.add(np.array(_embeddings).astype("float32"))
    except ImportError:
        logging.warning("Semantic search dependencies are not installed; using keyword search.")

# ── STATES ──────────────────────────────────────────────────────────
ASK_QTY, ASK_LOC = range(2)

# ── HELPERS ─────────────────────────────────────────────────────────
def _user(update: Update) -> dict:
    u = update.effective_user
    return {"user_id": u.id or 0, "username": u.username or "",
            "first_name": u.first_name or "", "chat_id": update.effective_chat.id or 0}

def _fmt_price(val) -> str:
    if isinstance(val, str):
        return val
    return f"${val:.2f}"


def _html(value) -> str:
    return html.escape(str(value or ""), quote=False)


def _clean_inline(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _clip(text: str, max_len: int = 650) -> str:
    text = re.sub(r"[ \t]+", " ", text or "").strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def _price_to_float(val) -> float:
    if isinstance(val, (int, float)):
        return float(val)

    match = re.search(r"\d+(?:,\d{3})*(?:\.\d+)?", str(val or ""))
    if not match:
        return 0.0

    return float(match.group(0).replace(",", ""))


def _checkout_url_for_cart(cart: list) -> str:
    if cart and all(item.get("variant_id") for item in cart):
        parts = ",".join(f"{item['variant_id']}:{item.get('qty', 1)}" for item in cart)
        return f"{SHOP_URL.rstrip('/')}/cart/{parts}"

    if len(cart) == 1 and cart[0].get("url"):
        return cart[0]["url"]

    return SHOP_URL


def _has_admin_handle() -> bool:
    return ADMIN_HANDLE.startswith("@") and len(ADMIN_HANDLE) > 1


def _is_admin(user) -> bool:
    if not _has_admin_handle() or not user:
        return False
    return (user.username or "").lower() == ADMIN_HANDLE[1:].lower()


def _track_subscriber(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id if update.effective_chat else None
    if chat_id is None:
        return
    context.bot_data.setdefault("subscribers", set()).add(chat_id)


def _default_language() -> str:
    return DEFAULT_LANGUAGE if DEFAULT_LANGUAGE in LANGUAGE_OPTIONS else "en"


def _lang(context: ContextTypes.DEFAULT_TYPE) -> str:
    if not context:
        return _default_language()
    language = context.user_data.get("language", _default_language())
    return language if language in LANGUAGE_OPTIONS else _default_language()


def _t(context: ContextTypes.DEFAULT_TYPE, key: str, **kwargs) -> str:
    language = _lang(context)
    template = TEXT.get(language, TEXT["en"]).get(key, TEXT["en"][key])
    return template.format(**kwargs)


def _language_name(language: str) -> str:
    return LANGUAGE_OPTIONS.get(language, LANGUAGE_OPTIONS["en"])


def _category_label(cat: str, language: str = "en") -> str:
    # Category labels come from the store's own taxonomy, so they are not translated.
    return CATEGORY_LABELS.get(cat) or f"🏷️ {cat.replace('-', ' ').title()}"


def _available_variants(product) -> list:
    variants = product.variants or []
    if not variants and product.variant_id:
        variants = [
            {
                "id": product.variant_id,
                "title": "Default",
                "price": product.price,
                "available": True,
                "options": [],
                "image": product.image,
            }
        ]
    return [variant for variant in variants if variant.get("id")]


def _variant_label(variant: dict, language: str = "en") -> str:
    title = variant.get("title") or "Default"
    options = [value for value in variant.get("options", []) if value and value != "Default Title"]
    if options:
        title = " / ".join(options)
    if title == "Default Title":
        title = "Default"
    price = variant.get("price") or ""
    stock = "" if variant.get("available", True) else f" · {TEXT.get(language, TEXT['en'])['sold_out'].lower()}"
    return f"{title} — {price}{stock}".strip(" —")


def _variant_summary(product, context: ContextTypes.DEFAULT_TYPE = None, limit: int = 6, formatted: bool = False) -> str:
    variants = _available_variants(product)
    if not variants:
        return ""
    language = _lang(context)
    labels = [_variant_label(variant, language) for variant in variants[:limit]]
    extra = len(variants) - len(labels)
    title = _t(context, "options").rstrip(":")
    if formatted:
        lines = [f"<b>{_html(title)}</b>"] + [f"• {_html(label)}" for label in labels]
    else:
        lines = [_t(context, "options")] + [f"• {label}" for label in labels]
    if extra > 0:
        extra_text = _t(context, "more_on_site", count=extra)
        lines.append(f"• {_html(extra_text) if formatted else extra_text}")
    return "\n".join(lines)


def _product_card_text(product, context: ContextTypes.DEFAULT_TYPE = None) -> str:
    parts = [
        f"<b>{_html(product.title)}</b>",
        f"<b>{_html(_t(context, 'price'))}</b>\n{_html(_fmt_price(product.price))}",
    ]
    description = _clip(_clean_inline(product.description), 430)
    if description:
        parts.append(f"<b>{_html(_t(context, 'description'))}</b>\n{_html(description)}")
    variant_text = _variant_summary(product, context, formatted=True)
    if variant_text:
        parts.append(variant_text)
    return "\n\n".join(parts)


def _money_symbol_for_cart(cart: list) -> str:
    for item in cart:
        price = str(item.get("price") or "").strip()
        if price and not price[0].isdigit():
            return price[0]
    return "$"


def _keyword_search(query_text: str, limit: int = 5) -> list:
    terms = [term for term in re.findall(r"[a-z0-9]+", query_text.lower()) if len(term) > 1]
    if not terms:
        return []

    scored = []
    for idx in VISIBLE_PRODUCT_INDEXES:
        product = products[idx]
        haystack = " ".join(
            [
                product.title,
                product.description,
                " ".join(product.tags),
                " ".join(product.categories),
            ]
        ).lower()
        score = sum(haystack.count(term) for term in terms)
        if score:
            scored.append((score, idx))

    scored.sort(reverse=True)
    return [idx for _, idx in scored[:limit]]


def _start_text(context: ContextTypes.DEFAULT_TYPE) -> str:
    body = SHOP_TAGLINE or _t(context, "welcome")
    return f"🛍️ *{SHOP_NAME}*\n\n{body}"


# ════════════════════════════════════════════════════════════════════
#  1. MAIN MENU
# ════════════════════════════════════════════════════════════════════
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _track_subscriber(update, context)
    language = _lang(context)
    text = _start_text(context)
    kb = []
    cat_items = list(CAT_NAMES.items())
    for i in range(0, len(cat_items), 2):
        row = [InlineKeyboardButton(_category_label(cat_items[i][0], language), callback_data=f"cat:{cat_items[i][0]}")]
        if i + 1 < len(cat_items):
            row.append(InlineKeyboardButton(_category_label(cat_items[i + 1][0], language), callback_data=f"cat:{cat_items[i+1][0]}"))
        kb.append(row)
    if VISIBLE_PRODUCT_INDEXES:
        kb.append([InlineKeyboardButton(_t(context, "all_items"), callback_data="cat:all")])
        kb.append([
            InlineKeyboardButton(_t(context, "view_cart"), callback_data="cart_show"),
            InlineKeyboardButton(_t(context, "site_sections"), callback_data="sections_show"),
        ])
    else:
        text = f"🛍️ *{SHOP_NAME}*\n\n{_t(context, 'empty_catalog')}"
    if SHOP_BADGES:
        text = f"{text}\n\n{SHOP_BADGES}"
    if SITE_SECTIONS and not VISIBLE_PRODUCT_INDEXES:
        kb.append([InlineKeyboardButton(_t(context, "site_sections"), callback_data="sections_show")])
    kb.append([InlineKeyboardButton(_t(context, "language"), callback_data="lang_show")])
    if not HAS_RESTRICTED_PRODUCTS:
        kb.append([InlineKeyboardButton(_t(context, "open_store"), url=SHOP_URL)])
    reply_markup = InlineKeyboardMarkup(kb)
    chat_id = update.effective_chat.id

    if BANNER_IMG and os.path.exists(BANNER_IMG):
        try:
            with open(BANNER_IMG, "rb") as photo:
                await context.bot.send_photo(chat_id=chat_id, photo=photo, caption=text,
                                             reply_markup=reply_markup, parse_mode="Markdown")
            return
        except Exception:
            pass
    try:
        await context.bot.send_photo(chat_id=chat_id, photo=BANNER_IMG or "https://placehold.co/800x400",
                                     caption=text, reply_markup=reply_markup, parse_mode="Markdown")
    except Exception:
        await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup, parse_mode="Markdown")


# ════════════════════════════════════════════════════════════════════
#  2. CATEGORY LISTING
# ════════════════════════════════════════════════════════════════════
async def show_category(update: Update, context: ContextTypes.DEFAULT_TYPE, cat: str):
    q = update.callback_query
    if q:
        await q.answer()
    language = _lang(context)

    if cat == "all":
        matching = [(idx, products[idx]) for idx in VISIBLE_PRODUCT_INDEXES]
    else:
        matching = [(idx, products[idx]) for idx in VISIBLE_PRODUCT_INDEXES if _category_for_product(products[idx]) == cat]

    if not matching:
        text = _t(context, "no_items")
        kb = [[InlineKeyboardButton(_t(context, "back"), callback_data="cat:start_mock")]]
        if q:
            if q.message.caption:
                await q.edit_message_caption(caption=text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
            else:
                await q.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
        return

    header = f"{_category_label(cat, language)} ({len(matching)} items)\n\n{_t(context, 'tap_to_view')}"
    kb = []
    for idx, p in matching[:20]:
        kb.append([InlineKeyboardButton(p.title, callback_data=f"prod_show:{idx}")])
    kb.append([InlineKeyboardButton(_t(context, "back"), callback_data="cat:start_mock")])
    if q:
        if q.message.caption:
            await q.edit_message_caption(caption=header, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
        else:
            await q.edit_message_text(text=header, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")


# ════════════════════════════════════════════════════════════════════
#  3. SITE SECTIONS
# ════════════════════════════════════════════════════════════════════
async def show_site_sections(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q:
        await q.answer()

    text = _t(context, "sections_title", shop_name=SHOP_NAME)
    if not SITE_SECTIONS:
        text = _t(context, "no_sections")
        kb = [[InlineKeyboardButton(_t(context, "back"), callback_data="cat:start_mock")]]
    else:
        kb = [[InlineKeyboardButton(section["title"], url=section["url"])] for section in SITE_SECTIONS]
        kb.append([InlineKeyboardButton(_t(context, "back"), callback_data="cat:start_mock")])

    if q:
        if q.message.caption:
            await q.edit_message_caption(caption=text, reply_markup=InlineKeyboardMarkup(kb))
        else:
            await q.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(kb))
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=InlineKeyboardMarkup(kb))


# ════════════════════════════════════════════════════════════════════
#  4. PRODUCT CARD
# ════════════════════════════════════════════════════════════════════
async def show_product(update: Update, context: ContextTypes.DEFAULT_TYPE, idx: int, edit=False):
    p = products[idx]
    if _is_restricted_product(p):
        await context.bot.send_message(chat_id=update.effective_chat.id, text=_t(context, "restricted"))
        return

    cart = context.user_data.get("cart", [])
    cart_n = sum(item.get("qty", 1) for item in cart)
    checkout_txt = _t(context, "checkout_site_count", count=cart_n) if cart_n > 0 else _t(context, "checkout_site")

    text = _product_card_text(p, context)
    variants = _available_variants(p)
    available_variant_indexes = [variant_idx for variant_idx, variant in enumerate(variants) if variant.get("available", True)]
    if not available_variant_indexes:
        add_label = _t(context, "sold_out")
        add_callback = "noop"
    elif len(available_variant_indexes) > 1:
        add_label = _t(context, "choose_option")
        add_callback = f"variant_show:{idx}"
    else:
        add_label = _t(context, "add_to_cart")
        add_callback = f"qty_sel:{idx}:{available_variant_indexes[0]}"

    actions = [
        [InlineKeyboardButton(add_label, callback_data=add_callback),
         InlineKeyboardButton(_t(context, "view_online"), url=p.url)],
        [InlineKeyboardButton(checkout_txt, callback_data="cart_show")],
    ]
    if _has_admin_handle():
        actions.append([
            InlineKeyboardButton(_t(context, "wholesale"), callback_data="wholesale_start"),
            InlineKeyboardButton(_t(context, "share"), switch_inline_query=p.title),
        ])
    else:
        actions.append([InlineKeyboardButton(_t(context, "share"), switch_inline_query=p.title)])
    actions.append([InlineKeyboardButton(_t(context, "back"), callback_data="cat:start_mock")])
    kb = actions
    reply_markup = InlineKeyboardMarkup(kb)
    chat_id = update.effective_chat.id

    if edit and update.callback_query:
        q = update.callback_query
        if q.message.caption:
            await q.edit_message_caption(caption=_clip(text, 950), reply_markup=reply_markup, parse_mode="HTML")
        else:
            await q.edit_message_text(text=text, reply_markup=reply_markup, parse_mode="HTML")
        return

    image = p.image or (p.images[0] if p.images else "")
    if image:
        try:
            await context.bot.send_photo(chat_id=chat_id, photo=image, caption=_clip(text, 950),
                                          reply_markup=reply_markup, parse_mode="HTML")
            return
        except Exception:
            pass
    await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup, parse_mode="HTML")


async def show_variant_selector(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    idx = int(q.data.split(":")[1])
    p = products[idx]
    if _is_restricted_product(p):
        await context.bot.send_message(chat_id=update.effective_chat.id, text=_t(context, "restricted"))
        return
    variants = _available_variants(p)
    language = _lang(context)
    text = _t(context, "choose_option_for", product=p.title)
    kb = []
    for variant_idx, variant in enumerate(variants[:20]):
        label = _variant_label(variant, language)
        callback = f"qty_sel:{idx}:{variant_idx}" if variant.get("available", True) else "noop"
        kb.append([InlineKeyboardButton(label, callback_data=callback)])
    kb.append([InlineKeyboardButton(_t(context, "back"), callback_data=f"prod_back:{idx}")])
    if q.message.caption:
        await q.edit_message_caption(caption=text, reply_markup=InlineKeyboardMarkup(kb))
    else:
        await q.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(kb))


# ════════════════════════════════════════════════════════════════════
#  5. QUANTITY SELECTOR
# ════════════════════════════════════════════════════════════════════
async def select_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    parts = q.data.split(":")
    idx = int(parts[1])
    variant_idx = int(parts[2]) if len(parts) > 2 else 0
    p = products[idx]
    if _is_restricted_product(p):
        await q.answer(_t(context, "not_available_alert"), show_alert=True)
        return
    variants = _available_variants(p)
    variant = variants[variant_idx] if variant_idx < len(variants) else {}
    if variant and not variant.get("available", True):
        await q.answer(_t(context, "option_sold_out"), show_alert=True)
        return
    cart = context.user_data.get("cart", [])
    cart_n = sum(item.get("qty", 1) for item in cart)
    checkout_txt = _t(context, "checkout_site_count", count=cart_n) if cart_n > 0 else _t(context, "checkout_site")

    option_text = _variant_label(variant, _lang(context)) if variant else _fmt_price(p.price)
    text = _t(context, "select_quantity", product=p.title, option=option_text)
    kb = [
        [InlineKeyboardButton("1x", callback_data=f"add_cart:{idx}:{variant_idx}:1"),
         InlineKeyboardButton("2x", callback_data=f"add_cart:{idx}:{variant_idx}:2"),
         InlineKeyboardButton("5x", callback_data=f"add_cart:{idx}:{variant_idx}:5")],
        [InlineKeyboardButton("10x", callback_data=f"add_cart:{idx}:{variant_idx}:10"),
         InlineKeyboardButton("25x", callback_data=f"add_cart:{idx}:{variant_idx}:25")],
        [InlineKeyboardButton(checkout_txt, callback_data="cart_show")],
        [InlineKeyboardButton(_t(context, "cancel"), callback_data=f"prod_back:{idx}")],
    ]
    if q.message.caption:
        await q.edit_message_caption(caption=text, reply_markup=InlineKeyboardMarkup(kb))
    else:
        await q.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(kb))


# ════════════════════════════════════════════════════════════════════
#  6. ADD TO CART
# ════════════════════════════════════════════════════════════════════
async def add_to_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    parts = q.data.split(":")
    if len(parts) == 3:
        idx, variant_idx, qty = int(parts[1]), 0, int(parts[2])
    else:
        idx, variant_idx, qty = int(parts[1]), int(parts[2]), int(parts[3])
    p = products[idx]
    if _is_restricted_product(p):
        await q.answer(_t(context, "not_available_alert"), show_alert=True)
        return
    variants = _available_variants(p)
    variant = variants[variant_idx] if variant_idx < len(variants) else {}
    if variant and not variant.get("available", True):
        await q.answer(_t(context, "option_sold_out"), show_alert=True)
        return
    variant_id = variant.get("id") or p.variant_id
    variant_title = _variant_label(variant, _lang(context)).split(" — ")[0] if variant else ""
    price = variant.get("price") or p.price
    item_title = f"{p.title} ({variant_title})" if variant_title and variant_title != "Default" else p.title

    if "cart" not in context.user_data:
        context.user_data["cart"] = []

    found = False
    for item in context.user_data["cart"]:
        if item.get("variant_id") == variant_id:
            item["qty"] = item.get("qty", 0) + qty
            found = True
            break
    if not found:
        item = {"title": item_title, "price": price, "url": p.url,
                "image": variant.get("image") or p.image, "variant_id": variant_id, "qty": qty}
        context.user_data["cart"].append(item)

    await q.answer(_t(context, "added", qty=qty))
    await show_product(update, context, idx, edit=True)


# ════════════════════════════════════════════════════════════════════
#  7. CART
# ════════════════════════════════════════════════════════════════════
async def show_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cart = context.user_data.get("cart", [])
    if not cart:
        text = _t(context, "cart_empty")
        if update.callback_query:
            await update.callback_query.message.reply_text(text)
        else:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
        return

    symbol = _money_symbol_for_cart(cart)
    lines = [_t(context, "cart_title", shop_name=SHOP_NAME)]
    total = 0.0
    for item in cart:
        price = _price_to_float(item.get("price"))
        sub = price * item.get("qty", 1)
        total += sub
        lines.append(f"• {item.get('qty',1)}x {item['title']} — {symbol}{sub:.2f}")
    lines.append("━━━━━━━━━━━━━━")
    lines.append(_t(context, "total", amount=f"{symbol}{total:.2f}"))

    checkout_url = _checkout_url_for_cart(cart)

    kb = [
        [InlineKeyboardButton(_t(context, "checkout_site"), url=checkout_url)],
        [InlineKeyboardButton(_t(context, "clear_cart"), callback_data="cart_clear")],
        [InlineKeyboardButton(_t(context, "back_to_shop"), callback_data="cat:start_mock")],
    ]
    await context.bot.send_message(chat_id=update.effective_chat.id, text="\n".join(lines),
                                    reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

async def clear_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer(_t(context, "cart_cleared"))
    context.user_data["cart"] = []
    await start(update, context)


# ════════════════════════════════════════════════════════════════════
#  8. WHOLESALE FLOW (optional — only active when ADMIN_HANDLE is set)
# ════════════════════════════════════════════════════════════════════
async def wholesale_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not _has_admin_handle():
        await context.bot.send_message(chat_id=update.effective_chat.id, text=_t(context, "wholesale_not_configured"))
        return ConversationHandler.END

    prod = context.user_data.get("last_seen_product", "a product")
    context.user_data["wholesale_product"] = prod
    text = _t(context, "wholesale_title", product=prod)
    kb = [
        [InlineKeyboardButton("10–50", callback_data="qty:10-50"),
         InlineKeyboardButton("50–100", callback_data="qty:50-100")],
        [InlineKeyboardButton("100–500", callback_data="qty:100-500"),
         InlineKeyboardButton("500+", callback_data="qty:500+")],
    ]
    await context.bot.send_message(chat_id=update.effective_chat.id, text=text,
                                    reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    return ASK_QTY

async def wholesale_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["wholesale_qty"] = q.data.split(":")[1]
    text = _t(context, "location_prompt")
    kb = [
        [InlineKeyboardButton("🇪🇺 Europe", callback_data="loc:Europe"),
         InlineKeyboardButton("🇺🇸 North America", callback_data="loc:North America")],
        [InlineKeyboardButton("🌍 International", callback_data="loc:International")],
    ]
    await context.bot.send_message(chat_id=update.effective_chat.id, text=text,
                                    reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    return ASK_LOC

async def wholesale_loc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    loc = q.data.split(":")[1]
    prod = context.user_data.get("wholesale_product", "")
    qty  = context.user_data.get("wholesale_qty", "")
    user = update.effective_user
    inquiry = (
        f"📬 NEW WHOLESALE INQUIRY\n"
        f"━━━━━━━━━━━━━━\n"
        f"📦 {prod}\n🔢 {qty}\n📍 {loc}\n"
        f"👤 @{user.username} ({user.first_name})\n"
        f"━━━━━━━━━━━━━━"
    )
    dm_link = f"https://t.me/{ADMIN_HANDLE[1:]}?text={urllib.parse.quote(inquiry)}"
    kb = [
        [InlineKeyboardButton(_t(context, "submit_inquiry"), url=dm_link)],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")],
    ]
    await context.bot.send_message(chat_id=update.effective_chat.id,
        text=_t(context, "review", product=prod, qty=qty, location=loc),
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    return ConversationHandler.END

async def wholesale_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text=_t(context, "cancelled"))
    return ConversationHandler.END


# ════════════════════════════════════════════════════════════════════
#  9. LANGUAGE SETTINGS
# ════════════════════════════════════════════════════════════════════
async def show_language_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q:
        await q.answer()

    current = _lang(context)
    text = _t(context, "choose_language")
    kb = []
    for code, label in LANGUAGE_OPTIONS.items():
        prefix = "✓ " if code == current else ""
        kb.append([InlineKeyboardButton(f"{prefix}{label}", callback_data=f"lang_set:{code}")])
    kb.append([InlineKeyboardButton(_t(context, "back"), callback_data="cat:start_mock")])
    reply_markup = InlineKeyboardMarkup(kb)

    if q:
        if q.message.caption:
            await q.edit_message_caption(caption=text, reply_markup=reply_markup)
        else:
            await q.edit_message_text(text=text, reply_markup=reply_markup)
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=reply_markup)


async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    code = q.data.split(":")[1]
    if code not in LANGUAGE_OPTIONS:
        return

    context.user_data["language"] = code
    await q.answer(_t(context, "language_saved", language=_language_name(code)))
    await show_language_settings(update, context)


# ════════════════════════════════════════════════════════════════════
#  10. ADMIN BROADCAST (optional — requires ADMIN_HANDLE)
# ════════════════════════════════════════════════════════════════════
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user):
        return  # silently ignore for non-admins

    message = update.message.text.partition(" ")[2].strip() if update.message else ""
    if not message:
        await update.message.reply_text("Usage: /broadcast <message to all users>")
        return

    subscribers = list(context.bot_data.get("subscribers", set()))
    sent = 0
    for chat_id in subscribers:
        try:
            await context.bot.send_message(chat_id=chat_id, text=message)
            sent += 1
        except Exception:
            pass
    await update.message.reply_text(f"📣 Broadcast delivered to {sent}/{len(subscribers)} users.")


# ════════════════════════════════════════════════════════════════════
#  11. SEARCH (semantic if enabled, otherwise keyword)
# ════════════════════════════════════════════════════════════════════
async def search_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _track_subscriber(update, context)
    query_text = update.message.text if update.message else ""
    if not query_text:
        return

    if _index is not None and _model is not None and np is not None:
        vec = _model.encode([query_text])
        _, matches = _index.search(np.array(vec).astype("float32"), k=5)
        result_indexes = [i for i in matches[0] if i != -1 and i in VISIBLE_PRODUCT_INDEXES]
    else:
        result_indexes = _keyword_search(query_text)

    for i in result_indexes:
        await show_product(update, context, i)

    found = bool(result_indexes)
    if not found:
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text=_t(context, "nothing_found"))


# ════════════════════════════════════════════════════════════════════
#  12. BUTTON ROUTER
# ════════════════════════════════════════════════════════════════════
async def button_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data

    if data.startswith("cat:"):
        target = data.split(":")[1]
        if target == "start_mock":
            await start(update, context)
        elif target == "all":
            await show_category(update, context, "all")
        elif target in CAT_NAMES:
            await show_category(update, context, target)

    elif data.startswith("prod_show:"):
        idx = int(data.split(":")[1])
        context.user_data["last_seen_product"] = products[idx].title
        await show_product(update, context, idx)

    elif data.startswith("variant_show:"):
        await show_variant_selector(update, context)

    elif data.startswith("qty_sel:"):
        await select_quantity(update, context)

    elif data.startswith("add_cart:"):
        await add_to_cart(update, context)

    elif data.startswith("prod_back:"):
        idx = int(data.split(":")[1])
        await show_product(update, context, idx, edit=True)

    elif data == "cart_show":
        await show_cart(update, context)
    elif data == "cart_clear":
        await clear_cart(update, context)
    elif data == "sections_show":
        await show_site_sections(update, context)
    elif data == "lang_show":
        await show_language_settings(update, context)
    elif data.startswith("lang_set:"):
        await set_language(update, context)
    elif data == "noop":
        return


# ════════════════════════════════════════════════════════════════════
#  13. MAIN
# ════════════════════════════════════════════════════════════════════
async def _post_init(app):
    # Populate Telegram's "/" command menu so users see commands as they type.
    commands = [
        BotCommand("start", "Open the shop"),
        BotCommand("language", "Change language"),
    ]
    try:
        await app.bot.set_my_commands(commands)
    except Exception as exc:
        logging.warning("Could not set command menu: %s", exc)


if __name__ == "__main__":
    persistence = PicklePersistence(filepath=PERSIST_FILE)
    app = ApplicationBuilder().token(TOKEN).persistence(persistence).post_init(_post_init).build()

    if _has_admin_handle():
        wholesale_conv = ConversationHandler(
            entry_points=[CallbackQueryHandler(wholesale_start, pattern="^wholesale_start$")],
            states={
                ASK_QTY: [CallbackQueryHandler(wholesale_qty, pattern="^qty:")],
                ASK_LOC: [CallbackQueryHandler(wholesale_loc, pattern="^loc:")],
            },
            fallbacks=[CallbackQueryHandler(wholesale_cancel, pattern="^cancel$")],
            name="wholesale_flow", persistent=True, allow_reentry=True,
        )
        app.add_handler(wholesale_conv)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("language", show_language_settings))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CallbackQueryHandler(button_router))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_products))

    print("Bot starting...")
    app.run_polling(drop_pending_updates=True)
