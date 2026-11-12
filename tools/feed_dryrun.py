"""Dry run of group reading (decision 73) with real Telegram accounts, before the deploy.

Local SQLite in .dryrun/ (git-ignored), sessions encrypted with a key that also lives only there. The accounts only
READ: they get no post template, so the scheduler never writes to a group. Cards come from @tulporgobot through
sendMessage, which does not compete with the coming-soon bot's getUpdates. Message texts are never printed or stored.

Run from the repository root, each step in your own terminal (codes and the 2FA password are typed there, never in a
chat and never shown to anyone):

    uv run python tools/feed_dryrun.py init
    uv run python tools/feed_dryrun.py login driver1      # phone, code, 2FA if set
    uv run python tools/feed_dryrun.py groups driver1     # pick the taxi groups by number
    uv run python tools/feed_dryrun.py run --minutes 30   # cards arrive in the bot chat; latency + memory printed
    uv run python tools/feed_dryrun.py cleanup --yes      # log the sessions out on Telegram, delete .dryrun/
"""
import argparse
import asyncio
import ctypes
import getpass
import logging
import os
import shutil
import sys
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / ".dryrun"
DB = DIR / "feed.db"
KEY = DIR / "fernet.key"
PLACEHOLDER_PHONE = "+998977777777"       # the real number is not needed and is not stored


def _load_env() -> None:
    for name in ("telegram_app.env", "bot.env"):
        f = ROOT / ".secrets" / name
        if f.exists():
            for line in f.read_text(encoding="utf-8").splitlines():
                k, sep, v = line.partition("=")
                if sep and not k.strip().startswith("#"):
                    os.environ.setdefault(k.strip(), v.strip())
    for sub in ("packages/core", "packages/payments", "apps/bot", "apps/userbot", "apps/api"):
        sys.path.insert(0, str(ROOT / sub))


_load_env()

from sqlalchemy import select  # noqa: E402
from tulporgo_core.config import Settings  # noqa: E402
from tulporgo_core.db import make_engine, make_sessionmaker, session_scope, utcnow  # noqa: E402
from tulporgo_core.enums import UserbotStatus  # noqa: E402
from tulporgo_core.models import DriverFilter, User, UserbotAccount, UserbotGroup  # noqa: E402
from tulporgo_core.services import drivers, users  # noqa: E402

URL = f"sqlite+aiosqlite:///{DB.as_posix()}"


def settings() -> Settings:
    return Settings.model_validate({
        "database_url": URL, "bot_token": os.environ.get("TULPORGO_BOT_TOKEN", ""),
        "userbot_encryption_key": KEY.read_text().strip() if KEY.exists() else "",
        "free_period_until": date.today() + timedelta(days=30)})      # everyone Business -> cards at once


def rss_mb() -> float:
    """Working set of this process (Windows), MB."""
    class PMC(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong), ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t)]
    pmc = PMC()
    pmc.cb = ctypes.sizeof(PMC)
    k32 = ctypes.windll.kernel32
    k32.GetCurrentProcess.restype = ctypes.c_void_p          # a 64-bit pseudo-handle; the default int truncates it
    k32.K32GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(PMC), ctypes.c_ulong]
    if not k32.K32GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb):
        raise ctypes.WinError()
    return pmc.WorkingSetSize / 1e6


# ---------------------------------------------------------------- steps

def cmd_init(_a) -> None:
    from cryptography.fernet import Fernet
    from tulporgo_core.manage import migrate, seed_places
    DIR.mkdir(exist_ok=True)
    if not KEY.exists():
        KEY.write_text(Fernet.generate_key().decode())
    migrate(URL)
    n = asyncio.run(seed_places(URL))
    print(f"init: database ready, {n} places")


async def _login(name: str) -> None:
    from telethon.errors import SessionPasswordNeededError
    from tulporgo_userbot.client import make_telethon_factory
    from tulporgo_userbot.crypto import encrypt_session
    st = settings()
    client = make_telethon_factory()(None)
    await client.connect()
    try:
        phone = uz_phone(await asyncio.to_thread(input, "Telefon raqami (90 123 45 67 yoki +998...): "))
        code_hash = await client.send_code(phone)
        code = (await asyncio.to_thread(input, "Telegram yuborgan kod: ")).strip()
        try:
            me_id = await client.sign_in_code(phone, code, code_hash)
        except SessionPasswordNeededError:
            me_id = await client.sign_in_password(getpass.getpass("2FA parol (ko'rinmaydi): "))
        session = client.session_string()
    finally:
        await client.disconnect()
    maker = make_sessionmaker(make_engine(URL))
    async with session_scope(maker) as s:
        user = await users.get_or_create_user(s, me_id, username=None, first_name=name)
        user.phone = user.phone or PLACEHOLDER_PHONE
        driver = await drivers.get_driver(s, user) or await drivers.register_driver(
            s, user, st, car_make="Test", car_color="oq", car_plate=f"01T{me_id % 1000:03d}DR")
        acc = (await s.execute(select(UserbotAccount).where(UserbotAccount.driver_id == driver.id))).scalar_one_or_none()
        if acc is None:
            acc = UserbotAccount(driver_id=driver.id)
            s.add(acc)
        acc.session_encrypted = encrypt_session(st, session)
        acc.tg_user_id, acc.status = me_id, UserbotStatus.CONNECTED
        acc.consent_at, acc.consent_version = utcnow(), 2
        await s.flush()
        if not (await s.execute(select(DriverFilter).where(DriverFilter.driver_id == driver.id))).first():
            s.add(DriverFilter(driver_id=driver.id, name="Hammasi (sinov)", routes=[]))   # every request, any route
    print(f"login: {name} ulandi (Telegram id {me_id}); kartochkalar shu hisobning @tulporgobot chatiga keladi")


def uz_phone(raw: str) -> str:
    """'90 123 45 67', '998901234567' and '+998901234567' all become +998901234567 (Telegram wants the country code)."""
    from tulporgo_userbot.service import normalize_phone
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) == 9:
        digits = "998" + digits
    return normalize_phone("+" + digits)


def cmd_login(a) -> None:
    from telethon import errors as tg
    from tulporgo_core.errors import Invalid
    try:
        asyncio.run(_login(a.name))
    except Invalid:
        sys.exit("Raqam noto'g'ri: 9 ta raqam (90 123 45 67) yoki +998 bilan to'liq kiriting.")
    except tg.PhoneNumberInvalidError:
        sys.exit("Telegram bu raqamni qabul qilmadi. Raqamni tekshirib, qayta urinib ko'ring.")
    except (tg.PhoneCodeInvalidError, tg.PhoneCodeExpiredError):
        sys.exit("Kod noto'g'ri yoki eskirgan. Buyruqni qayta ishga tushiring — yangi kod keladi.")
    except tg.PasswordHashInvalidError:
        sys.exit("2FA parol noto'g'ri. Buyruqni qayta ishga tushiring.")
    except tg.FloodWaitError as e:
        sys.exit(f"Telegram cheklov qo'ydi: {e.seconds} soniya kutish kerak. Hozir qayta urinmang.")


async def _account(s, name: str) -> UserbotAccount:
    user = (await s.execute(select(User).where(User.first_name == name))).scalar_one()
    driver = await drivers.get_driver(s, user)
    return (await s.execute(select(UserbotAccount).where(UserbotAccount.driver_id == driver.id))).scalar_one()


async def _groups(name: str) -> None:
    from tulporgo_userbot.client import make_telethon_factory
    from tulporgo_userbot.crypto import decrypt_session
    st = settings()
    maker = make_sessionmaker(make_engine(URL))
    async with session_scope(maker) as s:
        acc = await _account(s, name)
        session = decrypt_session(st, acc.session_encrypted)
    client = make_telethon_factory()(session)
    await client.connect()
    try:
        found = await client.list_groups()
    finally:
        await client.disconnect()
    for i, g in enumerate(found, 1):
        print(f"{i:3}. {g.title}")
    picked = await asyncio.to_thread(input, "Taksi guruhlari raqamlari (vergul bilan, masalan 1,4,7): ")
    nums = {int(x) for x in picked.replace(" ", "").split(",") if x.isdigit()}
    async with session_scope(maker) as s:
        acc = await _account(s, name)
        for row in (await s.execute(select(UserbotGroup).where(UserbotGroup.account_id == acc.id))).scalars():
            await s.delete(row)
        for i, g in enumerate(found, 1):
            if i in nums:
                s.add(UserbotGroup(account_id=acc.id, chat_id=g.chat_id, title=g.title, enabled=True))
    print(f"groups: {len(nums)} ta guruh tanlandi")


def cmd_groups(a) -> None:
    asyncio.run(_groups(a.name))


OWNER_CHAT = ROOT / ".secrets" / "owner_chat_id"


async def _preflight(bot, maker, to_owner: bool) -> bool:
    """Every driver's card target must be a chat the bot can write to. A Telegram bot cannot open a chat: the account
    has to press /start in @tulporgobot first ("chat not found" otherwise — the 2026-11-12 night run lost its card)."""
    from tulporgo_core.models import Driver
    owner = int(OWNER_CHAT.read_text().strip()) if to_owner else None
    ok = True
    async with session_scope(maker) as s:
        for d in (await s.execute(select(Driver))).scalars():
            if owner is not None:
                d.delivery_chat_id = owner                       # local dry-run copy only
            target = d.delivery_chat_id or d.user.tg_id
            try:
                await bot.get_chat(target)
                print(f"preflight: driver {d.id} -> chat ...{str(target)[-3:]} OK")
            except Exception as e:                               # noqa: BLE001
                ok = False
                print(f"preflight: driver {d.id} -> chat ...{str(target)[-3:]}: {getattr(e, 'message', e)}\n"
                      "  Bu hisobdan @tulporgobot ni ochib /start bosing, yoki `run --to-owner` bilan "
                      "kartochkalarni o'z chatingizga yuboring.")
    return ok


async def _run(minutes: float, to_owner: bool = False) -> None:
    from aiogram import Bot
    from aiogram.client.default import DefaultBotProperties
    from aiogram.enums import ParseMode
    from telethon import events
    from tulporgo_core.events import InMemoryBus
    from tulporgo_userbot.client import make_telethon_factory
    from tulporgo_userbot.notifier import BotNotifier
    from tulporgo_userbot.reader import BotCardSender, Reader
    from tulporgo_userbot.scheduler import Scheduler

    st = settings()
    maker = make_sessionmaker(make_engine(URL))
    bot = Bot(st.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    if not await _preflight(bot, maker, to_owner):
        await bot.session.close()
        sys.exit("run: kartochka yuboriladigan chat ochilmagan — yuqoridagi ko'rsatmaga qarang.")
    stats = {"messages": 0, "cards": 0, "latency": []}
    current: dict = {}
    # Passengers delete their post once they find a taxi (owner, 2026-11-11): how long does a request live?
    requests: dict[tuple[int, int], datetime] = {}     # (chat id, message id) of a detected request -> posted at
    lifetimes: list[float] = []                         # minutes
    hooked: set[int] = set()

    async def on_deleted(event) -> None:
        for mid in event.deleted_ids:
            # basic groups report no chat id; their message ids are unique per account
            key = next((k for k in requests if k[1] == mid and (event.chat_id is None or k[0] == event.chat_id)),
                       None)
            if key is not None:
                life = (datetime.now(UTC) - requests.pop(key)).total_seconds() / 60
                lifetimes.append(life)
                print(f"{time.strftime('%H:%M:%S')} so'rov o'chirildi: {life:.0f} daqiqa turdi")

    class Sender(BotCardSender):
        async def send(self, chat_id, text, buttons):
            mid = await super().send(chat_id, text, buttons)
            if mid and current.get("at"):
                lat = (datetime.now(UTC) - current["at"]).total_seconds()
                stats["cards"] += 1
                stats["latency"].append(lat)
                print(f"{time.strftime('%H:%M:%S')} card -> ...{str(chat_id)[-3:]}  {current.get('route')}  {lat:.1f}s")
            return mid

    class CountingReader(Reader):
        async def handle(self, account_id, msg):
            if msg.chat_id in self._assigned.get(account_id, set()):
                stats["messages"] += 1
                current["at"] = msg.sent_at
                from tulporgo_core.groupscan import detect
                idx = self._index
                det = detect(msg.text, idx) if idx else None
                current["route"] = (f"{det.kind}: {det.from_place.name if det.from_place else '?'} -> "
                                    f"{det.to_place.name if det.to_place else '?'}") if det else "-"
                if det is not None:
                    requests[(msg.chat_id, msg.message_id)] = msg.sent_at or datetime.now(UTC)
            await super().handle(account_id, msg)

    sch = Scheduler(maker, st, InMemoryBus(), make_telethon_factory(), BotNotifier(bot))
    reader = CountingReader(maker, st, sch.client_for, sch.live_client, Sender(bot))
    base = rss_mb()
    end = time.monotonic() + minutes * 60
    try:
        while time.monotonic() < end:
            assignment = await reader.refresh()
            for client in reader._hooked.values():
                raw = getattr(client, "_client", None)
                if raw is not None and id(raw) not in hooked:
                    raw.add_event_handler(on_deleted, events.MessageDeleted())
                    hooked.add(id(raw))
            await sch.tick()                                   # posts nothing: no account has a post template
            print(f"{time.strftime('%H:%M:%S')} readers={len(set(assignment.values()))} groups={len(assignment)} "
                  f"messages={stats['messages']} cards={stats['cards']} "
                  f"requests={len(requests) + len(lifetimes)} deleted={len(lifetimes)} "
                  f"memory={rss_mb():.0f}MB (start {base:.0f}MB)")
            await asyncio.sleep(60)
    finally:
        await reader.close()
        await sch.close()
        await bot.session.close()
    lat = sorted(stats["latency"])
    if lat:
        print(f"result: {stats['cards']} cards, latency median {lat[len(lat) // 2]:.1f}s, max {lat[-1]:.1f}s")
    print(f"result: {stats['messages']} messages read, memory {rss_mb():.0f}MB (start {base:.0f}MB)")
    life = sorted(lifetimes)
    total = len(requests) + len(life)
    if life:
        print(f"result: {len(life)}/{total} requests deleted by the passenger, lifetime median {life[len(life) // 2]:.0f}"
              f" min, shortest {life[0]:.0f} min")
    else:
        print(f"result: {total} requests, none deleted during the run")


def cmd_run(a) -> None:
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(_run(a.minutes, a.to_owner))


async def _cleanup() -> None:
    from tulporgo_userbot.client import make_telethon_factory
    from tulporgo_userbot.crypto import decrypt_session
    st = settings()
    maker = make_sessionmaker(make_engine(URL))
    async with session_scope(maker) as s:
        sessions = [decrypt_session(st, a.session_encrypted)
                    for a in (await s.execute(select(UserbotAccount))).scalars() if a.session_encrypted]
    for sess in sessions:
        client = make_telethon_factory()(sess)
        await client.connect()
        try:
            await client.log_out()                           # ends the "TulporGo (driver)" session on Telegram
        finally:
            await client.disconnect()
    print(f"cleanup: {len(sessions)} session(s) logged out")


def cmd_cleanup(a) -> None:
    if not a.yes:
        sys.exit("cleanup needs --yes (logs the test sessions out and deletes .dryrun/)")
    if DB.exists():
        asyncio.run(_cleanup())
    shutil.rmtree(DIR, ignore_errors=True)
    print("cleanup: .dryrun/ deleted")


def telethon_to_file() -> None:
    """Telethon logs routine reconnects ("Server closed the connection", "wrong session ID", "resent the older
    message") as warnings. They are kept in .dryrun/telethon.log (counted in the report) instead of the console."""
    DIR.mkdir(exist_ok=True)
    handler = logging.FileHandler(DIR / "telethon.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    log = logging.getLogger("telethon")
    log.addHandler(handler)
    log.propagate = False


def main() -> None:
    telethon_to_file()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init").set_defaults(fn=cmd_init)
    for name, fn in (("login", cmd_login), ("groups", cmd_groups)):
        sp = sub.add_parser(name)
        sp.add_argument("name")
        sp.set_defaults(fn=fn)
    sp = sub.add_parser("run")
    sp.add_argument("--minutes", type=float, default=30)
    sp.add_argument("--to-owner", action="store_true", help="send cards to the owner chat (.secrets/owner_chat_id)")
    sp.set_defaults(fn=cmd_run)
    sp = sub.add_parser("cleanup")
    sp.add_argument("--yes", action="store_true")
    sp.set_defaults(fn=cmd_cleanup)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
