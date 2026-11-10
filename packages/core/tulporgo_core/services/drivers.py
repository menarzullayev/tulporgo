"""Driver onboarding (decision 12: phone + car → can work; documents → "Tasdiqlangan" badge)."""
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings
from ..db import utcnow
from ..enums import DriverStatus
from ..errors import Conflict, Forbidden, Invalid
from ..events import DriverRegistered, DriverVerified
from ..models import Driver, User
from . import billing, referral
from .users import ensure_referral_code

PLATE = re.compile(r"^(\d{2})([A-Z]\d{3}[A-Z]{2}|\d{3}[A-Z]{3})$")      # 01A123BC (private) | 01123ABC (company)


def normalize_plate(plate: str) -> str:
    p = re.sub(r"[\s\-_]", "", (plate or "").upper())
    if not PLATE.match(p):
        raise Invalid("bad_plate", "Uzbek plate expected, e.g. 30 A 123 BC")
    return p


async def get_driver(s: AsyncSession, user: User) -> Driver | None:
    return (await s.execute(select(Driver).where(Driver.user_id == user.id))).scalar_one_or_none()


async def register_driver(s: AsyncSession, user: User, settings: Settings, *, car_make: str, car_color: str,
                          car_plate: str, seats: int = 4, car_photo_file_id: str | None = None,
                          home_place_id: int | None = None, referral_code: str | None = None, bus=None) -> Driver:
    if user.is_blocked:
        raise Forbidden("blocked")
    if not user.phone:
        raise Invalid("phone_required")
    if await get_driver(s, user):
        raise Conflict("already_driver")
    if not (1 <= seats <= 8):
        raise Invalid("bad_seats")
    plate = normalize_plate(car_plate)
    if (await s.execute(select(Driver.id).where(Driver.car_plate == plate))).first():
        raise Conflict("plate_taken")
    d = Driver(user_id=user.id, car_make=car_make.strip()[:64], car_color=car_color.strip()[:32], car_plate=plate,
               seats=seats, car_photo_file_id=car_photo_file_id, home_place_id=home_place_id,
               status=DriverStatus.ACTIVE)
    d.user = user                                          # bind now: no lazy load later in async code
    billing.extend(d, settings.trial_days)                 # 7-day trial (decision 10)
    s.add(d)
    await ensure_referral_code(s, user)
    if referral_code:
        await referral.link(s, user, referral_code)
    await s.flush()
    if bus:
        await bus.publish(DriverRegistered(d.id))
    return d


async def submit_documents(s: AsyncSession, driver: Driver, license_file_id: str, techpass_file_id: str) -> Driver:
    if not license_file_id or not techpass_file_id:
        raise Invalid("documents_required")
    driver.license_file_id, driver.techpass_file_id = license_file_id, techpass_file_id
    return driver


async def verify(s: AsyncSession, admin: User, driver: Driver, settings: Settings, bus=None) -> Driver:
    if not admin.is_admin:
        raise Forbidden("admin_only")
    if not (driver.license_file_id and driver.techpass_file_id):
        raise Invalid("documents_missing")
    if driver.verified:
        return driver
    driver.verified, driver.verified_at, driver.verified_by_id = True, utcnow(), admin.id
    await referral.grant_on_verification(s, driver, settings, bus)
    if bus:
        await bus.publish(DriverVerified(driver.id))
    return driver


async def set_status(s: AsyncSession, admin: User, driver: Driver, status: DriverStatus) -> Driver:
    if not admin.is_admin:
        raise Forbidden("admin_only")
    driver.status = status
    return driver
