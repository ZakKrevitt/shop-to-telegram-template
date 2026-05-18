"""
🛍️ Boutique Telegram Commerce Bot — shop-to-telegram-template
===============================================================
Drop-in Telegram bot with category browsing, product cards, cart,
semantic search, copy buttons, and wholesale inquiry flow.

Usage:
  1. pip install -r REQUIREMENTS.txt
  2. Set BOT_TOKEN env var (or hardcode TOKEN below)
  3. Create products.json using scraper.py (or hand-write)
  4. python3 bot.py
"""

import os, json, logging, urllib.parse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, CopyTextButton
from telegram.ext import (
    ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler, PicklePersistence, filters
)
from sentence_transformers import SentenceTransformer
import faiss, numpy as np
from scraper import Product, load_products

# ── CONFIG ──────────────────────────────────────────────────────────
TOKEN        = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN")
ADMIN_HANDLE = os.environ.get("ADMIN_HANDLE", "@your_username")
SHOP_NAME    = os.environ.get("SHOP_NAME", "Your Shop")
SHOP_URL     = os.environ.get("SHOP_URL", "https://your-shop.com")
IBAN         = os.environ.get("IBAN", "YOUR_IBAN_HERE")
BANNER_IMG   = os.environ.get("BANNER_IMG", "")
PERSIST_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot_persistence.pickle")
PRODUCTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "products.json")

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)

# ── LOAD CATALOG ────────────────────────────────────────────────────
products = load_products(PRODUCTS_FILE)
if not products:
    logging.warning("No products loaded! Check products.json")

# Derive categories from products
CAT_NAMES = {}
for p in products:
    for cat in p.categories:
        if cat not in CAT_NAMES:
            CAT_NAMES[cat] = f"🏷️ {cat.title()}"

# ── SEMANTIC SEARCH ─────────────────────────────────────────────────
print("Building semantic index...")
_model = SentenceTransformer("all-MiniLM-L6-v2")
_descriptions = [f"{p.title} {p.description}" for p in products]
_embeddings   = _model.encode(_descriptions) if products else np.array([])
_index        = None
if len(_embeddings) > 0:
    _dimension = _embeddings.shape[1]
    _index = faiss.IndexFlatL2(_dimension)
    _index.add(np.array(_embeddings).astype("float32"))

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


# ════════════════════════════════════════════════════════════════════
#  1. MAIN MENU
# ════════════════════════════════════════════════════════════════════
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = f"🌿 *{SHOP_NAME}*\n\nWelcome! Browse our collection.\n\n*Explore:*"
    kb = []
    cat_items = list(CAT_NAMES.items())
    for i in range(0, len(cat_items), 2):
        row = [InlineKeyboardButton(cat_items[i][1], callback_data=f"cat:{cat_items[i][0]}")]
        if i + 1 < len(cat_items):
            row.append(InlineKeyboardButton(cat_items[i+1][1], callback_data=f"cat:{cat_items[i+1][0]}"))
        kb.append(row)
    kb.append([InlineKeyboardButton("🗺️ All Items", callback_data="cat:all")])
    kb.append([
        InlineKeyboardButton("🛒 View Cart", callback_data="cart_show"),
        InlineKeyboardButton("🏦 Bank Transfer", callback_data="bank_transfer")
    ])
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

    if cat == "all":
        matching = list(enumerate(products))
    else:
        matching = [(i, p) for i, p in enumerate(products) if cat in p.categories]

    if not matching:
        text = f"No items found."
        kb = [[InlineKeyboardButton("⬅️ Back", callback_data="cat:start_mock")]]
        if q:
            await q.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
        return

    header = f"*{CAT_NAMES.get(cat, cat)}* ({len(matching)} items)\n\n_Tap to view:_\n"
    kb = []
    for idx, p in matching[:20]:
        kb.append([InlineKeyboardButton(f"{p.title} — {_fmt_price(p.price)}", callback_data=f"prod_show:{idx}")])
    kb.append([InlineKeyboardButton("⬅️ Back", callback_data="cat:start_mock")])
    if q:
        await q.edit_message_text(text=header, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")


# ════════════════════════════════════════════════════════════════════
#  3. PRODUCT CARD
# ════════════════════════════════════════════════════════════════════
async def show_product(update: Update, context: ContextTypes.DEFAULT_TYPE, idx: int, edit=False):
    p = products[idx]
    cart = context.user_data.get("cart", [])
    cart_n = sum(item.get("qty", 1) for item in cart)
    checkout_txt = f"💳 Checkout ({cart_n} items)" if cart_n > 0 else "💳 Checkout"

    text = (
        f"*{p.title.upper()}*\n"
        f"💰 {_fmt_price(p.price)}  |  📦 In Stock\n\n"
        f"_{p.description}_"
    )
    kb = [
        [InlineKeyboardButton("🛒 Add to Cart", callback_data=f"qty_sel:{idx}"),
         InlineKeyboardButton("🌐 View Online", url=p.url)],
        [InlineKeyboardButton(checkout_txt, callback_data="cart_show")],
        [InlineKeyboardButton("🏢 Wholesale", callback_data="wholesale_start"),
         InlineKeyboardButton("📤 Share", switch_inline_query=p.title)],
        [InlineKeyboardButton("⬅️ Back", callback_data="cat:start_mock")],
    ]
    reply_markup = InlineKeyboardMarkup(kb)
    chat_id = update.effective_chat.id

    if edit and update.callback_query:
        q = update.callback_query
        if q.message.caption:
            await q.edit_message_caption(caption=text, reply_markup=reply_markup, parse_mode="Markdown")
        else:
            await q.edit_message_text(text=text, reply_markup=reply_markup, parse_mode="Markdown")
        return

    if p.image:
        try:
            await context.bot.send_photo(chat_id=chat_id, photo=p.image, caption=text,
                                          reply_markup=reply_markup, parse_mode="Markdown")
            return
        except Exception:
            pass
    await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup, parse_mode="Markdown")


# ════════════════════════════════════════════════════════════════════
#  4. QUANTITY SELECTOR
# ════════════════════════════════════════════════════════════════════
async def select_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    idx = int(q.data.split(":")[1])
    p = products[idx]
    cart = context.user_data.get("cart", [])
    cart_n = sum(item.get("qty", 1) for item in cart)
    checkout_txt = f"💳 Checkout ({cart_n} items)" if cart_n > 0 else "💳 Checkout"

    text = f"🛍️ *{p.title}*\n\nSelect quantity:"
    kb = [
        [InlineKeyboardButton("1x", callback_data=f"add_cart:{idx}:1"),
         InlineKeyboardButton("2x", callback_data=f"add_cart:{idx}:2"),
         InlineKeyboardButton("5x", callback_data=f"add_cart:{idx}:5")],
        [InlineKeyboardButton("10x", callback_data=f"add_cart:{idx}:10"),
         InlineKeyboardButton("25x", callback_data=f"add_cart:{idx}:25")],
        [InlineKeyboardButton(checkout_txt, callback_data="cart_show")],
        [InlineKeyboardButton("⬅️ Cancel", callback_data=f"prod_back:{idx}")],
    ]
    if q.message.caption:
        await q.edit_message_caption(caption=text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    else:
        await q.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")


# ════════════════════════════════════════════════════════════════════
#  5. ADD TO CART
# ════════════════════════════════════════════════════════════════════
async def add_to_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    parts = q.data.split(":")
    idx, qty = int(parts[1]), int(parts[2])
    p = products[idx]

    if "cart" not in context.user_data:
        context.user_data["cart"] = []

    found = False
    for item in context.user_data["cart"]:
        if item["url"] == p.url:
            item["qty"] = item.get("qty", 0) + qty
            found = True
            break
    if not found:
        item = {"title": p.title, "price": p.price, "url": p.url,
                "image": p.image, "variant_id": p.variant_id, "qty": qty}
        context.user_data["cart"].append(item)

    await q.answer(f"Added {qty}x! 🛒")
    await show_product(update, context, idx, edit=True)


# ════════════════════════════════════════════════════════════════════
#  6. CART
# ════════════════════════════════════════════════════════════════════
async def show_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cart = context.user_data.get("cart", [])
    if not cart:
        text = "Your cart is empty."
        if update.callback_query:
            await update.callback_query.message.reply_text(text)
        else:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
        return

    lines = [f"🛒 *Your Cart — {SHOP_NAME}*\n━━━━━━━━━━━━━━"]
    total = 0.0
    for item in cart:
        try:
            price_str = item["price"].replace("$", "").replace(",", "").strip()
            price = float(price_str)
        except:
            price = 0.0
        sub = price * item.get("qty", 1)
        total += sub
        lines.append(f"• {item.get('qty',1)}x {item['title']} — ${sub:.2f}")
    lines.append("━━━━━━━━━━━━━━")
    lines.append(f"💰 *Total: ${total:.2f}*")

    # Build cart permalink if variant_ids exist
    if all(item.get("variant_id") for item in cart):
        parts = ",".join(f"{item['variant_id']}:{item.get('qty',1)}" for item in cart)
        checkout_url = f"{SHOP_URL}/cart/{parts}"
    else:
        checkout_url = SHOP_URL

    kb = [
        [InlineKeyboardButton("💳 Checkout", url=checkout_url)],
        [InlineKeyboardButton("🪟 Clear Cart", callback_data="cart_clear")],
        [InlineKeyboardButton("⬅️ Back to Shop", callback_data="cat:start_mock")],
    ]
    await context.bot.send_message(chat_id=update.effective_chat.id, text="\n".join(lines),
                                    reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

async def clear_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("Cart cleared!")
    context.user_data["cart"] = []
    await start(update, context)


# ════════════════════════════════════════════════════════════════════
#  7. COPY BUTTONS
# ════════════════════════════════════════════════════════════════════
async def show_bank_transfer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q:
        await q.answer()
    text = (
        "🏦 *Bank Transfer*\n\n"
        f"`{IBAN}`\n\n"
        "In Revolut: *Payments → New payment → Send to bank → enter IBAN*"
    )
    kb = [
        [InlineKeyboardButton("📋 Copy IBAN", copy_text=CopyTextButton(text=IBAN))],
        [InlineKeyboardButton("⬅️ Back", callback_data="cat:start_mock")],
    ]
    if q:
        await q.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text,
                                        reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")


# ════════════════════════════════════════════════════════════════════
#  8. WHOLESALE FLOW
# ════════════════════════════════════════════════════════════════════
async def wholesale_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    prod = context.user_data.get("last_seen_product", "a product")
    context.user_data["wholesale_product"] = prod
    text = f"🏢 *Wholesale: {prod}*\n\nSelect quantity range:"
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
    text = "🌍 *Where are you located?*"
    kb = [
        [InlineKeyboardButton("🇩🇪 Berlin", callback_data="loc:Berlin"),
         InlineKeyboardButton("🇪🇺 EU", callback_data="loc:EU")],
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
        f"🧫 {prod}\n🔢 {qty}\n📍 {loc}\n"
        f"👤 @{user.username} ({user.first_name})\n"
        f"━━━━━━━━━━━━━━"
    )
    dm_link = f"https://t.me/{ADMIN_HANDLE[1:]}?text={urllib.parse.quote(inquiry)}"
    kb = [
        [InlineKeyboardButton("📤 Submit Inquiry", url=dm_link)],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")],
    ]
    await context.bot.send_message(chat_id=update.effective_chat.id,
        text=f"📋 *Review:*\n🧫 {prod}\n🔢 {qty}\n📍 {loc}\n\nReady to submit?",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    return ConversationHandler.END

async def wholesale_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Cancelled.")
    return ConversationHandler.END


# ════════════════════════════════════════════════════════════════════
#  9. SEMANTIC SEARCH
# ════════════════════════════════════════════════════════════════════
async def search_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query_text = update.message.text if update.message else ""
    if not query_text or _index is None:
        return
    vec = _model.encode([query_text])
    D, I = _index.search(np.array(vec).astype("float32"), k=5)
    found = False
    for i in I[0]:
        if i == -1 or i >= len(products):
            continue
        found = True
        await show_product(update, context, i)
    if not found:
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text="Nothing found. Try browsing categories.")


# ════════════════════════════════════════════════════════════════════
#  10. BUTTON ROUTER
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
    elif data == "bank_transfer":
        await show_bank_transfer(update, context)


# ════════════════════════════════════════════════════════════════════
#  11. MAIN
# ════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    persistence = PicklePersistence(filepath=PERSIST_FILE)
    app = ApplicationBuilder().token(TOKEN).persistence(persistence).build()

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
    app.add_handler(CallbackQueryHandler(button_router))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_products))

    print("Bot starting...")
    app.run_polling(drop_pending_updates=True)
