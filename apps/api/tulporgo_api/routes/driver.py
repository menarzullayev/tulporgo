"""Driver side: registration, document upload (-> Telegram file ids), the driver's own offers (decision 12)."""
import logging

from fastapi import APIRouter, Depends, File, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.formparsers import MultiPartParser
from tulporgo_core.config import Settings
from tulporgo_core.errors import DomainError, Forbidden, Invalid, NotFound
from tulporgo_core.models import Offer, Place, RideRequest, Trip, User
from tulporgo_core.services import documents, drivers
from tulporgo_core.services.referral import code_from_start
from tulporgo_core.services.users import set_phone

from ..deps import current_user, get_bus, get_session, get_settings
from ..telegram_api import TelegramUploader
from .common import Outbox, commit_and_publish, get_outbox, iso, to_local_iso
from .me import me_view

log = logging.getLogger(__name__)
router = APIRouter(prefix="/driver", tags=["driver"])

MAX_FILE = 8 * 1024 * 1024
# Starlette spools uploaded parts to a temp file above 1 MB; keep them in memory up to our limit instead, so a
# driver's documents are never written to the server disk (they only pass through to Telegram).
MultiPartParser.spool_max_size = MAX_FILE + 1024


class NotConfigured(DomainError):
    status = 503


class TooLarge(DomainError):
    status = 413


class DriverIn(BaseModel):
    phone: str | None = Field(default=None, max_length=32)
    car_make: str = Field(min_length=2, max_length=64)
    car_color: str = Field(min_length=2, max_length=32)
    car_plate: str = Field(min_length=6, max_length=16)
    seats: int = Field(default=4, ge=1, le=8)
    home_place_id: int | None = None
    referral_code: str | None = Field(default=None, max_length=20)


def get_uploader(settings: Settings = Depends(get_settings)) -> TelegramUploader:
    return TelegramUploader(settings.bot_token)


def sniff(data: bytes) -> tuple[str, str] | None:
    """(extension, content type) from the file's magic bytes; the client's name and type are never trusted."""
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg", "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png", "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp", "image/webp"
    if data.startswith(b"%PDF-"):
        return "pdf", "application/pdf"
    return None


async def read_upload(f: UploadFile | None, name: str, required: bool = True) -> tuple[bytes, str, str] | None:
    if f is None or not f.filename:
        if required:
            raise Invalid("documents_required", f"{name} missing")
        return None
    data = await f.read(MAX_FILE + 1)
    if len(data) > MAX_FILE:
        raise TooLarge("file_too_large", f"{name} is larger than {MAX_FILE // (1024 * 1024)} MB")
    kind = sniff(data)
    if not data or kind is None:
        raise Invalid("bad_file_type", f"{name}: JPEG, PNG, WebP or PDF expected")
    return data, kind[0], kind[1]


@router.post("", status_code=201)
async def register(body: DriverIn, user: User = Depends(current_user), s: AsyncSession = Depends(get_session),
                   settings: Settings = Depends(get_settings), bus=Depends(get_bus), out: Outbox = Depends(get_outbox)):
    if body.phone:
        await set_phone(s, user, body.phone)
    if body.home_place_id is not None and await s.get(Place, body.home_place_id) is None:
        raise NotFound("place_not_found")
    code = body.referral_code.strip() if body.referral_code else None
    code = code_from_start(code) if code and code.lower().startswith("ref_") else code
    await drivers.register_driver(s, user, settings, car_make=body.car_make, car_color=body.car_color,
                                  car_plate=body.car_plate, seats=body.seats, home_place_id=body.home_place_id,
                                  referral_code=code, bus=out)
    await commit_and_publish(s, out, bus)
    return await me_view(s, user, settings)


@router.post("/documents")
async def upload_documents(request: Request, license_file: UploadFile | None = File(default=None, alias="license"),
                           techpass_file: UploadFile | None = File(default=None, alias="techpass"),
                           car_photo_file: UploadFile | None = File(default=None, alias="car_photo"), user: User = Depends(current_user),
                           s: AsyncSession = Depends(get_session), settings: Settings = Depends(get_settings),
                           uploader: TelegramUploader = Depends(get_uploader)):
    """Driving licence + vehicle registration (both required -> "Tasdiqlangan" badge after admin review), optional
    car photo. Each file is sent to the private storage chat (file ids are kept) and, when a documents key is
    configured, the licence and tech passport are also stored encrypted on our server (decision 57). Both copies or
    an error: if the server copy fails the request fails (the Telegram copy may remain, it is logged)."""
    if int(request.headers.get("content-length") or 0) > 3 * MAX_FILE + 64 * 1024:
        raise TooLarge("file_too_large")
    d = await drivers.get_driver(s, user)
    if d is None:
        raise Forbidden("not_a_driver")
    if not settings.storage_chat_id:
        raise NotConfigured("storage_not_configured")
    lic, tp = await read_upload(license_file, "license"), await read_upload(techpass_file, "techpass")
    photo = await read_upload(car_photo_file, "car_photo", required=False)
    ids = {}
    for kind, item in (("license", lic), ("techpass", tp), ("car_photo", photo)):
        if item is None:
            continue
        data, ext, ctype = item
        ids[kind] = await uploader.send_document(settings.storage_chat_id, f"{kind}-{d.id}.{ext}", data, ctype,
                                                 caption=f"{kind} / driver #{d.id}")
    try:
        for kind, item in (("license", lic), ("techpass", tp)):
            assert item is not None                          # both are required above
            await documents.store(s, d, kind, item[0], item[2], settings)
    except Exception:
        log.error("server copy of driver %s documents failed; the Telegram copy stays in the storage chat", d.id)
        raise
    await drivers.submit_documents(s, d, ids["license"], ids["techpass"])
    if "car_photo" in ids:
        d.car_photo_file_id = ids["car_photo"]
    return await me_view(s, user, settings)


@router.get("/offers")
async def driver_offers(user: User = Depends(current_user), s: AsyncSession = Depends(get_session)):
    d = await drivers.get_driver(s, user)
    if d is None:
        raise Forbidden("not_a_driver")
    rows = (await s.execute(select(Offer, RideRequest).join(RideRequest, RideRequest.id == Offer.request_id)
                            .where(Offer.driver_id == d.id).order_by(Offer.id.desc()).limit(30))).all()
    trips = {}
    if rows:
        trips = {t.offer_id: t.id for t in (await s.execute(
            select(Trip).where(Trip.offer_id.in_([o.id for o, _ in rows])))).scalars()}
    return {"items": [{
        "id": o.id, "request_id": r.id, "status": o.status, "price": o.price, "counter_price": o.counter_price,
        "message": o.message, "created_at": iso(o.created_at), "trip_id": trips.get(o.id),
        "from_text": r.from_text, "to_text": r.to_text, "depart_at": to_local_iso(r.depart_at), "seats": r.seats,
        "request_status": r.status,
    } for o, r in rows]}
