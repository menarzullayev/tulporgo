"""Runtime settings, read from the environment (and an optional `.env`), never from the repository."""
from datetime import date

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TULPORGO_", env_file=".env", extra="ignore",
                                      env_ignore_empty=True)

    # storage — PostgreSQL in production, SQLite for development/tests, MySQL optional (decision 46)
    database_url: str = "sqlite+aiosqlite:///./tulporgo.db"
    redis_url: str | None = None

    # Telegram
    bot_token: str = ""
    bot_username: str = "tulporgobot"
    owner_chat_id: int | None = None
    admin_ids: list[int] = Field(default_factory=list)
    channel_username: str = "tulporgo"
    miniapp_url: str = "https://tulporgo.uz/app"
    storage_chat_id: int | None = None              # private chat where uploaded documents are stored as file ids

    # "Login with Telegram" for the site opened outside Telegram (OpenID Connect). OFF while the secret is empty;
    # the secret comes from BotFather -> Bot Settings -> Login Widget. The client id is the bot's numeric id.
    login_client_secret: str = ""
    web_session_hours: int = 72

    # product rules
    free_period_until: date | None = None          # decision 44: everyone free until this date (inclusive)
    trial_days: int = 7                            # decision 10
    referral_bonus_days: int = 7                   # decision 52
    request_ttl_minutes: int = 120
    offer_ttl_minutes: int = 30

    # userbot (decision 8 / 48)
    userbot_encryption_key: str = ""               # Fernet key; sessions are stored encrypted
    userbot_min_interval_minutes: int = 45
    userbot_jitter_minutes: int = 15

    # payments (decision 44) — sandbox keys in development, live keys only after a merchant contract
    stars_rate_uzs: int = 165                       # so'm per Telegram Star — OWNER TO CONFIRM before live Stars
    p2p_card_number: str = ""
    p2p_card_holder: str = ""
    click_service_id: str = ""
    click_merchant_id: str = ""
    click_secret_key: str = ""
    payme_merchant_id: str = ""
    payme_key: str = ""
    payme_test_mode: bool = True


def get_settings() -> Settings:
    return Settings()
