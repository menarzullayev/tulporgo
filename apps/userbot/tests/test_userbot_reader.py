"""Group reader (decision 73): one reader per group, cards only to matching members, Biznes first, duplicates merged,
cards deleted after 2 h, the reader never writes to a group. Fake Telethon client, no network."""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select
from tulporgo_core.enums import Plan
from tulporgo_core.models import DriverFilter, FeedCard, Place
from tulporgo_userbot import cards
from tulporgo_userbot.client import GroupDeletion, GroupMessage
from tulporgo_userbot.reader import Reader
from tulporgo_userbot.scheduler import Scheduler
from userbot_fixtures import *  # noqa: F403
from userbot_helpers import make_account, make_driver

NOW = datetime(2026, 11, 10, 13, 0)         # 18:00 local
G1, G2, G3 = -1001, -1002, -1003
REQUEST = "Qoshrabotdan Samarqandga 2 kishi bor, kim ketadi?"


class FakeSender:
    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []
        self.edited: list[tuple[int, int, str]] = []
        self.edited_buttons: list[list] = []
        self.deleted: list[tuple[int, int]] = []

    async def send(self, chat_id, text, buttons):
        self.sent.append((chat_id, text))
        return len(self.sent)

    async def edit(self, chat_id, message_id, text, buttons):
        self.edited.append((chat_id, message_id, text))
        self.edited_buttons.append(buttons)

    async def delete(self, chat_id, message_id):
        self.deleted.append((chat_id, message_id))


class Clock:
    def __init__(self) -> None:
        self.now = NOW
        self.slept: list[float] = []

    def __call__(self):
        return self.now

    async def sleep(self, seconds):
        self.slept.append(seconds)


@pytest.fixture
async def places(s):
    qosh, sam = Place(kind="district", name_uz="Qo'shrabot", aliases=["qoshrabot"]), Place(kind="city", name_uz="Samarqand")
    s.add_all([qosh, sam])
    await s.commit()
    return qosh, sam


async def member(s, settings, places, *, groups=2, plan=None, **flt):
    d = await make_driver(s, settings, plan=plan)
    acc = await make_account(s, settings, d, groups=groups)
    acc.consent_version = 2
    f = DriverFilter(driver_id=d.id, name="kech", routes=[{"from": places[0].id, "to": places[1].id}], **flt)
    s.add(f)
    await s.commit()
    return d, acc


def build(maker, settings, bus, factory, notifier, clock, sender):
    sch = Scheduler(maker, settings, bus, factory, notifier, clock=clock)
    return Reader(maker, settings, sch.client_for, sch.live_client, sender, clock=clock, sleep=clock.sleep), sch


async def push(factory, chat, text=REQUEST, msg_id=10, sender_id=42):
    for c in factory.clients:
        await c.push(GroupMessage(chat, msg_id, sender_id, "yolovchi42", None, text))


async def push_delete(factory, chat, *ids):
    for c in factory.clients:
        await c.push_delete(GroupDeletion(chat, tuple(ids)))


async def test_cards_go_to_matching_members_only(s, maker, settings, bus, factory, notifier, places):
    d1, _ = await member(s, settings, places)
    d2, _ = await member(s, settings, places)
    d3, _ = await member(s, settings, places, groups=0)              # in no group
    clock, sender = Clock(), FakeSender()
    reader, _ = build(maker, settings, bus, factory, notifier, clock, sender)
    assignment = await reader.refresh()
    assert set(assignment) == {G1, G2}
    assert sum(bool(c.handlers) for c in factory.clients) == 1      # one account reads both groups
    await push(factory, G1)
    targets = {chat for chat, _ in sender.sent}
    assert targets == {d1.user.tg_id, d2.user.tg_id} and d3.user.tg_id not in targets
    assert "Qo'shrabot → Samarqand" in sender.sent[0][1] and "2 kişi" in sender.sent[0][1]
    assert factory.sent == []                                         # negative: the reader never writes to a group
    async with maker() as s2:
        assert len((await s2.execute(select(FeedCard))).scalars().all()) == 2


@pytest.mark.parametrize("text", ["Samarqandga ketamiz 2 joy bor", "Assalomu alaykum", "Toshkentga taksi kerak"])
async def test_no_card_for_driver_ads_chat_or_other_routes(s, maker, settings, bus, factory, notifier, places, text):
    await member(s, settings, places)
    clock, sender = Clock(), FakeSender()
    reader, _ = build(maker, settings, bus, factory, notifier, clock, sender)
    await reader.refresh()
    await push(factory, G1, text)
    assert sender.sent == []


async def test_unwanted_group_is_ignored(s, maker, settings, bus, factory, notifier, places):
    await member(s, settings, places, group_chat_ids=[G1])           # only x1 selected
    clock, sender = Clock(), FakeSender()
    reader, _ = build(maker, settings, bus, factory, notifier, clock, sender)
    assert set(await reader.refresh()) == {G1}
    await push(factory, G2)                                           # negative: x2 is not read for anyone
    assert sender.sent == []


async def test_duplicate_in_another_group_edits_the_card(s, maker, settings, bus, factory, notifier, places):
    await member(s, settings, places)
    clock, sender = Clock(), FakeSender()
    reader, _ = build(maker, settings, bus, factory, notifier, clock, sender)
    await reader.refresh()
    await push(factory, G1, msg_id=10)
    await push(factory, G2, msg_id=20)
    assert len(sender.sent) == 1 and len(sender.edited) == 1
    assert "Guruh 1, Guruh 2" in sender.edited[0][2]


async def test_biznes_first_others_after_60s(s, maker, paid_settings, bus, factory, notifier, places):
    biz, _ = await member(s, paid_settings, places, plan=Plan.BUSINESS)
    pro, _ = await member(s, paid_settings, places, plan=Plan.PRO)
    clock, sender = Clock(), FakeSender()
    reader, _ = build(maker, paid_settings, bus, factory, notifier, clock, sender)
    await reader.refresh()
    await push(factory, G1)
    assert [c for c, _ in sender.sent] == [biz.user.tg_id]           # Pro is still waiting
    for task in list(reader._tasks):
        await task
    assert [c for c, _ in sender.sent] == [biz.user.tg_id, pro.user.tg_id] and clock.slept == [60.0]


async def test_delivery_channel_and_cleanup_after_2h(s, maker, settings, bus, factory, notifier, places):
    d, _ = await member(s, settings, places)
    d.delivery_chat_id = -1009999
    await s.commit()
    clock, sender = Clock(), FakeSender()
    reader, _ = build(maker, settings, bus, factory, notifier, clock, sender)
    await reader.refresh()
    await push(factory, G1)
    assert sender.sent[0][0] == -1009999
    clock.now = NOW + timedelta(hours=1)
    assert await reader.purge() == 0                                  # negative: not yet
    clock.now = NOW + timedelta(hours=2, minutes=1)
    assert await reader.purge() == 1 and sender.deleted == [(-1009999, 1)]
    async with maker() as s2:
        assert (await s2.execute(select(FeedCard))).scalars().all() == []


def test_message_links():
    assert cards.message_link(-1001234567890, 5) == "https://t.me/c/1234567890/5"
    assert cards.message_link(-1001234567890, 5, "samtaksi") == "https://t.me/samtaksi/5"
    assert cards.message_link(-4567, 5) is None                       # negative: basic groups have no links


def test_card_escapes_user_text():
    from tulporgo_core.enums import RequestKind
    from tulporgo_core.groupscan import Detection
    from tulporgo_core.places import PlaceRef
    det = Detection(RequestKind.PASSENGER, True, PlaceRef(1, "A<b>", "city"), None, None, 2, 0.9)
    text, rows = cards.render(det, [cards.CardGroup(-1001234567890, 7, "Guruh <x>")], "uz", NOW,
                              excerpt="<script>x</script>", author="a_b")
    assert "<script>" not in text and "&lt;script&gt;" in text and "A&lt;b&gt;" in text and "yuk bilan" in text
    assert rows[0][0]["url"] == "https://t.me/c/1234567890/7"


# ---------------------------------------------------------------- decision 75: passenger deleted the request

async def test_deleted_request_marks_cards_then_deletes_after_10_min(s, maker, settings, bus, factory, notifier,
                                                                     places):
    await member(s, settings, places)
    await member(s, settings, places)
    clock, sender = Clock(), FakeSender()
    reader, _ = build(maker, settings, bus, factory, notifier, clock, sender)
    await reader.refresh()
    await push(factory, G1, msg_id=10)
    assert len(sender.sent) == 2
    await push_delete(factory, G1, 99)                               # negative: another message
    assert sender.edited == []
    await push_delete(factory, G1, 10)
    assert len(sender.edited) == 2 and all(e[2].startswith("<s>") and "10" in e[2] for e in sender.edited)
    assert sender.edited_buttons == [[], []]                           # no "Taken" / group links left
    assert "«" not in sender.edited[0][2]                              # the excerpt is gone too
    clock.now = NOW + timedelta(minutes=9)
    assert await reader.purge() == 0                                   # negative: not yet
    clock.now = NOW + timedelta(minutes=11)
    assert await reader.purge() == 2


async def test_basic_group_deletion_has_no_chat_id(s, maker, settings, bus, factory, notifier, places):
    await member(s, settings, places)
    clock, sender = Clock(), FakeSender()
    reader, _ = build(maker, settings, bus, factory, notifier, clock, sender)
    await reader.refresh()
    await push(factory, G1, msg_id=10)
    await push_delete(factory, None, 11)                               # negative: a different id
    assert sender.edited == []
    await push_delete(factory, None, 10)
    assert len(sender.edited) == 1


async def test_supergroup_id_is_not_matched_without_chat_id(s, maker, settings, bus, factory, notifier, places):
    _, acc = await member(s, settings, places)
    acc.groups[0].chat_id = -1001234567890                              # a real supergroup id (-100…)
    await s.commit()
    clock, sender = Clock(), FakeSender()
    reader, _ = build(maker, settings, bus, factory, notifier, clock, sender)
    await reader.refresh()
    await push(factory, -1001234567890, msg_id=10)
    assert len(sender.sent) == 1
    await push_delete(factory, None, 10)                               # negative: a basic-group deletion, same id
    assert sender.edited == []
    await push_delete(factory, -1001234567890, 10)
    assert len(sender.edited) == 1


async def test_duplicate_is_gone_only_when_every_copy_is_deleted(s, maker, settings, bus, factory, notifier, places):
    await member(s, settings, places)
    clock, sender = Clock(), FakeSender()
    reader, _ = build(maker, settings, bus, factory, notifier, clock, sender)
    await reader.refresh()
    await push(factory, G1, msg_id=10)
    await push(factory, G2, msg_id=20)
    assert len(sender.edited) == 1                                      # the second group link
    await push_delete(factory, G1, 10)
    assert len(sender.edited) == 1                                      # negative: still posted in G2
    await push_delete(factory, G2, 20)
    assert len(sender.edited) == 2 and sender.edited[-1][2].startswith("<s>")


async def test_delayed_card_is_not_sent_after_deletion(s, maker, paid_settings, bus, factory, notifier, places):
    biz, _ = await member(s, paid_settings, places, plan=Plan.BUSINESS)
    pro, _ = await member(s, paid_settings, places, plan=Plan.PRO)
    clock, sender = Clock(), FakeSender()
    reader, _ = build(maker, paid_settings, bus, factory, notifier, clock, sender)
    await reader.refresh()
    await push(factory, G1)
    await push_delete(factory, G1, 10)                                  # within Pro's 60 s
    for task in list(reader._tasks):
        await task
    assert [c for c, _ in sender.sent] == [biz.user.tg_id]             # Pro never gets the dead request
    assert [e[0] for e in sender.edited] == [biz.user.tg_id]


async def test_request_posted_again_after_deletion_gets_a_fresh_card(s, maker, settings, bus, factory, notifier,
                                                                      places):
    await member(s, settings, places)
    clock, sender = Clock(), FakeSender()
    reader, _ = build(maker, settings, bus, factory, notifier, clock, sender)
    await reader.refresh()
    await push(factory, G1, msg_id=10)
    await push_delete(factory, G1, 10)
    clock.now = NOW + timedelta(minutes=5)
    await push(factory, G1, msg_id=11)                                  # same text, posted again
    assert len(sender.sent) == 2 and not sender.sent[1][1].startswith("<s>")
    await push_delete(factory, G1, 11)
    assert len(sender.edited) == 2                                      # the fresh card is marked as well


def test_gone_card_escapes_and_has_no_buttons():
    from tulporgo_core.enums import RequestKind
    from tulporgo_core.groupscan import Detection
    from tulporgo_core.places import PlaceRef
    det = Detection(RequestKind.PASSENGER, False, PlaceRef(1, "A<b>", "city"), None, None, 1, 0.9)
    text, rows = cards.render_gone(det, "ru")
    assert rows == [] and text.startswith("<s>") and "A&lt;b&gt;" in text and "10 минут" in text
