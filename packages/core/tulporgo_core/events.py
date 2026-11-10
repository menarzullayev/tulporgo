"""Domain events shared by the bot, userbot workers and API (GOAL.md §2).

In one process use InMemoryBus; across processes RedisBus publishes JSON on one pub/sub channel.
Handlers must be idempotent — Redis pub/sub is at-most-once.
"""
import asyncio
import json
import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, fields

log = logging.getLogger(__name__)
CHANNEL = "tulporgo.events"


@dataclass(frozen=True)
class Event:
    @property
    def name(self) -> str:
        return type(self).__name__


@dataclass(frozen=True)
class RequestCreated(Event):
    request_id: int


@dataclass(frozen=True)
class RequestClosed(Event):
    request_id: int
    status: str


@dataclass(frozen=True)
class OfferCreated(Event):
    offer_id: int
    request_id: int


@dataclass(frozen=True)
class OfferCountered(Event):
    offer_id: int
    counter_price: int


@dataclass(frozen=True)
class OfferAccepted(Event):
    offer_id: int
    trip_id: int


@dataclass(frozen=True)
class TripCompleted(Event):
    trip_id: int


@dataclass(frozen=True)
class DriverRegistered(Event):
    driver_id: int


@dataclass(frozen=True)
class DriverVerified(Event):
    driver_id: int


@dataclass(frozen=True)
class PaymentConfirmed(Event):
    payment_id: int


@dataclass(frozen=True)
class ReferralGranted(Event):
    referrer_id: int
    referred_id: int
    days: int


@dataclass(frozen=True)
class UserbotStopped(Event):
    account_id: int
    reason: str


EVENT_TYPES: dict[str, type[Event]] = {
    c.__name__: c for c in (RequestCreated, RequestClosed, OfferCreated, OfferCountered, OfferAccepted, TripCompleted,
                            DriverRegistered, DriverVerified, PaymentConfirmed, ReferralGranted, UserbotStopped)
}

Handler = Callable[[Event], Awaitable[None]]


def encode(event: Event) -> str:
    return json.dumps({"type": event.name, "data": asdict(event)})


def decode(raw: str | bytes) -> Event:
    d = json.loads(raw)
    cls = EVENT_TYPES[d["type"]]
    allowed = {f.name for f in fields(cls)}
    return cls(**{k: v for k, v in d["data"].items() if k in allowed})


class InMemoryBus:
    def __init__(self) -> None:
        self._handlers: dict[type[Event], list[Handler]] = defaultdict(list)
        self.published: list[Event] = []

    def subscribe(self, event_type: type[Event], handler: Handler) -> None:
        self._handlers[event_type].append(handler)

    async def publish(self, event: Event) -> None:
        self.published.append(event)
        await self.dispatch(event)

    async def dispatch(self, event: Event) -> None:
        for h in self._handlers.get(type(event), []):
            try:
                await h(event)
            except Exception:                      # one failing handler must not stop the others
                log.exception("event handler failed for %s", event.name)


class RedisBus(InMemoryBus):
    """Publishes to Redis; `listen()` dispatches events from other processes to local handlers."""

    def __init__(self, redis) -> None:
        super().__init__()
        self.redis = redis

    async def publish(self, event: Event) -> None:
        self.published.append(event)
        await self.redis.publish(CHANNEL, encode(event))

    async def listen(self, stop: asyncio.Event | None = None) -> None:
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(CHANNEL)
        try:
            while not (stop and stop.is_set()):
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if msg and msg.get("type") == "message":
                    try:
                        await self.dispatch(decode(msg["data"]))
                    except (KeyError, ValueError, TypeError):
                        log.warning("dropped malformed event")
        finally:
            await pubsub.unsubscribe(CHANNEL)
