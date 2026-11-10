"""KPIs (decision 53) and the weekly report text for the owner."""
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import utcnow
from ..enums import TripStatus, UserbotStatus
from ..models import Driver, RideRequest, Trip, UserbotAccount

TARGETS = {  # metric: (day 30, day 60)
    "drivers": (100, 250),
    "userbot_drivers": (30, 80),
    "daily_requests": (20, 50),
    "daily_trips": (10, 30),
    "active_drivers": (15, 50),
    "blocked_userbots": (0, 0),
}
LABELS = {
    "drivers": "Ro'yxatdan o'tgan haydovchilar",
    "userbot_drivers": "Userbot ulagan haydovchilar",
    "daily_requests": "Kunlik so'rovlar (7 kun o'rtacha)",
    "daily_trips": "Kunlik kelishilgan qatnovlar (7 kun o'rtacha)",
    "active_drivers": "Faol haydovchilar (7 kunda 1+ qatnov)",
    "blocked_userbots": "Bloklangan haydovchi hisoblari",
}


@dataclass
class Kpi:
    at: datetime
    values: dict[str, float]


async def compute(s: AsyncSession, now: datetime | None = None) -> Kpi:
    now = now or utcnow()
    week = now - timedelta(days=7)
    scalar = lambda q: s.scalar(q)  # noqa: E731
    v = {
        "drivers": await scalar(select(func.count(Driver.id))) or 0,
        "userbot_drivers": await scalar(select(func.count(UserbotAccount.id))
                                        .where(UserbotAccount.status.in_([UserbotStatus.CONNECTED, UserbotStatus.PAUSED,
                                                                          UserbotStatus.FLOOD_WAIT]))) or 0,
        "daily_requests": round((await scalar(select(func.count(RideRequest.id))
                                              .where(RideRequest.created_at >= week)) or 0) / 7, 1),
        "daily_trips": round((await scalar(select(func.count(Trip.id)).where(
            Trip.created_at >= week, Trip.status != TripStatus.CANCELLED)) or 0) / 7, 1),
        "active_drivers": await scalar(select(func.count(distinct(Trip.driver_id))).where(
            Trip.completed_at >= week, Trip.status == TripStatus.COMPLETED)) or 0,
        "blocked_userbots": await scalar(select(func.count(UserbotAccount.id))
                                         .where(UserbotAccount.status == UserbotStatus.STOPPED)) or 0,
    }
    return Kpi(now, v)


def report(kpi: Kpi, launch_day: datetime | None = None) -> str:
    """Uzbek (new alphabet is applied by the bot's text layer) plain-text weekly report."""
    day = (kpi.at - launch_day).days if launch_day else None
    lines = [f"TulporGo — haftalik KPI ({kpi.at:%Y-%m-%d})" + (f", ishga tushganiga {day} kun" if day is not None else "")]
    for k, label in LABELS.items():
        t30, t60 = TARGETS[k]
        val = kpi.values[k]
        if k == "blocked_userbots":
            mark = "✅" if val <= t30 else "⚠️"
        else:
            mark = "✅" if val >= t30 else "⏳"
        lines.append(f"{mark} {label}: {val:g} (maqsad 30 kun: {t30}, 60 kun: {t60})")
    return "\n".join(lines)
