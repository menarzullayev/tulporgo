"""Userbot-only settings and safety constants. Telegram API credentials come from the environment
(`TULPORGO_TELEGRAM_API_ID`, `TULPORGO_TELEGRAM_API_HASH`), never from the repository."""
from pydantic_settings import BaseSettings, SettingsConfigDict

DEVICE_MODEL = "TulporGo (driver)"
APP_VERSION = "TulporGo userbot"

# Safety floor: even a driver who acknowledged the risk cannot set the interval below this (decision 48 makes the
# default safe and the limit adjustable; a floor only protects the driver's own account from a typo).
ABSOLUTE_MIN_INTERVAL_MINUTES = 5

TICK_SECONDS = 30                 # worker loop; at most ONE post per account per tick spreads sends naturally
LOGIN_TTL_SECONDS = 600           # a pending phone login is dropped after 10 minutes
LOGIN_START_COOLDOWN_SECONDS = 60  # do not ask Telegram for a new code more often than this
MAX_LOGIN_ATTEMPTS = 5            # wrong code / password attempts per pending login
TASHKENT_UTC_OFFSET_HOURS = 5     # "daily cap" counts the driver's local day (Uzbekistan has no DST)


class TelegramApiSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TULPORGO_", env_file=".env", extra="ignore")

    telegram_api_id: int = 0
    telegram_api_hash: str = ""

    @property
    def configured(self) -> bool:
        return bool(self.telegram_api_id and self.telegram_api_hash)
