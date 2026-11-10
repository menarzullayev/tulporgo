"""Bot-only settings (kept out of tulporgo_core.config so the shared core stays untouched)."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class BotExtra(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TULPORGO_", env_file=".env", extra="ignore")

    drivers_group_id: int | None = None        # closed drivers group: member tags "Tasdiqlangan" / "Elchi" (Bot API 9.5)
    chat_username: str = "tulporgo_chat"       # public Q&A group (decision 27)
    rate_per_second: float = 25.0              # Telegram allows ~30 msg/s to different chats; keep headroom
    expire_every_seconds: int = 60
    tags_every_seconds: int = 1800
    report_weekday: int = 0                    # Monday
    report_hour: int = 9                       # 09:00 Asia/Tashkent
    # Optional Telegram features: OFF until the owner approves the UX (CLAUDE.md "Telegram ishlari", rule 4).
    trip_topics: bool = False                  # one topic per trip in each party's private chat (Bot API 9.3; needs topics enabled in BotFather)
    ephemeral_group: bool = False              # group commands + stale group buttons answered ephemerally (Bot API 10.2)
    widgets: bool = False                      # trip-status HTML widget in private chats (Bot API 10.4; raw sendWidget)


def get_extra() -> BotExtra:
    return BotExtra()
