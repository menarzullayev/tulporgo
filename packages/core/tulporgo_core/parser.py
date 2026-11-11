"""Free-text order parser (decision 47): 'Qo'shrabot → Samarqand 07:30 2 kishi', 'Qoshrabotdan Samarqandga ertaga
8 da', 'Самарканд - Кошрабад завтра 18:00'. Returns None when no route can be found, so the bot falls back to buttons."""
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, timezone

from .places import PlaceIndex, PlaceRef, key, strip_suffix, to_latin

UZT = timezone(timedelta(hours=5))
# All word lists are in Latin: the input is transliterated first (to_latin), so Cyrillic/Russian arrive as Latin.
NUM_WORDS = {"bir": 1, "ikki": 2, "uch": 3, "to'rt": 4, "tort": 4, "besh": 5, "odin": 1, "dva": 2, "tri": 3, "chetyre": 4}
DAY_WORDS = {"poslezavtra": 2, "bugun": 0, "ertaga": 1, "indin": 2, "segodnya": 0, "zavtra": 1}
NOW_WORDS = ("hozir", "srochno", "tezda", "seychas")
# "from the village" names no place; fuzzy search would turn it into a mahalla such as "Katta qishloq" (2026-11-11)
GENERIC_PLACES = frozenset(key(w) for w in ("qishloq", "kishloq", "ovul", "mahalla", "uy", "dom", "derevnya"))
SEP = re.compile(r"\s*(?:→|->|—|–|=>|>|\s-\s|-(?=\S)|/)\s*")


@dataclass
class ParsedRoute:
    from_text: str
    to_text: str
    from_place: PlaceRef | None
    to_place: PlaceRef | None
    depart_at: datetime | None          # naive UTC; None = as soon as possible
    seats: int


def _local_now(now: datetime | None) -> datetime:
    """Uzbekistan local time; a naive `now` is taken as UTC (the project-wide convention)."""
    if now is None:
        return datetime.now(UZT)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    return now.astimezone(UZT)


def _extract_time(t: str, now_local: datetime) -> tuple[datetime | None, str]:
    day = None
    for w, d in DAY_WORDS.items():
        if re.search(rf"\b{re.escape(w)}\b", t):
            day = d
            t = re.sub(rf"\b{re.escape(w)}\b", " ", t)
            break
    hm = None
    m = re.search(r"\b([01]?\d|2[0-3])[:.]([0-5]\d)\b", t)
    if m:
        hm = (int(m[1]), int(m[2]))
        t = t[: m.start()] + " " + t[m.end():]
    else:
        m = re.search(r"\b(?:soat\s*|v\s*)?([01]?\d|2[0-3])\s*(?:da|ga|cha|chasov|chasa|chas|ch)\b", t)
        if m:
            hm = (int(m[1]), 0)
            t = t[: m.start()] + " " + t[m.end():]
    if hm is None and day is None:
        return None, t
    base: date = (now_local + timedelta(days=day or 0)).date()
    h, mi = hm or (8, 0)
    local = datetime.combine(base, time(h, mi), UZT)
    if day is None and local < now_local - timedelta(minutes=15):
        local += timedelta(days=1)                         # a time already >15 min past today means tomorrow
    return local.astimezone(UTC).replace(tzinfo=None), t


def _extract_seats(t: str) -> tuple[int, str]:
    m = re.search(r"\b(\d|bir|ikki|uch|to'rt|tort|besh|odin|dva|tri|chetyre)\s*(?:ta\s*)?(kishi|odam|joy|nafar|"
                  r"chelovek|chel|mesto|mesta|mest)\b", t)
    if not m:
        return 1, t
    n = int(m[1]) if m[1].isdigit() else NUM_WORDS[m[1]]
    return max(1, min(n, 8)), t[: m.start()] + " " + t[m.end():]


def _clean(part: str) -> str:
    part = re.sub(r"\b(dan|ga|ka|qa|iz|v|do|ot|tomonga|tomondan|taksi|kerak|bor|mashina|moshin)\b", " ", part)
    return re.sub(r"[^\w' ]", " ", part).strip(" '")


def when_and_seats(text: str, now: datetime | None = None) -> tuple[datetime | None, int]:
    """Departure (naive UTC, None = now / not said) and seats of any text, without needing a route."""
    now_local = _local_now(now)
    t = to_latin(text)
    depart, t = _extract_time(t, now_local)
    if any(w in t for w in NOW_WORDS) and depart and depart <= (now_local.astimezone(UTC).replace(tzinfo=None)
                                                                 + timedelta(minutes=5)):
        depart = None
    return depart, _extract_seats(t)[0]


def parse(text: str, index: PlaceIndex, now: datetime | None = None) -> ParsedRoute | None:
    if not text or not text.strip():
        return None
    now_local = _local_now(now)
    t = to_latin(text)
    asap = any(w in t for w in NOW_WORDS)
    depart, t = _extract_time(t, now_local)
    if asap and depart and depart <= (now_local.astimezone(UTC).replace(tzinfo=None) + timedelta(minutes=5)):
        depart = None
    seats, t = _extract_seats(t)

    parts = [p for p in SEP.split(t) if p and p.strip()]
    if len(parts) >= 2:
        a, b = _clean(parts[0]), _clean(parts[1])
    else:
        m = re.search(r"([\w' ]+?)\s*-?(?:dan|tan)\s+([\w' ]+?)\s*-?(?:ga|ka|qa)\b", t)
        # destination first: 'Navoiyga qishloqdan' (2026-11-11 survey). Only when the -ga word is a known place, so
        # 'ertaga Jo'shdan ...' still goes the usual way.
        inv = re.search(r"\b([\w']+?-?(?:ga|ka|qa))\s+([\w']+?)-?(?:dan|tan)\b", t)
        if inv and index.exact(inv[1]):
            a, b = _clean(inv[2]), _clean(inv[1])
        elif m:
            # keep the suffixes on the edge words: 'urganchi' alone is no place, 'urganchidan' is Urganch
            a, b = _clean(m[1] + "dan"), _clean(m[2] + "ga")
        else:
            words = [w for w in re.findall(r"[\w']+", t) if len(w) >= 3 and key(strip_suffix(w)) not in GENERIC_PLACES]
            found: list[tuple[str, PlaceRef]] = []
            for w in words:                               # first two words that are places, in order
                ref = index.exact(w)
                if ref and (not found or ref.id != found[-1][1].id):
                    found.append((w, ref))
            if len(found) < 2:
                return None
            a, b = found[0][0], found[1][0]
            if suffix_role(a, index) == "to" or suffix_role(b, index) == "from":
                a, b = b, a                               # 'Qo'shrabotga ... Sebistonda bir kishi bor'
    if not a or not b:
        return None
    pa, pb = _match(a, index), _match(b, index)
    if not pa and not pb:
        return None
    return ParsedRoute(a, b, pa, pb, depart, seats)


def suffix_role(word: str, index: PlaceIndex) -> str | None:
    """'from' for Jo'shdan / Sebistonda, 'to' for Samarqandga — only when the suffix really was cut off a known place
    (Nurota ends in -ta but is the name itself)."""
    w = to_latin(word.strip()).lower()
    base = strip_suffix(word)
    if base == w or not (index.by_key.get(key(base)) or (base.endswith("i") and index.by_key.get(key(base[:-1])))):
        return None
    if re.search(r"(?:dan|tan|da|ta)$", w):
        return "from"
    if re.search(r"(?:ga|ka|qa|gacha)$", w):
        return "to"
    return None


def _match(text: str, index: PlaceIndex) -> PlaceRef | None:
    if key(strip_suffix(text)) in GENERIC_PLACES:
        return None
    ref = index.exact(text)
    if ref:
        return ref
    for w in sorted(re.findall(r"[\w']+", text), key=len, reverse=True):
        ref = index.exact(w)
        if ref:
            return ref
    hits = index.search(text, limit=1)
    return hits[0] if hits else None
