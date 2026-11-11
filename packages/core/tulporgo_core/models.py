"""TulporGo domain model (decisions 1–53). Portable across PostgreSQL / SQLite / MySQL: string enums, JSON, naive UTC."""
from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.mysql import LONGBLOB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base, utcnow
from .enums import (
    ComplaintStatus,
    DriverStatus,
    OfferStatus,
    PaymentStatus,
    PlaceKind,
    PostStatus,
    RequestSource,
    RequestStatus,
    TripStatus,
    UserbotStatus,
)


def _now_col() -> Mapped[datetime]:
    return mapped_column(DateTime, default=utcnow, nullable=False)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str | None] = mapped_column(String(128))
    lang: Mapped[str | None] = mapped_column(String(8))
    phone: Mapped[str | None] = mapped_column(String(20))
    is_woman: Mapped[bool] = mapped_column(Boolean, default=False)          # "ayol yo'lovchi" marker (decision 13)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)        # blacklist (decision 13)
    referral_code: Mapped[str | None] = mapped_column(String(16), unique=True)
    referred_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = _now_col()
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime)

    driver: Mapped["Driver | None"] = relationship(back_populates="user", uselist=False, foreign_keys="Driver.user_id")


class Place(Base):
    __tablename__ = "places"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), default=PlaceKind.DISTRICT)
    name_uz: Mapped[str] = mapped_column(String(128), index=True)            # current Latin (canonical)
    name_ru: Mapped[str | None] = mapped_column(String(128))
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("places.id"), index=True)
    code: Mapped[str | None] = mapped_column(String(16))                    # SOATO when known
    aliases: Mapped[list] = mapped_column(JSON, default=list)               # extra spellings, lowercase
    lat: Mapped[float | None]
    lon: Mapped[float | None]
    popularity: Mapped[int] = mapped_column(Integer, default=0)

    parent: Mapped["Place | None"] = relationship(remote_side="Place.id")


class Driver(Base):
    __tablename__ = "drivers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    status: Mapped[str] = mapped_column(String(16), default=DriverStatus.PENDING)
    car_make: Mapped[str] = mapped_column(String(64))
    car_color: Mapped[str] = mapped_column(String(32))
    car_plate: Mapped[str] = mapped_column(String(16))
    car_photo_file_id: Mapped[str | None] = mapped_column(String(256))
    seats: Mapped[int] = mapped_column(Integer, default=4)
    license_file_id: Mapped[str | None] = mapped_column(String(256))        # optional docs → verified badge (12)
    techpass_file_id: Mapped[str | None] = mapped_column(String(256))
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime)
    verified_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    home_place_id: Mapped[int | None] = mapped_column(ForeignKey("places.id"))
    rating_sum: Mapped[int] = mapped_column(Integer, default=0)
    rating_count: Mapped[int] = mapped_column(Integer, default=0)
    plan: Mapped[str | None] = mapped_column(String(16))
    subscription_until: Mapped[datetime | None] = mapped_column(DateTime)
    ambassador: Mapped[bool] = mapped_column(Boolean, default=False)          # "Elchi" tag (decision 52)
    delivery_chat_id: Mapped[int | None] = mapped_column(BigInteger)          # driver's own channel for cards (73)
    feed_paused: Mapped[bool] = mapped_column(Boolean, default=False)         # "pause all" quick toggle (73)
    created_at: Mapped[datetime] = _now_col()

    # eager: bot/API always need the driver's user (tg_id, name) and async sessions cannot lazy-load
    user: Mapped[User] = relationship(back_populates="driver", foreign_keys=[user_id], lazy="selectin")

    @property
    def rating(self) -> float | None:
        return round(self.rating_sum / self.rating_count, 2) if self.rating_count else None


class DriverDocument(Base):
    """Encrypted server copy of a driver document (decision 57). One row per (driver, kind); a new upload replaces it.
    `data_encrypted` is a Fernet token, never plaintext; `sha256` is the hash of the plaintext (integrity check)."""
    __tablename__ = "driver_documents"
    __table_args__ = (UniqueConstraint("driver_id", "kind"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), index=True)
    kind: Mapped[str] = mapped_column(String(16))                            # 'license' | 'techpass'
    content_type: Mapped[str] = mapped_column(String(64))
    size: Mapped[int] = mapped_column(Integer)                               # plaintext bytes
    sha256: Mapped[str] = mapped_column(String(64))
    # LONGBLOB on MySQL (plain BLOB tops out at 64 KB), BYTEA on PostgreSQL, BLOB on SQLite
    data_encrypted: Mapped[bytes] = mapped_column(LargeBinary().with_variant(LONGBLOB(), "mysql"))
    created_at: Mapped[datetime] = _now_col()
    # set when an admin rejects the documents (decision 63): the row is purged once this moment has passed;
    # a new upload clears it
    delete_after: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)


class RideRequest(Base):
    __tablename__ = "ride_requests"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    passenger_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    from_place_id: Mapped[int | None] = mapped_column(ForeignKey("places.id"))
    to_place_id: Mapped[int | None] = mapped_column(ForeignKey("places.id"))
    from_text: Mapped[str] = mapped_column(String(128))
    to_text: Mapped[str] = mapped_column(String(128))
    depart_at: Mapped[datetime | None] = mapped_column(DateTime)            # None = "hozir" / as soon as possible
    seats: Mapped[int] = mapped_column(Integer, default=1)
    women_only: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str | None] = mapped_column(String(256))
    price_hint: Mapped[int | None] = mapped_column(Integer)                 # so'm, decision 7
    status: Mapped[str] = mapped_column(String(16), default=RequestStatus.OPEN, index=True)
    source: Mapped[str] = mapped_column(String(16), default=RequestSource.BUTTONS)
    created_at: Mapped[datetime] = _now_col()
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)

    offers: Mapped[list["Offer"]] = relationship(back_populates="request")


class Offer(Base):
    __tablename__ = "offers"
    __table_args__ = (UniqueConstraint("request_id", "driver_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("ride_requests.id"), index=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), index=True)
    price: Mapped[int] = mapped_column(Integer)
    counter_price: Mapped[int | None] = mapped_column(Integer)
    message: Mapped[str | None] = mapped_column(String(256))
    status: Mapped[str] = mapped_column(String(16), default=OfferStatus.SENT)
    created_at: Mapped[datetime] = _now_col()
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    request: Mapped[RideRequest] = relationship(back_populates="offers")
    driver: Mapped[Driver] = relationship(lazy="selectin")


class Trip(Base):
    __tablename__ = "trips"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # not unique: a request can be re-matched after a driver cancels; "one live trip per request" is enforced by the
    # conditional OPEN→MATCHED update in services.rides._make_trip (portable across PostgreSQL / SQLite / MySQL)
    request_id: Mapped[int] = mapped_column(ForeignKey("ride_requests.id"), index=True)
    offer_id: Mapped[int] = mapped_column(ForeignKey("offers.id"), unique=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), index=True)
    passenger_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    price: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default=TripStatus.CONFIRMED)
    share_token: Mapped[str] = mapped_column(String(32), unique=True)       # "share the trip" link (decision 13)
    created_at: Mapped[datetime] = _now_col()
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    cancelled_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    # message_thread_id of this trip's topic in each party's private chat with the bot (Bot API 9.3; optional feature)
    passenger_topic_id: Mapped[int | None] = mapped_column(BigInteger)
    driver_topic_id: Mapped[int | None] = mapped_column(BigInteger)


class Rating(Base):
    __tablename__ = "ratings"
    __table_args__ = (UniqueConstraint("trip_id", "from_user_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id"))
    from_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    to_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    stars: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(String(512))
    created_at: Mapped[datetime] = _now_col()


class Complaint(Base):
    __tablename__ = "complaints"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    from_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    against_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    trip_id: Mapped[int | None] = mapped_column(ForeignKey("trips.id"))
    text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default=ComplaintStatus.OPEN)
    resolved_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    resolution: Mapped[str | None] = mapped_column(String(512))
    created_at: Mapped[datetime] = _now_col()


class Payment(Base):
    __tablename__ = "payments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    provider: Mapped[str] = mapped_column(String(16))
    plan: Mapped[str] = mapped_column(String(16))
    months: Mapped[int] = mapped_column(Integer, default=1)
    amount: Mapped[int] = mapped_column(Integer)                            # so'm, or Stars for provider=stars
    currency: Mapped[str] = mapped_column(String(3), default="UZS")         # UZS | XTR
    status: Mapped[str] = mapped_column(String(16), default=PaymentStatus.PENDING, index=True)
    external_id: Mapped[str | None] = mapped_column(String(128), index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    receipt_file_id: Mapped[str | None] = mapped_column(String(256))        # P2P screenshot
    reviewed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = _now_col()
    paid_at: Mapped[datetime | None] = mapped_column(DateTime)


class ReferralBonus(Base):
    __tablename__ = "referral_bonuses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    referrer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    referred_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)   # one bonus per new driver
    days: Mapped[int] = mapped_column(Integer)
    granted_at: Mapped[datetime] = _now_col()


class UserbotAccount(Base):
    __tablename__ = "userbot_accounts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), unique=True)
    session_encrypted: Mapped[str | None] = mapped_column(Text)            # Fernet token, never plain (decision 8)
    tg_user_id: Mapped[int | None] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(16), default=UserbotStatus.NEEDS_LOGIN)
    consent_at: Mapped[datetime | None] = mapped_column(DateTime)          # risk-consent screen accepted
    consent_version: Mapped[int] = mapped_column(Integer, default=1)       # 2 = also "may watch groups" (decision 73)
    min_interval_minutes: Mapped[int] = mapped_column(Integer, default=45)  # decision 48
    jitter_minutes: Mapped[int] = mapped_column(Integer, default=15)
    daily_max_posts: Mapped[int | None] = mapped_column(Integer)
    risk_acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)  # driver lowered limits after warning
    post_template: Mapped[str | None] = mapped_column(Text)
    flood_until: Mapped[datetime | None] = mapped_column(DateTime)
    stop_reason: Mapped[str | None] = mapped_column(String(256))
    created_at: Mapped[datetime] = _now_col()

    groups: Mapped[list["UserbotGroup"]] = relationship(back_populates="account", cascade="all, delete-orphan")


class UserbotGroup(Base):
    __tablename__ = "userbot_groups"
    __table_args__ = (UniqueConstraint("account_id", "chat_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("userbot_accounts.id"), index=True)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    title: Mapped[str] = mapped_column(String(256))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_posted_at: Mapped[datetime | None] = mapped_column(DateTime)

    account: Mapped[UserbotAccount] = relationship(back_populates="groups")


class UserbotPost(Base):
    __tablename__ = "userbot_posts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("userbot_groups.id"), index=True)
    status: Mapped[str] = mapped_column(String(16), default=PostStatus.SENT)
    error: Mapped[str | None] = mapped_column(String(256))
    created_at: Mapped[datetime] = _now_col()


class DriverFilter(Base):
    """What a driver wants from the groups he is in (decision 73). Empty lists mean "any"."""
    __tablename__ = "driver_filters"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), index=True)
    name: Mapped[str] = mapped_column(String(64))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # [{"from": place id | null, "to": place id | null, "on_way": bool}] — matched at district level
    routes: Mapped[list] = mapped_column(JSON, default=list)
    time_from: Mapped[str | None] = mapped_column(String(5))                # "18:00" local; None = any time
    time_to: Mapped[str | None] = mapped_column(String(5))
    include_asap: Mapped[bool] = mapped_column(Boolean, default=True)       # "hozir" / no time given
    include_tomorrow: Mapped[bool] = mapped_column(Boolean, default=True)
    weekdays: Mapped[list] = mapped_column(JSON, default=list)              # 0 = Monday
    seats_min: Mapped[int | None] = mapped_column(Integer)
    seats_max: Mapped[int | None] = mapped_column(Integer)
    kinds: Mapped[list] = mapped_column(JSON, default=list)                 # RequestKind values
    group_chat_ids: Mapped[list] = mapped_column(JSON, default=list)        # empty = every taxi group he selected
    created_at: Mapped[datetime] = _now_col()


class GroupReader(Base):
    """The one account that watches a group for everybody (decision 73)."""
    __tablename__ = "group_readers"
    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    account_id: Mapped[int] = mapped_column(ForeignKey("userbot_accounts.id"), index=True)
    assigned_at: Mapped[datetime] = _now_col()


class FeedCard(Base):
    """A card the bot sent; deleted after 2 h. No text of the group message is kept (decision 73)."""
    __tablename__ = "feed_cards"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), index=True)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    message_id: Mapped[int] = mapped_column(Integer)
    delete_at: Mapped[datetime] = mapped_column(DateTime, index=True)
