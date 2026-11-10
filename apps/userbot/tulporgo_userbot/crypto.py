"""Session encryption (decision 8): a Telethon StringSession is stored ONLY as a Fernet token and decrypted only in
memory. The key comes from `Settings.userbot_encryption_key`; an empty or malformed key refuses to work."""
from cryptography.fernet import Fernet, InvalidToken
from tulporgo_core.config import Settings

from .errors import DomainError, NotConfigured


class SessionUnreadable(DomainError):
    status = 500


def generate_key() -> str:
    return Fernet.generate_key().decode()


def _fernet(settings: Settings) -> Fernet:
    key = settings.userbot_encryption_key
    if not key:
        raise NotConfigured("userbot_key_missing", "TULPORGO_USERBOT_ENCRYPTION_KEY is not set")
    try:
        return Fernet(key.encode())
    except (ValueError, TypeError) as e:
        raise NotConfigured("userbot_key_invalid", "TULPORGO_USERBOT_ENCRYPTION_KEY is not a Fernet key") from e


def encrypt_session(settings: Settings, session_string: str) -> str:
    return _fernet(settings).encrypt(session_string.encode()).decode()


def decrypt_session(settings: Settings, token: str) -> str:
    try:
        return _fernet(settings).decrypt(token.encode()).decode()
    except InvalidToken as e:                              # wrong key or tampered value; never echo the token
        raise SessionUnreadable("session_unreadable") from e
