"""Data-subject rights (privacy policy §8): export own data, delete own data.

Deletion anonymises instead of dropping rows that other people or the books depend on:
- removed: phone, names, username, women marker, referral code, car photo, document photos, the whole userbot
  account (encrypted session, groups, post log), comments the user wrote in ratings;
- kept, linked to the anonymised user: trips (the other party's history and ratings), payments (accounting —
  retention period is a lawyer item), complaints (evidence), referral bonuses;
- `tg_id` is replaced so the person is no longer linked — except for blocked users, whose ban must keep working
  (privacy policy §6, retention of bans is a lawyer item).
"""
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import utcnow
from ..enums import DriverStatus, OfferStatus, RequestStatus, TripStatus, UserbotStatus
from ..errors import Conflict
from ..events import UserbotStopped
from ..models import (
    Complaint,
    Driver,
    Offer,
    Payment,
    Rating,
    RideRequest,
    Trip,
    User,
    UserbotAccount,
    UserbotGroup,
    UserbotPost,
)

ACTIVE_TRIP = (TripStatus.CONFIRMED, TripStatus.STARTED)


def _iso(d: datetime | None) -> str | None:
    return d.isoformat() if d else None


async def export_user_data(s: AsyncSession, user: User) -> dict:
    """Everything stored about the user, as JSON-ready data. Never contains session strings or file ids."""
    d = (await s.execute(select(Driver).where(Driver.user_id == user.id))).scalar_one_or_none()
    out: dict = {
        "profile": {"telegram_id": user.tg_id, "username": user.username, "first_name": user.first_name,
                    "language": user.lang, "phone": user.phone, "women_marker": user.is_woman,
                    "referral_code": user.referral_code, "blocked": user.is_blocked,
                    "created_at": _iso(user.created_at)},
        "driver": None,
        "requests": [],
        "trips": [],
        "ratings_given": [],
        "ratings_received": [],
        "complaints_filed": [],
        "complaints_against_count": 0,
        "payments": [],
        "userbot": None,
    }
    driver_trips = []
    if d is not None:
        out["driver"] = {"status": d.status, "car_make": d.car_make, "car_color": d.car_color,
                         "car_plate": d.car_plate, "seats": d.seats, "car_photo_on_file": bool(d.car_photo_file_id),
                         "documents_on_file": bool(d.license_file_id or d.techpass_file_id),
                         "verified": d.verified, "plan": d.plan, "subscription_until": _iso(d.subscription_until),
                         "ambassador": d.ambassador, "rating": d.rating, "created_at": _iso(d.created_at)}
        driver_trips = [Trip.driver_id == d.id]
        acc = (await s.execute(select(UserbotAccount).where(UserbotAccount.driver_id == d.id))).scalar_one_or_none()
        if acc is not None:
            groups = (await s.execute(select(UserbotGroup).where(UserbotGroup.account_id == acc.id))).scalars().all()
            posts = await s.scalar(select(func.count()).select_from(UserbotPost).join(UserbotGroup)
                                   .where(UserbotGroup.account_id == acc.id))
            out["userbot"] = {"status": acc.status, "telegram_user_id": acc.tg_user_id,
                              "consent_at": _iso(acc.consent_at), "min_interval_minutes": acc.min_interval_minutes,
                              "risk_acknowledged": acc.risk_acknowledged, "post_template": acc.post_template,
                              "groups": [{"title": g.title, "enabled": g.enabled} for g in groups],
                              "posts_logged": posts or 0}

    for r in (await s.execute(select(RideRequest).where(RideRequest.passenger_id == user.id)
                              .order_by(RideRequest.id))).scalars():
        out["requests"].append({"from": r.from_text, "to": r.to_text, "depart_at": _iso(r.depart_at),
                                "seats": r.seats, "note": r.note, "status": r.status,
                                "created_at": _iso(r.created_at)})
    for t in (await s.execute(select(Trip).where(or_(Trip.passenger_id == user.id, *driver_trips))
                              .order_by(Trip.id))).scalars():
        r = await s.get(RideRequest, t.request_id)
        out["trips"].append({"role": "passenger" if t.passenger_id == user.id else "driver",
                             "from": r.from_text if r else None, "to": r.to_text if r else None,
                             "price": t.price, "status": t.status, "created_at": _iso(t.created_at),
                             "completed_at": _iso(t.completed_at)})
    for g in (await s.execute(select(Rating).where(Rating.from_user_id == user.id))).scalars():
        out["ratings_given"].append({"trip": g.trip_id, "stars": g.stars, "comment": g.comment})
    for g in (await s.execute(select(Rating).where(Rating.to_user_id == user.id))).scalars():
        out["ratings_received"].append({"trip": g.trip_id, "stars": g.stars, "comment": g.comment})
    for c in (await s.execute(select(Complaint).where(Complaint.from_user_id == user.id))).scalars():
        out["complaints_filed"].append({"text": c.text, "status": c.status, "created_at": _iso(c.created_at)})
    out["complaints_against_count"] = await s.scalar(
        select(func.count()).select_from(Complaint).where(Complaint.against_user_id == user.id)) or 0
    for p in (await s.execute(select(Payment).where(Payment.user_id == user.id).order_by(Payment.id))).scalars():
        out["payments"].append({"provider": p.provider, "plan": p.plan, "months": p.months, "amount": p.amount,
                                "currency": p.currency, "status": p.status, "created_at": _iso(p.created_at),
                                "paid_at": _iso(p.paid_at)})
    return out


@dataclass
class DeletionReport:
    requests_cancelled: int = 0
    offers_withdrawn: int = 0
    userbot_deleted: bool = False
    tg_id_kept_for_ban: bool = False


async def delete_user_data(s: AsyncSession, user: User, bus=None) -> DeletionReport:
    """Anonymise the user (see module docstring). Refused while a trip is confirmed or under way."""
    d = (await s.execute(select(Driver).where(Driver.user_id == user.id))).scalar_one_or_none()
    trip_owner = [Trip.passenger_id == user.id] + ([Trip.driver_id == d.id] if d else [])
    active = await s.scalar(select(func.count()).select_from(Trip)
                            .where(or_(*trip_owner), Trip.status.in_(ACTIVE_TRIP)))
    if active:
        raise Conflict("active_trip")

    rep = DeletionReport()
    res = await s.execute(update(RideRequest).where(RideRequest.passenger_id == user.id,
                                                   RideRequest.status == RequestStatus.OPEN)
                          .values(status=RequestStatus.CANCELLED, note=None))
    rep.requests_cancelled = res.rowcount or 0
    await s.execute(update(RideRequest).where(RideRequest.passenger_id == user.id).values(note=None))

    if d is not None:
        res = await s.execute(update(Offer).where(Offer.driver_id == d.id,
                                                  Offer.status.in_((OfferStatus.SENT, OfferStatus.COUNTERED)))
                              .values(status=OfferStatus.WITHDRAWN))
        rep.offers_withdrawn = res.rowcount or 0
        await s.execute(update(Offer).where(Offer.driver_id == d.id).values(message=None))
        acc = (await s.execute(select(UserbotAccount).where(UserbotAccount.driver_id == d.id))).scalar_one_or_none()
        if acc is not None:
            if bus is not None and acc.status == UserbotStatus.CONNECTED:
                # the worker holds the live client: it logs the Telegram session out on this event
                await bus.publish(UserbotStopped(account_id=acc.id, reason="data_deleted"))
            group_ids = select(UserbotGroup.id).where(UserbotGroup.account_id == acc.id)
            await s.execute(delete(UserbotPost).where(UserbotPost.group_id.in_(group_ids)))
            await s.execute(delete(UserbotGroup).where(UserbotGroup.account_id == acc.id))
            await s.execute(delete(UserbotAccount).where(UserbotAccount.id == acc.id))
            rep.userbot_deleted = True
        d.status = DriverStatus.SUSPENDED if d.status != DriverStatus.BLOCKED else DriverStatus.BLOCKED
        d.car_photo_file_id = d.license_file_id = d.techpass_file_id = None
        d.car_plate = f"DELETED{d.id}"[:16]
        d.car_make = d.car_color = "-"
        d.home_place_id = None

    await s.execute(update(Rating).where(Rating.from_user_id == user.id).values(comment=None))

    user.username = user.first_name = user.phone = None
    user.is_woman = False
    user.referral_code = None
    user.last_seen_at = None
    if user.is_blocked:
        rep.tg_id_kept_for_ban = True
    else:
        user.tg_id = -user.id                  # real Telegram user ids are positive: no collision, no link
    user.lang = None
    await s.flush()
    return rep


__all__ = ["export_user_data", "delete_user_data", "DeletionReport", "utcnow"]
