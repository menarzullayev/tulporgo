"""Place picker (decision 47): district → mahalla/place with inline pagination over `places`, plus typed search.

Used by the order flow (roles f/t) and by driver registration (role h = home district). The caller registers a
chooser per role; the picker never needs to know what happens after a place is selected."""
from collections.abc import Awaitable, Callable

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from tulporgo_core import i18n
from tulporgo_core.enums import Lang, PlaceKind
from tulporgo_core.models import Place
from tulporgo_core.places import PlaceIndex
from tulporgo_core.text.alphabet import convert

from .common import PRIVATE, btn, int_arg, kb, parse_cb, show
from .states import Order, Reg

router = Router(name="picker")
router.message.filter(F.chat.type == PRIVATE)

PAGE = 8
ROLES = ("f", "t", "h")
# role → async chooser(event, state, place=Place|None, text=str, **ctx); registered by order.py / driver.py
CHOOSERS: dict[str, Callable[..., Awaitable[None]]] = {}


def register_chooser(role: str, fn: Callable[..., Awaitable[None]]) -> None:
    CHOOSERS[role] = fn


def label(name_uz: str, name_ru: str | None, lang) -> str:
    lg = i18n.lang_of(lang)
    if lg == Lang.RU and name_ru:
        return name_ru
    if lg in (Lang.UZ_NEW, Lang.UZ_LATN, Lang.UZ_CYRL):
        return convert(name_uz, lg.value)
    return name_uz


def place_label(p: Place, lang) -> str:
    return label(p.name_uz, p.name_ru, lang)


async def place_page(session: AsyncSession, parent_id: int, page: int) -> tuple[list[Place], bool]:
    q = select(Place)
    if parent_id == 0:
        q = q.where(Place.kind.in_([PlaceKind.DISTRICT, PlaceKind.CITY]))
    else:
        q = q.where(Place.parent_id == parent_id)
    rows = list((await session.execute(q.order_by(Place.popularity.desc(), Place.name_uz)
                                       .offset(page * PAGE).limit(PAGE + 1))).scalars())
    return rows[:PAGE], len(rows) > PAGE


async def has_children(session: AsyncSession, place_id: int) -> bool:
    return bool(await session.scalar(select(func.count(Place.id)).where(Place.parent_id == place_id)))


def keyboard(role: str, parent: int, page: int, rows: list[Place], has_next: bool, lang, t, parent_place: Place | None):
    out = []
    if parent_place is not None:                                   # "the whole district" is a valid choice too
        out.append([btn(f"📍 {place_label(parent_place, lang)} ({t('bot.place.whole')})", f"pk:{role}:{parent_place.id}",
                        style="primary")])
    for p in rows:
        action = "pd" if parent == 0 else "pk"
        out.append([btn(place_label(p, lang), f"{action}:{role}:{p.id}")])
    nav = []
    if page > 0:
        nav.append(btn("◀", f"pg:{role}:{parent}:{page - 1}"))
    if parent != 0:
        nav.append(btn(f"↩ {t('common.back')}", f"pg:{role}:0:0"))
    if has_next:
        nav.append(btn("▶", f"pg:{role}:{parent}:{page + 1}"))
    out.append(nav)
    if role == "h":
        out.append([btn(t("bot.btn.skip"), "ph:skip")])
    return kb(*out)


async def ask_place(event, state: FSMContext, session: AsyncSession, t, lang, role: str, parent: int = 0,
                    page: int = 0) -> None:
    await state.set_state(Reg.home if role == "h" else Order.place)
    await state.update_data(role=role)
    rows, has_next = await place_page(session, parent, page)
    parent_place = await session.get(Place, parent) if parent else None
    head = t(f"bot.place.ask_{role}")
    if parent_place is not None:
        head += f"\n<b>{place_label(parent_place, lang)}</b>"
    await show(event, head + "\n" + t("bot.place.type_hint"), keyboard(role, parent, page, rows, has_next, lang, t, parent_place))


async def _choose(event, state: FSMContext, role: str, place: Place | None, text: str, ctx: dict) -> None:
    chooser = CHOOSERS.get(role)
    if chooser is None:
        return
    await chooser(event, state, place=place, text=text, **ctx)


def _parsed(cb: CallbackQuery, n: int):
    parts = parse_cb(cb.data, n)
    if not parts or parts[1] not in ROLES:
        return None
    return parts


@router.callback_query(F.data.startswith("pg:"))
async def page(cb: CallbackQuery, state: FSMContext, session: AsyncSession, t, lang) -> None:
    parts = _parsed(cb, 4)
    parent, pg = (int_arg(parts[2]), int_arg(parts[3])) if parts else (None, None)
    if parts is None or parent is None or pg is None:
        await cb.answer()
        return
    await cb.answer()
    await ask_place(cb, state, session, t, lang, parts[1], parent, pg)


@router.callback_query(F.data.startswith("pd:"))
async def descend(cb: CallbackQuery, state: FSMContext, session: AsyncSession, t, lang, **ctx) -> None:
    parts = _parsed(cb, 3)
    pid = int_arg(parts[2]) if parts else None
    place = await session.get(Place, pid) if pid else None
    if parts is None or place is None:
        await cb.answer()
        return
    await cb.answer()
    if await has_children(session, place.id):
        await ask_place(cb, state, session, t, lang, parts[1], place.id, 0)
    else:
        await _choose(cb, state, parts[1], place, place.name_uz, dict(ctx, session=session, t=t, lang=lang))


@router.callback_query(F.data.startswith("pk:"))
async def choose(cb: CallbackQuery, state: FSMContext, session: AsyncSession, t, lang, **ctx) -> None:
    parts = _parsed(cb, 3)
    pid = int_arg(parts[2]) if parts else None
    place = await session.get(Place, pid) if pid else None
    if parts is None or place is None:
        await cb.answer()
        return
    await cb.answer()
    await _choose(cb, state, parts[1], place, place.name_uz, dict(ctx, session=session, t=t, lang=lang))


@router.callback_query(F.data.startswith("pt:"))
async def choose_typed(cb: CallbackQuery, state: FSMContext, session: AsyncSession, t, lang, **ctx) -> None:
    """"Use what I typed" — a place that is not in our database (the request keeps the text only)."""
    parts = _parsed(cb, 2)
    text = (await state.get_data()).get("typed") if parts else None
    await cb.answer()
    if parts is None or not text or parts[1] == "h":
        return
    await _choose(cb, state, parts[1], None, text, dict(ctx, session=session, t=t, lang=lang))


@router.message(StateFilter(Order.place, Reg.home), F.text, ~F.text.startswith("/"))
async def typed_search(msg: Message, state: FSMContext, session: AsyncSession, t, lang) -> None:
    role = (await state.get_data()).get("role", "f")
    query = (msg.text or "").strip()[:64]
    hits = (await PlaceIndex.load(session)).search(query, limit=PAGE)
    await state.update_data(typed=query)
    rows = [[btn(label(h.name, None, lang), f"pk:{role}:{h.id}")] for h in hits]
    if role != "h":
        rows.append([btn(t("bot.place.use_typed", text=query), f"pt:{role}")])
    rows.append([btn(f"↩ {t('common.back')}", f"pg:{role}:0:0")])
    await show(msg, t("bot.place.results" if hits else "bot.place.none"), kb(*rows))
