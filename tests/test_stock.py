import asyncio
from types import SimpleNamespace

import bot


def _prod(variants, variant_id=""):
    return SimpleNamespace(variants=variants, variant_id=variant_id, price="$1", image="")


# ── _is_in_stock ─────────────────────────────────────────────────────
def test_in_stock_when_a_variant_is_available():
    assert bot._is_in_stock(_prod([{"id": "a", "available": True}])) is True


def test_out_of_stock_when_all_variants_unavailable():
    assert bot._is_in_stock(_prod([{"id": "a", "available": False}])) is False


def test_in_stock_when_any_variant_available():
    p = _prod([{"id": "a", "available": False}, {"id": "b", "available": True}])
    assert bot._is_in_stock(p) is True


def test_no_variant_data_is_treated_as_in_stock():
    # bare variant_id → synthesized default variant (available); and truly empty
    assert bot._is_in_stock(_prod([], variant_id="x")) is True
    assert bot._is_in_stock(_prod([], variant_id="")) is True


# ── start keyboard reflects the toggle state ─────────────────────────
def _ctx(in_stock_only=None):
    ud = {}
    if in_stock_only is not None:
        ud["in_stock_only"] = in_stock_only
    return SimpleNamespace(user_data=ud)


def _toggle_button(markup):
    for row in markup.inline_keyboard:
        for btn in row:
            if btn.callback_data == "stock_toggle":
                return btn
    return None


def test_start_keyboard_has_toggle_and_shows_state():
    off = _toggle_button(bot._start_keyboard(_ctx(False)))
    on = _toggle_button(bot._start_keyboard(_ctx(True)))
    assert off is not None and on is not None
    assert "⬜️" in off.text          # off state
    assert "✅" in on.text            # on state


# ── toggle handler flips the flag and refreshes the menu ─────────────
def test_toggle_flips_and_edits_markup():
    edited = {}

    async def edit_message_reply_markup(reply_markup):
        edited["markup"] = reply_markup

    q = SimpleNamespace(edit_message_reply_markup=edit_message_reply_markup)
    ctx = _ctx()  # starts unset (falsey)
    upd = SimpleNamespace(callback_query=q)

    asyncio.run(bot.toggle_stock_filter(upd, ctx))
    assert ctx.user_data["in_stock_only"] is True
    assert _toggle_button(edited["markup"]).text.endswith("✅")

    asyncio.run(bot.toggle_stock_filter(upd, ctx))
    assert ctx.user_data["in_stock_only"] is False
    assert _toggle_button(edited["markup"]).text.endswith("⬜️")
