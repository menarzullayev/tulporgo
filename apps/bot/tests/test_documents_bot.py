"""Driver documents kept encrypted on our server too (decision 57): bot upload path and admin retrieval."""
from datetime import timedelta

from bot_harness import Env, tx
from cryptography.fernet import Fernet
from sqlalchemy import select
from tulporgo_bot import jobs
from tulporgo_core.db import utcnow
from tulporgo_core.models import Driver, DriverDocument, User
from tulporgo_core.services import documents

LICENCE = b"\xff\xd8\xff\xe0" + b"BOT-LICENCE" * 8
TECHPASS = b"\xff\xd8\xff\xe0" + b"BOT-TECHPASS" * 8
KEY = Fernet.generate_key().decode()


async def start(tmp_path, **kw):
    env = await Env(tmp_path, admin_ids=[50], **kw).start()
    await env.seed_places()
    await env.user(50, name="Admin", admin=True)
    await env.driver(20, plate="30A222BC")
    return env


async def driver_row(env) -> Driver:
    return await env.db(lambda s: s.scalar(select(Driver).join(User, User.id == Driver.user_id).where(User.tg_id == 20)))


async def server_rows(env):
    return await env.db(lambda s: _rows(s))


async def _rows(s):
    return list((await s.execute(select(DriverDocument).order_by(DriverDocument.kind))).scalars())


async def send_both(env, lic="lic-1", tp="tp-1"):
    await env.press(20, "drv:doc")
    await env.photo(20, lic)
    await env.photo(20, tp)


async def test_bot_upload_stores_the_downloaded_bytes_encrypted_and_keeps_file_ids(tmp_path):
    env = await start(tmp_path, documents_encryption_key=KEY)
    try:
        env.fake.files.update({"lic-1": LICENCE, "tp-1": TECHPASS})
        await send_both(env)
        d = await driver_row(env)
        assert (d.license_file_id, d.techpass_file_id) == ("lic-1", "tp-1")             # Telegram copy as today
        rows = await server_rows(env)
        assert [r.kind for r in rows] == ["license", "techpass"]
        assert all(r.data_encrypted not in (LICENCE, TECHPASS) for r in rows)
        f = Fernet(KEY.encode())
        assert [f.decrypt(r.data_encrypted) for r in rows] == [LICENCE, TECHPASS]
        assert env.said(20, tx("bot.docs.sent"))
    finally:
        await env.stop()


async def test_download_failure_asks_to_resend_and_leaves_no_half_state(tmp_path):
    env = await start(tmp_path, documents_encryption_key=KEY)
    try:
        env.fake.files["lic-1"] = LICENCE                                              # tp-1 cannot be fetched
        await send_both(env)
        assert env.said(20, tx("bot.docs.download_failed"))
        d = await driver_row(env)
        assert (d.license_file_id, d.techpass_file_id) == (None, None)
        assert await server_rows(env) == []
        assert not env.said(20, tx("bot.docs.sent")) and "ad:docs" not in env.buttons(50)   # admin not notified
        env.fake.files["tp-2"] = TECHPASS                                              # resend → still on that step
        await env.photo(20, "tp-2")
        d = await driver_row(env)
        assert (d.license_file_id, d.techpass_file_id) == ("lic-1", "tp-2")
        assert len(await server_rows(env)) == 2
    finally:
        await env.stop()


async def test_licence_download_failure_restarts_from_the_licence_step(tmp_path):
    env = await start(tmp_path, documents_encryption_key=KEY)
    try:
        env.fake.files["tp-1"] = TECHPASS                                              # lic-1 cannot be fetched
        await send_both(env)
        assert env.said(20, tx("bot.docs.download_failed")) and env.said(20, tx("bot.docs.license"))
        assert await server_rows(env) == [] and (await driver_row(env)).license_file_id is None
    finally:
        await env.stop()


async def test_unusable_bytes_are_refused_without_a_half_stored_licence(tmp_path):
    env = await start(tmp_path, documents_encryption_key=KEY)
    try:
        env.fake.files.update({"lic-1": LICENCE, "tp-1": b"MZ-not-an-image"})
        await send_both(env)
        assert env.said(20, tx("bot.docs.download_failed"))
        assert await server_rows(env) == []                                            # the licence was rolled back too
        assert (await driver_row(env)).techpass_file_id is None
    finally:
        await env.stop()


async def test_without_a_key_nothing_is_downloaded_or_stored(tmp_path):
    env = await start(tmp_path)                                                         # no key: development
    try:
        await send_both(env)                                                           # files not even servable
        d = await driver_row(env)
        assert (d.license_file_id, d.techpass_file_id) == ("lic-1", "tp-1")
        assert await server_rows(env) == [] and env.methods("GetFile") == []
    finally:
        await env.stop()


async def test_admin_gets_the_server_copy_as_documents_and_only_the_admin(tmp_path):
    env = await start(tmp_path, documents_encryption_key=KEY)
    try:
        env.fake.files.update({"lic-1": LICENCE, "tp-1": TECHPASS})
        await send_both(env)
        d = await driver_row(env)
        await env.press(50, "ad:docs")
        assert f"ad:dl:{d.id}" in [b.callback_data for b in env.all_buttons(50)]
        env.fake.calls.clear()
        await env.press(50, f"ad:dl:{d.id}")
        sent = env.methods("SendDocument")
        assert [m.chat_id for m in sent] == [50, 50]
        assert [m.document.data for m in sent] == [LICENCE, TECHPASS]
        assert all(m.protect_content for m in sent)
    finally:
        await env.stop()


async def test_non_admin_cannot_fetch_the_server_copy(tmp_path):
    env = await start(tmp_path, documents_encryption_key=KEY)
    try:
        env.fake.files.update({"lic-1": LICENCE, "tp-1": TECHPASS})
        await send_both(env)
        d = await driver_row(env)
        await env.user(1)
        await env.press(1, f"ad:dl:{d.id}")                                            # a passenger
        await env.press(20, f"ad:dl:{d.id}")                                           # the document's own owner
        assert env.alerts()[-2:] == [tx("bot.err.admin_only")] * 2
        assert env.methods("SendDocument") == []
    finally:
        await env.stop()


async def test_admin_reject_keeps_the_server_copy_seven_days_then_the_job_purges_it(tmp_path):
    """Decision 63: a rejected copy stays 7 days (a dispute, a second look), then the hourly job removes it."""
    env = await start(tmp_path, documents_encryption_key=KEY)
    try:
        env.fake.files.update({"lic-1": LICENCE, "tp-1": TECHPASS})
        await send_both(env)
        d = await driver_row(env)
        before = utcnow()
        await env.press(50, f"ad:dr:{d.id}")
        rows = await server_rows(env)
        assert [r.kind for r in rows] == ["license", "techpass"]                 # not deleted at once
        for r in rows:
            assert before + timedelta(days=7) <= r.delete_after <= utcnow() + timedelta(days=7)
        # negative: the job leaves it alone while the 7 days run
        assert await jobs.purge_documents_once(env.maker, now=utcnow() + timedelta(days=6, hours=23)) == 0
        assert len(await server_rows(env)) == 2
        assert await jobs.purge_documents_once(env.maker, now=utcnow() + timedelta(days=7, minutes=1)) == 2
        assert await server_rows(env) == []
        assert env.settings.documents_encryption_key == KEY and documents.enabled(env.settings)
    finally:
        await env.stop()


async def test_a_new_upload_after_a_rejection_is_not_purged(tmp_path):
    env = await start(tmp_path, documents_encryption_key=KEY)
    try:
        env.fake.files.update({"lic-1": LICENCE, "tp-1": TECHPASS, "lic-2": LICENCE, "tp-2": TECHPASS})
        await send_both(env)
        d = await driver_row(env)
        await env.press(50, f"ad:dr:{d.id}")
        await send_both(env, "lic-2", "tp-2")                                      # clearer photos, under review
        assert all(r.delete_after is None for r in await server_rows(env))
        assert await jobs.purge_documents_once(env.maker, now=utcnow() + timedelta(days=30)) == 0
        assert len(await server_rows(env)) == 2
    finally:
        await env.stop()
