"""Place names: one matching key for every spelling (current Latin, new alphabet, Cyrillic, Russian), fuzzy search,
CSV seeding. Data files live in tulporgo_core/data (see data/SOURCES.md)."""
import csv
import difflib
import re
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .enums import PlaceKind
from .models import Place

DATA = Path(__file__).resolve().parent / "data"
APOS = "'‘’ʻʼ`"
CYR = {"а": "a", "б": "b", "в": "v", "г": "g", "ғ": "g'", "д": "d", "е": "e", "ё": "yo", "ж": "j", "з": "z", "и": "i",
       "й": "y", "к": "k", "қ": "q", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t",
       "у": "u", "ў": "o'", "ф": "f", "х": "x", "ҳ": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sh", "ъ": "'", "ь": "",
       "ы": "i", "э": "e", "ю": "yu", "я": "ya"}
NEW = {"ö": "o'", "ğ": "g'", "ş": "sh", "ç": "ch"}


def to_latin(text: str) -> str:
    """Any Uzbek spelling → current Latin with ASCII apostrophes, lowercase."""
    t = text.lower()
    for a in APOS:
        t = t.replace(a, "'")
    t = "".join(NEW.get(c, c) for c in t)
    return "".join(CYR.get(c, c) for c in t)


def key(text: str) -> str:
    """Matching key: Latin, no apostrophes/punctuation, q→k and x→h so 'Samarqand'='Samarkand', 'Xatirchi'='Hatirchi'."""
    t = re.sub(r"[^a-z0-9 ]", "", to_latin(text).replace("'", ""))
    t = t.replace("q", "k").replace("x", "h")
    return re.sub(r"\s+", " ", t).strip()


@dataclass
class PlaceRef:
    id: int
    name: str
    kind: str
    keys: list[str] = field(default_factory=list)
    popularity: int = 0
    area_id: int | None = None          # district/city a mahalla or POI belongs to (decision 73: district-level match)

    @property
    def area(self) -> int:
        return self.area_id or self.id


class PlaceIndex:
    """In-memory index for fast matching (parser, inline search). Build it from the DB with `load`."""

    def __init__(self, refs: list[PlaceRef]):
        self.refs = refs
        self.by_key: dict[str, list[PlaceRef]] = {}
        for r in refs:
            for k in r.keys:
                self.by_key.setdefault(k, []).append(r)

    @classmethod
    async def load(cls, session: AsyncSession) -> "PlaceIndex":
        rows = (await session.execute(select(Place))).scalars().all()
        return cls([ref_of(p) for p in rows])

    def _rank(self, r: PlaceRef) -> tuple:
        order: list[str] = [PlaceKind.CITY, PlaceKind.DISTRICT, PlaceKind.POI, PlaceKind.MAHALLA, PlaceKind.REGION]
        return (-r.popularity, order.index(r.kind) if r.kind in order else 9, r.name)

    def exact(self, text: str) -> PlaceRef | None:
        base = strip_suffix(text)
        cands = self.by_key.get(key(base), []) or self.by_key.get(key(text), [])
        if not cands and base != to_latin(text.strip()) and base.endswith("i") and len(base) > 4:
            cands = self.by_key.get(key(base[:-1]), [])        # colloquial linking -i-: 'Urganchidan' -> Urganch
        return sorted(cands, key=self._rank)[0] if cands else None

    def search(self, text: str, limit: int = 8) -> list[PlaceRef]:
        k = key(strip_suffix(text))
        if not k:
            return []
        hits = {r.id: r for kk, rs in self.by_key.items() if kk.startswith(k) or f" {k}" in f" {kk}" for r in rs}
        if len(hits) < limit:
            for kk in difflib.get_close_matches(k, list(self.by_key), n=limit, cutoff=0.8):
                for r in self.by_key[kk]:
                    hits.setdefault(r.id, r)
        return sorted(hits.values(), key=self._rank)[:limit]


SUFFIXES = ("dan", "tan", "ga", "ka", "qa", "da", "ta", "gacha", "dagi", "lik", "liklar")


def strip_suffix(word: str) -> str:
    """'Qo'shrabotdan' → 'Qo'shrabot', 'Samarqandga' → 'Samarqand' (Latin or Cyrillic)."""
    w = to_latin(word.strip())
    for s in sorted(SUFFIXES, key=len, reverse=True):
        if w.endswith(s) and len(w) - len(s) >= 3:
            return w[: -len(s)].rstrip("-'")
    return w


def ref_of(p: Place) -> PlaceRef:
    names = [p.name_uz] + ([p.name_ru] if p.name_ru else []) + list(p.aliases or [])
    area = p.parent_id if p.kind in (PlaceKind.MAHALLA, PlaceKind.POI) and p.parent_id else None
    return PlaceRef(p.id, p.name_uz, p.kind, sorted({key(n) for n in names if n}), p.popularity or 0, area)


async def seed(session: AsyncSession, data_dir: Path = DATA) -> int:
    """Idempotent import of data/*.csv. Returns the number of places created."""
    existing = {(p.kind, key(p.name_uz), p.parent_id): p for p in (await session.execute(select(Place))).scalars()}
    created = 0

    async def upsert(kind, name, parent_id=None, code=None, aliases=(), popularity=0):
        nonlocal created
        k = (kind, key(name), parent_id)
        if k in existing:
            return existing[k]
        p = Place(kind=kind, name_uz=name, parent_id=parent_id, code=code or None, aliases=list(aliases),
                  popularity=popularity)
        session.add(p)
        await session.flush()
        existing[k] = p
        created += 1
        return p

    uz = await upsert(PlaceKind.COUNTRY, "O'zbekiston")
    regions: dict[str, Place] = {}
    districts: dict[tuple[str, str], Place] = {}           # (region key, district key) — names repeat across regions
    f = data_dir / "regions_districts.csv"
    if f.exists():
        for row in csv.DictReader(f.open(encoding="utf-8")):
            reg = regions.get(row["region_uz"]) or await upsert(PlaceKind.REGION, row["region_uz"], uz.id, row.get("region_code"))
            regions[row["region_uz"]] = reg
            city = row.get("kind", "").strip() == "shahar"
            name = row["district_uz"]
            short = re.sub(r"\s+shahri$", "", name)       # "Samarqand shahri" is also just "Samarqand"
            p = await upsert(PlaceKind.CITY if city else PlaceKind.DISTRICT, name, reg.id, row.get("district_code"),
                             aliases=[short] if city and short != name else ())
            districts[(key(row["region_uz"]), key(name))] = p
    f = data_dir / "samarqand_mahallas.csv"
    if f.exists():
        reg_key = key("Samarqand viloyati")
        for row in csv.DictReader(f.open(encoding="utf-8")):
            parent = districts.get((reg_key, key(row["district_uz"])))
            await upsert(PlaceKind.MAHALLA, row["mahalla_uz"], parent.id if parent else None)
    f = data_dir / "landmarks.csv"       # decision 73: bazaars, stations, missing villages — only owner-approved rows
    if f.exists():
        for row in csv.DictReader(f.open(encoding="utf-8")):
            if (row.get("approved") or "").strip().lower() != "yes":
                continue
            parent = districts.get((key(row.get("region_uz") or "Samarqand viloyati"), key(row.get("district_uz") or "")))
            lm_kind = PlaceKind.POI if (row.get("kind") or "").strip() == "poi" else PlaceKind.MAHALLA
            extra = [x.strip() for x in (row.get("aliases") or "").split("|") if x.strip()]
            await upsert(lm_kind, row["name_uz"], parent.id if parent else None, aliases=extra)
    f = data_dir / "aliases.csv"                             # Russian/other spellings + popularity from the analysis
    if f.exists():
        for row in csv.DictReader(f.open(encoding="utf-8")):
            for (kind, k, _), p in existing.items():
                if kind == row["kind"] and k == key(row["name_uz"]):
                    extra = [a.strip() for a in row["aliases"].split("|") if a.strip()]
                    p.aliases = sorted(set(p.aliases or []) | set(extra))
                    p.popularity = max(p.popularity or 0, int(row.get("popularity") or 0))
    return created


def corridors(index: PlaceIndex, data_dir: Path = DATA) -> list[list[int]]:
    """Owner-approved road corridors as ordered area ids, for "on the way" matching (decision 73). A corridor with a
    stop that is not in the places index is skipped as a whole — a wrong order is worse than none."""
    f = data_dir / "corridors.csv"
    out: list[list[int]] = []
    if not f.exists():
        return out
    for row in csv.DictReader(f.open(encoding="utf-8")):
        if (row.get("approved") or "").strip().lower() != "yes":
            continue
        refs = [index.exact(s.strip()) for s in row["stops"].split("|") if s.strip()]
        if refs and all(refs):
            out.append([r.area for r in refs if r])
    return out
