"""TulporGo admin tasks that no MCP tool can do, through a DEDICATED Telethon session of @menarzullayev.

Separate auth key (its own QR login, device "TulporGo admin (Claude)"), so it never shares a key with the running
MCP servers (no AUTH_KEY_DUPLICATED) and never touches WorkBuddy's ~/.mcp-telegram/session. Session string lives in
~/.mcp-telegram/claude-tulporgo-admin/.env and is never printed. Any FloodWait stops the run (exit 3).

  login        one-time QR login (the owner scans; a 2FA password, if any, is typed by the owner)
  bot-rights   @tulporgobot admin rights incl. manage_welcome_messages (no add-admins / change-info)
  welcome      Welcome Messages (approved texts, decision 40; channel with the approved image, decision 41)
  community    Community "TulporGo": channel + Q&A visible, drivers hidden, bot; only admins may add chats
  usernames    public links: channel @tulporgo, Q&A @tulporgo_chat   (this is the public launch)
  status       read everything back
Every step is idempotent: what is already in place is skipped.
Run with the chigwell venv (Telethon 1.45, layer 229):
  C:/Users/nsn/tools/telegram-mcp-chigwell/.venv/Scripts/python.exe tg_admin.py <step>
"""
import asyncio, json, os, sys
from pathlib import Path

from telethon import TelegramClient, errors, functions, types
from telethon.extensions import html as tghtml
from telethon.sessions import StringSession

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
I18N = ROOT / "content" / "i18n"
CHATS = HERE / "chats.json"
ADMIN_DIR = Path.home() / ".mcp-telegram" / "claude-tulporgo-admin"
ENV = ADMIN_DIR / ".env"
SRC_ENV = Path.home() / ".mcp-telegram" / "claude-chigwell-menarzullayev" / ".env"
OWNER_ID, BOT = 1808327630, "tulporgobot"
USERNAMES = {"channel": "tulporgo", "chat": "tulporgo_chat"}
DEVICE = {"device_model": "TulporGo admin (Claude)", "system_version": "Windows 11", "app_version": "tg_admin 1.0"}
RIGHTS = {
    "channel": dict(post_messages=True, edit_messages=True, delete_messages=True, invite_users=True, other=True,
                    manage_welcome_messages=True),
    "group": dict(delete_messages=True, ban_users=True, invite_users=True, pin_messages=True, other=True,
                  manage_topics=True, manage_welcome_messages=True),
}


# ---------- env / texts (no secrets printed) ----------
def read_env(p):
    if not p.exists():
        return {}
    return dict(l.split("=", 1) for l in p.read_text(encoding="utf-8").splitlines() if "=" in l and not l.startswith("#"))


def write_env(p, env):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text("".join(f"{k}={v}\n" for k, v in env.items()), encoding="utf-8")
    os.replace(tmp, p)


def welcome_payloads(texts, emoji):
    """{chat key: (message, entities, photo path or None)} from the approved texts; custom emoji per decision 39."""
    def deco(h):
        for std in sorted(emoji, key=len, reverse=True):
            for form in {std, std.replace("\ufe0f", ""), std + "\ufe0f"}:
                if form and not form.isascii() and form in h:
                    h = h.replace(form, f'<tg-emoji emoji-id="{emoji[std]}">{std}</tg-emoji>')
        return h

    def esc(s):
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def block(key):
        t = texts[key]["text"]
        return f"{esc(t['uz_new'])}\n\n<blockquote expandable>{esc(t['ru'])}</blockquote>"

    out = {"channel": (block("channel.welcome"), HERE / "out" / "welcome-channel.png"),
           "chat": (block("chat.welcome") + "\n\n" + block("chat.rules"), None),
           "drivers": (block("drivers.welcome"), None)}
    res = {}
    for k, (h, photo) in out.items():
        msg, ents = tghtml.parse(deco(h))
        res[k] = (msg, ents, photo)
    return res


def stop_on_flood(e):
    print(f"FloodWait: Telegram {e.seconds} s kutishni so'radi. To'xtatildi (akkauntga zarar yetmasin).")
    sys.exit(3)


# ---------- client ----------
async def client(login=False):
    env = read_env(ENV)
    if not env:
        src = read_env(SRC_ENV)
        env = {"TELEGRAM_API_ID": src["TELEGRAM_API_ID"], "TELEGRAM_API_HASH": src["TELEGRAM_API_HASH"]}
        write_env(ENV, env)
    c = TelegramClient(StringSession(env.get("TELEGRAM_SESSION_STRING") or None), int(env["TELEGRAM_API_ID"]),
                       env["TELEGRAM_API_HASH"], **DEVICE)
    await c.connect()
    if not await c.is_user_authorized():
        if not login:
            sys.exit("Admin sessiya yo'q: avval `tg_admin.py login` (QR).")
        return c, env
    me = await c.get_me()
    if me.id != OWNER_ID:
        sys.exit(f"Kutilmagan hisob id {me.id}")
    return c, env


async def do_login():
    sys.path.insert(0, str(Path.home() / ".mcp-telegram" / "claude-chigwell"))
    from tg_login import show_qr, seconds_left, sign_in_with_password, write_page  # owner-facing QR helpers
    c, env = await client(login=True)
    if await c.is_user_authorized():
        print("Admin sessiya allaqachon ulangan.")
        return
    qr = await c.qr_login()
    for attempt in range(12):
        show_qr(qr, ADMIN_DIR, "menarzullayev (TulporGo admin)", first=attempt == 0)
        try:
            await qr.wait(timeout=seconds_left(qr))
            break
        except asyncio.TimeoutError:
            await qr.recreate()
        except errors.SessionPasswordNeededError:
            await sign_in_with_password(c)
            break
    else:
        sys.exit("QR 12 marta eskirdi.")
    me = await c.get_me()
    if me.id != OWNER_ID:
        await c.log_out()
        sys.exit(f"Boshqa hisob skanerlandi (id {me.id}); sessiya yopildi.")
    env["TELEGRAM_SESSION_STRING"] = c.session.save()
    write_env(ENV, env)
    write_page(ADMIN_DIR, "TulporGo admin", "Ulandi", "<p>Sessiya saqlandi. Oynani yopishingiz mumkin.</p>", False)
    print(f"Tayyor: id {me.id} admin sessiyasi saqlandi.")


def chats():
    return json.load(open(CHATS, encoding="utf-8"))


def save_chats(d):
    json.dump(d, open(CHATS, "w", encoding="utf-8"), indent=1, ensure_ascii=False)


async def entity(c, key):
    return await c.get_input_entity(chats()[key]["bot_api_id"])


async def bot_rights(c):
    bot = await c.get_input_entity(BOT)
    for key in ("channel", "chat", "drivers"):
        r = types.ChatAdminRights(**RIGHTS["channel" if key == "channel" else "group"])
        await c(functions.channels.EditAdminRequest(await entity(c, key), bot, r, rank=""))
        print("bot rights:", key)
        await asyncio.sleep(3)


async def welcome(c, replace=False):
    texts = json.load(open(I18N / "build" / "telegram_texts.json", encoding="utf-8"))
    emoji = json.load(open(I18N / "build" / "emoji_map.json", encoding="utf-8"))
    for key, (msg, ents, photo) in welcome_payloads(texts, emoji).items():
        peer = await entity(c, key)
        have = await c(functions.ephemeral.GetWelcomeMessagesRequest(peer, hash=0))
        n = len(getattr(have, "messages", []) or [])
        if n and not replace:
            print("welcome:", key, f"already has {n}, skipped")
            continue
        if n:
            await c(functions.ephemeral.DeleteAllWelcomeMessagesRequest(peer))
        media = None
        if photo:
            media = types.InputMediaUploadedPhoto(await c.upload_file(str(photo)))
        await c(functions.ephemeral.SendMessageRequest(receiver_id=types.InputUserEmpty(), message=msg, welcome=True,
                                                       peer=peer, entities=ents, media=media))
        print("welcome:", key, "set")
        await asyncio.sleep(3)


def find_community(updates):
    for ch in getattr(updates, "chats", []) or []:
        if isinstance(ch, types.Community):
            return ch


async def community(c):
    d = chats()
    texts = json.load(open(I18N / "build" / "telegram_texts.json", encoding="utf-8"))
    about = texts["channel.description"]["text"]["uz_new"].split("\n")[0]
    if not d.get("community"):
        res = await c(functions.communities.CreateRequest(title="TulporGo", peer=await entity(c, "channel"), about=about))
        com = find_community(res)
        if not com:
            sys.exit(f"Community yaratildi, lekin javobda topilmadi: {type(res).__name__}")
        d["community"] = {"title": "TulporGo", "id": com.id, "access_hash": com.access_hash, "created": "2026-11-10"}
        save_chats(d)
        print("community: created", com.id)
        await asyncio.sleep(3)
    com = types.InputChannel(d["community"]["id"], d["community"]["access_hash"])
    links = d["community"].setdefault("links", {})
    for key, hidden in (("chat", False), ("drivers", True), ("bot", False)):
        if links.get(key):
            continue
        peer = await c.get_input_entity(BOT) if key == "bot" else await entity(c, key)
        try:
            await c(functions.communities.TogglePeerLinkRequest(com, peer, visible=None if hidden else True, hidden=True if hidden else None))
            links[key] = "hidden" if hidden else "visible"
            save_chats(d)
            print("community link:", key, links[key])
        except errors.FloodWaitError:
            raise
        except errors.RPCError as e:
            print("community link FAILED:", key, e)
        await asyncio.sleep(3)
    if not d["community"].get("admins_only_links"):
        await c(functions.messages.EditChatDefaultBannedRightsRequest(
            types.InputPeerChannel(d["community"]["id"], d["community"]["access_hash"]),
            types.ChatBannedRights(until_date=None, manage_linked_peers=True)))
        d["community"]["admins_only_links"] = True
        save_chats(d)
        print("community: only admins can add chats")


async def usernames(c):
    d = chats()
    for key, name in USERNAMES.items():
        if d[key].get("public_username") == name:
            print("username:", key, "already", name)
            continue
        peer = await entity(c, key)
        if not await c(functions.channels.CheckUsernameRequest(peer, name)):
            print("username:", name, "not available — stopped")
            return
        await c(functions.channels.UpdateUsernameRequest(peer, name))
        d[key]["public_username"] = name
        save_chats(d)
        print("username:", key, "->", "@" + name)
        await asyncio.sleep(3)


async def status(c):
    d = chats()
    for key in ("channel", "chat", "drivers"):
        full = await c(functions.channels.GetFullChannelRequest(await entity(c, key)))
        ch = full.chats[0]
        w = await c(functions.ephemeral.GetWelcomeMessagesRequest(await entity(c, key), hash=0))
        print(f"{key:8s} username={getattr(ch, 'username', None)} welcome={len(getattr(w, 'messages', []) or [])}")
    print("community:", d.get("community"))


async def main(step):
    if step == "login":
        return await do_login()
    c, _ = await client()
    try:
        await {"bot-rights": bot_rights, "welcome": welcome, "community": community, "usernames": usernames,
               "status": status}[step](c)
    except errors.FloodWaitError as e:
        stop_on_flood(e)
    finally:
        await c.disconnect()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
