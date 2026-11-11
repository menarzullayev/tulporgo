"""Status vocabularies. Stored as plain strings (no native DB enums) so migrations stay portable."""
from enum import StrEnum


class Lang(StrEnum):
    UZ_NEW = "uz_new"
    UZ_LATN = "uz_latn"
    UZ_CYRL = "uz_cyrl"
    RU = "ru"
    EN = "en"


class DriverStatus(StrEnum):
    PENDING = "pending"        # registered, waiting for a quick check
    ACTIVE = "active"
    SUSPENDED = "suspended"
    BLOCKED = "blocked"


class PlaceKind(StrEnum):
    COUNTRY = "country"
    REGION = "region"
    DISTRICT = "district"
    CITY = "city"
    MAHALLA = "mahalla"
    POI = "poi"                # bazaar, station, landmark


class RequestStatus(StrEnum):
    OPEN = "open"
    MATCHED = "matched"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    COMPLETED = "completed"


class RequestSource(StrEnum):
    BUTTONS = "buttons"
    TEXT = "text"
    MINIAPP = "miniapp"
    GUEST = "guest"            # Guest Mode mention in a group (Bot API 10.0)


class OfferStatus(StrEnum):
    SENT = "sent"
    COUNTERED = "countered"    # passenger proposed a lower price (decision 7)
    ACCEPTED = "accepted"
    DECLINED = "declined"
    WITHDRAWN = "withdrawn"
    EXPIRED = "expired"


class TripStatus(StrEnum):
    CONFIRMED = "confirmed"
    STARTED = "started"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ComplaintStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"
    REJECTED = "rejected"


class Plan(StrEnum):
    BASIC = "basic"            # Asosiy 29 000 so'm / month (decision 10)
    PRO = "pro"                # Pro 59 000 — auto-post, up to 15 groups
    BUSINESS = "business"      # Biznes 99 000 — unlimited groups, priority


class PaymentProvider(StrEnum):
    P2P = "p2p"
    STARS = "stars"
    CLICK = "click"
    PAYME = "payme"
    OTHER = "other"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    AWAITING_REVIEW = "awaiting_review"   # P2P: receipt uploaded, an admin must confirm
    PAID = "paid"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class UserbotStatus(StrEnum):
    NEEDS_LOGIN = "needs_login"
    CONNECTED = "connected"
    PAUSED = "paused"          # stopped by the driver
    FLOOD_WAIT = "flood_wait"  # stopped by Telegram, resumes after flood_until
    STOPPED = "stopped"        # PEER_FLOOD / banned / revoked — needs the driver


class PostStatus(StrEnum):
    SENT = "sent"
    FAILED = "failed"
    SKIPPED = "skipped"


class RequestKind(StrEnum):
    """What a group message asks for (decision 73). A passenger trip may also carry cargo (`Detection.cargo`)."""
    PASSENGER = "passenger"
    PARCEL = "parcel"          # pochta / posilka, no people
    CARGO = "cargo"            # only goods (Damas / Labo)
    DELIVERY = "delivery"      # buy or fetch something and bring it
    BAZAAR = "bazaar"          # a trip to a bazaar (Mayiz bozor, Mol bozor, ...)


class MessageClass(StrEnum):
    REQUEST = "request"        # somebody needs a ride / a parcel carried
    DRIVER_AD = "driver_ad"    # a driver offers seats — never becomes a card
    OTHER = "other"
