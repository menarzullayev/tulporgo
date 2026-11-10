"""At most one createNewStickerSet attempt per set within a cooldown window.

Telegram answered every Reactions creation with 429 retry_after=301 (MUAMMOLAR #26), and more attempts
can only extend the limit. Two runners (a scheduled task and a manual run) must not both attempt, so
every attempt is recorded *before* the API call in create_attempts.json, and a claim is refused while
the last attempt for that set is younger than the cooldown.

Fails closed: an unreadable state file or a lock held by another process refuses the claim.
TG_FORCE_CREATE=1 overrides the cooldown (not the lock).
"""
import json, os, time
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "create_attempts.json")
COOLDOWN_H = float(os.environ.get("TG_CREATE_COOLDOWN_H", "20"))
STALE_LOCK_S = 120


class Refused(Exception):
    pass


def _lock(path):
    lock = path + ".lock"
    try:
        if time.time() - os.path.getmtime(lock) > STALE_LOCK_S:
            os.remove(lock)
    except OSError:
        pass
    try:
        return os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY), lock
    except FileExistsError:
        raise Refused(f"another create attempt holds {lock}")


def claim(name, now=None, path=STATE, cooldown_h=None, force=None):
    """Record an attempt for `name` and return it, or raise Refused if one is too recent."""
    now = now or datetime.now(timezone.utc).astimezone()
    cooldown = timedelta(hours=COOLDOWN_H if cooldown_h is None else cooldown_h)
    force = os.environ.get("TG_FORCE_CREATE") == "1" if force is None else force
    fd, lock = _lock(path)
    try:
        state = {}
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    state = json.load(f)
                assert isinstance(state, dict)
            except (ValueError, AssertionError) as e:
                raise Refused(f"{path} is unreadable ({e}); fix it by hand before another attempt")
        history = state.get(name, [])
        if history and not force:
            last = datetime.fromisoformat(history[-1])
            if now - last < cooldown:
                raise Refused(f"last {name} attempt {history[-1]}; next allowed after {(last + cooldown).isoformat(timespec='minutes')}"
                              " (TG_FORCE_CREATE=1 overrides)")
        state[name] = history + [now.isoformat(timespec="seconds")]
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=1, ensure_ascii=False)
        os.replace(tmp, path)
        return state[name][-1]
    finally:
        os.close(fd)
        os.remove(lock)
