import json
from pathlib import Path

from bot_harness import env, free_env, no_waiting  # noqa: F401  (fixtures)
import pytest
from tulporgo_bot.delivery import strip_tags
from tulporgo_core import i18n
from tulporgo_core.models import User
from tulporgo_core.services import referral
from tulporgo_core.services import rides as rides_service

APPROVED = json.loads((Path(__file__).resolve().parents[3] / "content/i18n/build/telegram_texts.json")
                      .read_text(encoding="utf-8"))
LANGS = ["uz_new", "uz_latn", "uz_cyrl", "ru", "en"]


async def get_user(env, uid):
    from sqlalchemy import select
    return await env.db(lambda s: s.scalar(select(User).where(User.tg_id == uid)))


@pytest.mark.parametrize("lang", LANGS)
def test_start_and_command_texts_are_the_approved_ones(lang):
    # decision 40: the greeting and the command descriptions are exactly the approved texts
    assert i18n.t("bot.start", lang) == APPROVED["bot.start"]["text"][lang]
    for cmd in ("start", "qatnovlarim", "til", "yordam", "elon", "obuna"):
        assert i18n.t(f"bot.cmd.{cmd}", lang) == APPROVED[f"bot.cmd.{cmd}"]["text"][lang]


async def test_first_start_offers_five_languages(env):
    await env.say(1, "/start")
    assert env.buttons(1) == [f"lang:{c}" for c in LANGS]
    labels = [b.text for b in env.all_buttons(1)]
    assert labels == ["Özbekça", "Oʻzbekcha", "Ўзбекча", "Русский", "English"]
    assert (await get_user(env, 1)).lang is None          # nothing is assumed before the user chooses


@pytest.mark.parametrize("lang", LANGS)
async def test_language_choice_is_saved_and_greeting_follows(env, lang):
    await env.say(1, "/start")
    await env.press(1, f"lang:{lang}")
    assert (await get_user(env, 1)).lang == lang
    greeting = strip_tags(env.last_text(1))
    assert greeting == APPROVED["bot.start"]["text"][lang]
    assert env.buttons(1)[:2] == ["ord:new", "drv:reg"]


async def test_greeting_uses_the_tulpor_head_emoji(env):
    await env.user(1)
    await env.say(1, "/start")
    assert '<tg-emoji emoji-id="' in env.last_text(1, raw=True)      # decision 39: 👋 becomes the TulporGo greeting emoji


async def test_start_has_mini_app_button_with_the_configured_url(env):
    await env.user(1)
    await env.say(1, "/start")
    apps = [b.web_app.url for b in env.all_buttons(1) if b.web_app]
    assert apps == [env.settings.miniapp_url]


async def test_unknown_language_code_is_ignored(env):
    await env.say(1, "/start")
    await env.press(1, "lang:klingon")                     # negative: tampered callback
    assert (await get_user(env, 1)).lang is None
    assert not any("Xuş kelibsiz" in t for t in env.texts(1))


async def test_til_changes_language(env):
    await env.user(1, lang="uz_new")
    await env.say(1, "/til")
    assert env.buttons(1) == [f"lang:{c}" for c in LANGS]
    await env.press(1, "lang:ru")
    assert (await get_user(env, 1)).lang == "ru"
    assert "Язык сохранён" in env.texts(1)[-1] or "Язык сохранён" in "".join(env.texts(1))
    await env.say(1, "/yordam")
    assert "Помощь" in env.last_text(1)


async def test_til_does_not_replay_the_greeting(env):
    await env.user(1)
    await env.say(1, "/til")
    await env.press(1, "lang:en")
    assert not any("Welcome!" in strip_tags(t) for t in env.texts(1))     # only the first start greets


async def test_commands_menu_per_scope(env):
    await env.user(1)
    await env.say(1, "/start")
    chat_calls = [c for c in env.methods("SetMyCommands") if getattr(c.scope, "chat_id", None) == 1]
    assert [c.command for c in chat_calls[-1].commands] == ["start", "qatnovlarim", "til", "yordam"]
    await env.driver(2)
    await env.say(2, "/start")
    drv_calls = [c for c in env.methods("SetMyCommands") if getattr(c.scope, "chat_id", None) == 2]
    assert [c.command for c in drv_calls[-1].commands] == ["start", "qatnovlarim", "til", "yordam", "elon", "obuna"]


async def test_default_menu_has_no_driver_commands(env):
    defaults = [c for c in env.methods("SetMyCommands") if type(c.scope).__name__ == "BotCommandScopeDefault"]
    assert defaults and all("elon" not in [x.command for x in c.commands] for c in defaults)
    assert {c.language_code for c in defaults} == {None, "ru", "en"}


# ---------- deep links ----------

async def test_ref_link_is_remembered_before_language_is_chosen(env):
    await env.driver(10)
    code = (await get_user(env, 10)).referral_code
    await env.say(20, f"/start ref_{code}")
    inviter = await get_user(env, 10)
    assert (await get_user(env, 20)).referred_by_id == inviter.id
    await env.press(20, "lang:uz_new")
    assert "+7" in env.last_text(20)                        # the greeting carries the bonus rule (decision 52)


async def test_ref_link_of_an_existing_driver_is_ignored(env):
    await env.driver(10)
    await env.driver(11, plate="30A222BC")
    code = (await get_user(env, 10)).referral_code
    await env.say(11, f"/start ref_{code}")
    assert (await get_user(env, 11)).referred_by_id is None


async def test_own_and_unknown_ref_links_are_ignored(env):
    await env.driver(10)
    code = (await get_user(env, 10)).referral_code
    await env.user(30)
    await env.say(30, "/start ref_ZZZZZZ")
    assert (await get_user(env, 30)).referred_by_id is None
    await env.user(10)
    await env.say(10, f"/start ref_{code}")                 # self-invite
    assert (await get_user(env, 10)).referred_by_id is None


async def test_deep_link_driver_starts_registration(env):
    await env.user(1)
    await env.say(1, "/start driver")
    assert any("telefon" in t.lower() for t in env.texts(1))
    assert env.sent(1)[-1].reply_markup.keyboard[0][0].request_contact is True


async def test_deep_link_driver_for_existing_driver_shows_panel(env):
    await env.driver(1)
    await env.say(1, "/start driver")
    assert "Haydovçi paneli" in env.last_text(1) or "paneli" in env.last_text(1)


async def test_deep_link_faq_and_command_hints(env):
    await env.user(1)
    await env.say(1, "/start faq")
    assert "Yordam" in env.last_text(1)
    await env.say(1, "/start elon")
    assert "/elon" in env.last_text(1)
    await env.say(1, "/start obuna")
    assert "/obuna" in env.last_text(1)


async def test_deep_link_after_language_pick_is_not_lost(env):
    await env.say(1, "/start faq")
    await env.press(1, "lang:en")
    assert "Help" in env.last_text(1)


async def test_unknown_deep_link_gives_the_plain_greeting(env):
    await env.user(1, lang="en")
    await env.say(1, "/start whatever_123")
    assert strip_tags(env.last_text(1)) == APPROVED["bot.start"]["text"]["en"]


async def test_start_in_a_group_is_ignored(env):
    await env.say(1, "/start", chat="supergroup")
    assert env.sent(1) == [] and not [c for c in env.fake.calls if type(c).__name__ == "SendMessage"]


async def test_blocked_user_gets_no_answer(env):
    await env.user(1, blocked=True)
    n = len(env.fake.calls)
    await env.say(1, "/start")
    assert len(env.fake.calls) == n


async def test_shared_trip_link_shows_status_without_phone_numbers(env):
    from sqlalchemy import select
    from tulporgo_core.models import Driver
    await env.user(5, phone="+998900000000")
    await env.driver(6, username="drv")

    async def flow(s):
        p = await s.scalar(select(User).where(User.tg_id == 5))
        d = await s.scalar(select(Driver))
        r = await rides_service.create_request(s, p, env.settings, from_text="A", to_text="B", seats=1)
        o = await rides_service.send_offer(s, d, r, env.settings, 30000)
        return (await rides_service.accept_offer(s, p, o)).share_token
    token = await env.db(flow)
    await env.user(9)                                       # a relative who got the link
    await env.say(9, f"/start trip_{token}")
    text = env.last_text(9)
    assert "A → B" in text and "Cobalt" in text and "30A123BC" in text
    assert "+998" not in text and "@drv" not in text         # route, car, status — never contact details
    await env.say(9, "/start trip_nonexistent")
    assert env.last_text(9) == i18n.t("bot.err.trip_not_found", "uz_new")     # negative: a wrong token reveals nothing


def test_referral_helper_still_parses_codes():
    assert referral.code_from_start("ref_ABC123") == "ABC123" and referral.code_from_start("driver") is None
