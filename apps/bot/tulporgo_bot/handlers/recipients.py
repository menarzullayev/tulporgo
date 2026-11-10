"""Who gets admin notifications (new documents, new complaints): admins in the database, `settings.admin_ids`
and the owner chat. Deduplicated, never the blocked. Each target comes with an i18n function in their language."""
from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tulporgo_core.config import Settings
from tulporgo_core.i18n import lang_of
from tulporgo_core.models import User

from .common import bind


async def admin_targets(session: AsyncSession, settings: Settings) -> list[tuple[int, Callable[..., str]]]:
    ids = list(settings.admin_ids)
    if settings.owner_chat_id:
        ids.append(settings.owner_chat_id)
    ids += list((await session.execute(select(User.tg_id).where(User.is_admin.is_(True),
                                                                 User.is_blocked.is_(False)))).scalars())
    ids = list(dict.fromkeys(ids))
    langs = dict((await session.execute(select(User.tg_id, User.lang).where(User.tg_id.in_(ids)))).all()) if ids else {}
    return [(i, bind(lang_of(langs.get(i)))) for i in ids]
