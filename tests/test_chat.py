import asyncio
from types import SimpleNamespace

import bot


def _tool_use(reply, product_ids):
    block = SimpleNamespace(type="tool_use", name="recommend_products",
                            input={"reply": reply, "product_ids": product_ids})
    return SimpleNamespace(content=[block])


def _fake_client(response):
    async def create(**kwargs):
        create.kwargs = kwargs
        return response
    return SimpleNamespace(messages=SimpleNamespace(create=create))


def _ctx(user_data=None):
    sent = []

    async def send_message(chat_id, text, **kw):
        sent.append({"text": text, "reply_markup": kw.get("reply_markup")})

    async def send_chat_action(chat_id, action):
        pass

    bot_obj = SimpleNamespace(send_message=send_message, send_chat_action=send_chat_action)
    ctx = SimpleNamespace(bot=bot_obj, user_data=user_data if user_data is not None else {})
    ctx._sent = sent
    return ctx


def _update(text="something calming for the evening"):
    return SimpleNamespace(
        message=SimpleNamespace(text=text),
        callback_query=None,
        effective_chat=SimpleNamespace(id=1),
        effective_user=SimpleNamespace(id=1, username="u", first_name="U", language_code="en"),
    )


def test_chat_enabled_requires_key_and_pkg(monkeypatch):
    monkeypatch.setattr(bot, "ANTHROPIC_API_KEY", "")
    assert bot._chat_enabled() is False
    monkeypatch.setattr(bot, "ANTHROPIC_API_KEY", "sk-x")
    monkeypatch.setattr(bot, "_anthropic_pkg", object())
    assert bot._chat_enabled() is True
    monkeypatch.setattr(bot, "_anthropic_pkg", None)
    assert bot._chat_enabled() is False


def test_recommend_validates_and_dedupes_ids(monkeypatch):
    good = bot.VISIBLE_PRODUCT_INDEXES[:2]
    raw = [good[0], good[1], good[0], 999999, "x"]
    monkeypatch.setattr(bot, "_get_anthropic_client",
                        lambda: _fake_client(_tool_use("Here are a few.", raw)))
    reply, ids = asyncio.run(bot._chat_recommend([{"role": "user", "content": "hi"}]))
    assert reply == "Here are a few."
    assert ids == [good[0], good[1]]


def test_recommend_forces_the_tool(monkeypatch):
    client = _fake_client(_tool_use("ok", []))
    monkeypatch.setattr(bot, "_get_anthropic_client", lambda: client)
    asyncio.run(bot._chat_recommend([{"role": "user", "content": "hi"}]))
    kwargs = client.messages.create.kwargs
    assert kwargs["tool_choice"] == {"type": "tool", "name": "recommend_products"}
    assert kwargs["model"] == bot.CHAT_MODEL


def test_chat_message_renders_menu_and_stays_active(monkeypatch):
    picks = bot.VISIBLE_PRODUCT_INDEXES[:1]

    async def fake_reco(history):
        return "These fit your vibe.", picks
    monkeypatch.setattr(bot, "_chat_recommend", fake_reco)

    ctx = _ctx()
    state = asyncio.run(bot.chat_message(_update(), ctx))
    assert state == bot.CHAT_ACTIVE
    menu = next(m for m in ctx._sent if m["reply_markup"] is not None)
    rows = menu["reply_markup"].inline_keyboard
    assert rows[0][0].callback_data == f"prod_show:{picks[0]}"
    assert rows[-1][0].callback_data == "chat_exit"
    assert [m["role"] for m in ctx.user_data["chat_history"]] == ["user", "assistant"]


def test_chat_message_handles_api_error(monkeypatch):
    async def boom(history):
        raise RuntimeError("api down")
    monkeypatch.setattr(bot, "_chat_recommend", boom)

    ctx = _ctx()
    state = asyncio.run(bot.chat_message(_update(), ctx))
    assert state == bot.CHAT_ACTIVE
    assert ctx.user_data["chat_history"] == []
    assert ctx._sent[-1]["reply_markup"].inline_keyboard[-1][0].callback_data == "chat_exit"
