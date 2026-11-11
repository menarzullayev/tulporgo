"""Reading taxi groups (decision 73): is a group message a request, what kind, and which route.

Rule-based and local: no message ever leaves the machine (localisation, decision 43). `Classifier` is the seam for a
local AI model later; `RuleClassifier` starts from the patterns of the 2026 group analysis (15 Samarqand groups).
Nothing here stores the message — callers get a `Detection` and drop the text.
"""
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from .enums import MessageClass, PlaceKind, RequestKind
from .parser import parse, when_and_seats
from .places import PlaceIndex, PlaceRef, strip_suffix, to_latin

MIN_CONFIDENCE = 0.6           # below this a message is not delivered (the local AI slot will look at these later)


def _rx(*parts: str) -> re.Pattern[str]:
    return re.compile("|".join(f"(?:{p})" for p in parts))


CAR = r"taks\w*|taxi|moshin\w*|mashina\w*|labo|damas|nexia|neksiya|cobalt|kobalt|kobilt|gentra|jentra|spark|malibu|" \
      r"lacetti|lasetti|kaptiva|captiva|onix"
NUM = r"\d|bir|ikki|uch|tort|besh"

# (pattern, weight). Text is current Latin, lowercase, without apostrophes (see `_norm`).
PASSENGER = [
    (_rx(rf"\b(?:{CAR}|haydovchi|shofyor|shafyor)\s?(?:kerak|kere|kerag|kk|bormi)\b"), 2.0),
    (_rx(r"\bkim (?:ketadi|ketyapti|ketvotti|ketayapti|boradi|boryapti|yuradi|chiqadi)\b"), 2.0),
    (_rx(rf"\bketadigan (?:{CAR})"), 2.0),
    (_rx(rf"\b(?:{NUM})\s?(?:kishi|odam|nafar)(?:miz)?\s?(?:bor|bormiz)\b"), 2.0),
    (_rx(r"\b(?:pochta|posilka|yuk) bor\b"), 2.0),
    (_rx(r"\bolib kelib ber\w*|\bolib keling\b|\bdostavka (?:kerak|kk)\b|\bsotib olib (?:kel|ber)\w*"), 2.0),
    (_rx(r"\b(?:nujno|nujen|nujna|ishu|ishem) (?:taksi|mashin\w*|voditel\w*)",
         r"\bkto (?:edet|poedet|edut|yedet)\b", r"\b(?:est|imeetsya) (?:posilka|gruz)\b"), 2.0),
    (_rx(r"\b(?:ketaman|boraman|ketmoqchiman|ketishim kerak|borishim kerak|ketishimiz kerak)\b"), 1.5),
    (_rx(r"\bnech(?:a)? pul\b|\bqancha (?:oladi|turadi|boladi)\b|\bskolko stoit\b"), 1.0),
]
DRIVER = [
    (_rx(rf"\b(?:{CAR})\s?(?:bor|b0r)\b"), 2.0),
    (_rx(rf"\b(?:(?:{NUM})\s?(?:ta\s)?)?joy(?:lar)? bor\b", r"\bbosh joy\b"), 2.0),
    (_rx(r"\b(?:kishi|odam|yolovchi|passajir|pochta)\w*\s?(?:kerak|kk|olamiz|olaman|olib ketamiz)\b", r"\b\d\s?kk\b"), 2.0),
    (_rx(r"\b(?:ketamiz|yuramiz|jonaymiz|yolga chiqamiz|ketyapmiz|chiqamiz|ketuvchi)\b(?!\s*\?)"), 1.5),
    (_rx(r"\b(?:est|svobodn\w*) mest\w*\b", r"\bvozmu\b", r"\b(?:edu|poedu)\b"), 2.0),
    (_rx(r"\bdostavka (?:xizmati|qilamiz|qilaman)\b"), 2.0),
]

DELIVERY = _rx(r"\bdostavka\b", r"\bolib kel\w*", r"\bsotib olib\b", r"\byetkazib ber\w*", r"\bkupit\b")
PARCEL = _rx(r"\bpochta\w*", r"\bposilka\w*", r"\bjonat\w*", r"\bperedat\w*")
CARGO = _rx(r"\byuk\w*", r"\bbagaj\w*", r"\bchemodan\w*", r"\bgruz\w*", r"\bbagaj\w*")
PEOPLE = _rx(rf"\b(?:{NUM})\s?(?:kishi|odam|nafar)", r"\bkishi\b", r"\bodam\b")
BAZAAR = _rx(r"\bbozor\w*", r"\bbazar\w*")


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", to_latin(text).replace("'", "")).strip()


class Classifier(Protocol):
    def classify(self, text: str) -> tuple[MessageClass, float]: ...


class RuleClassifier:
    """Weighted patterns: passenger signals against driver-ad signals. A tie is a low-confidence request."""

    def classify(self, text: str) -> tuple[MessageClass, float]:
        t = _norm(text)
        p = sum(w for rx, w in PASSENGER if rx.search(t))
        d = sum(w for rx, w in DRIVER if rx.search(t))
        if p and "?" in text:
            p += 0.5
        if not p and not d:
            return MessageClass.OTHER, 1.0
        if d > p:
            return MessageClass.DRIVER_AD, min(1.0, 0.5 + 0.2 * (d - p))
        if p == d:
            return MessageClass.REQUEST, 0.4
        return MessageClass.REQUEST, min(1.0, 0.5 + 0.2 * (p - d))


@dataclass(frozen=True)
class Detection:
    kind: RequestKind
    cargo: bool                       # people travelling with goods/luggage
    from_place: PlaceRef | None       # None = not said
    to_place: PlaceRef | None
    depart_at: datetime | None        # naive UTC; None = now / not said
    seats: int
    confidence: float


def _single_place(text: str, index: PlaceIndex) -> tuple[PlaceRef | None, PlaceRef | None]:
    """One named place: '-dan' marks the origin, anything else the destination. Two-word names first (Mayiz bozor)."""
    words = re.findall(r"[\w']+", to_latin(text))
    for n in (2, 1):
        for i in range(len(words) - n + 1):
            chunk = " ".join(words[i:i + n])
            ref = index.exact(chunk)
            if ref and len(strip_suffix(chunk)) >= 3:
                return (ref, None) if re.search(r"(?:dan|tan)$", chunk) else (None, ref)
    return None, None


def _kind(t: str, to_place: PlaceRef | None) -> tuple[RequestKind, bool]:
    cargo = bool(CARGO.search(t))
    people = bool(PEOPLE.search(t))
    if DELIVERY.search(t):
        return RequestKind.DELIVERY, cargo
    if PARCEL.search(t) and not people:
        return RequestKind.PARCEL, cargo
    if cargo and not people:
        return RequestKind.CARGO, True
    if BAZAAR.search(t) or (to_place and to_place.kind == PlaceKind.POI and "bozor" in to_place.name.lower()):
        return RequestKind.BAZAAR, cargo
    return RequestKind.PASSENGER, cargo


def detect(text: str, index: PlaceIndex, now: datetime | None = None,
           classifier: Classifier | None = None) -> Detection | None:
    """A request with at least one known place, or None (driver ads, chat, unknown places)."""
    if not text or not text.strip():
        return None
    cls, confidence = (classifier or RuleClassifier()).classify(text)
    if cls != MessageClass.REQUEST:
        return None
    route = parse(text, index, now)
    if route is not None:
        frm, to, depart, seats = route.from_place, route.to_place, route.depart_at, route.seats
    else:
        frm, to = _single_place(text, index)
        if frm is None and to is None:
            return None
        depart, seats = when_and_seats(text, now)
    kind, cargo = _kind(_norm(text), to)
    return Detection(kind, cargo, frm, to, depart, seats, confidence)
