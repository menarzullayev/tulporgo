"""Minimal Bot API client for the one thing the Mini App backend sends to Telegram: driver documents.

Documents are forwarded to the private storage chat with `sendDocument` and only the returned `file_id` is kept
(decision 12; files never touch the server disk). Errors never include the request URL, which contains the token.
"""
import httpx
from tulporgo_core.errors import DomainError


class UploadFailed(DomainError):
    status = 502


class TelegramUploader:
    def __init__(self, token: str, base_url: str = "https://api.telegram.org", timeout: float = 30.0,
                 transport: httpx.AsyncBaseTransport | None = None):
        self._token = token
        self._base = base_url.rstrip("/")
        self._timeout = timeout
        self._transport = transport

    async def send_document(self, chat_id: int, filename: str, content: bytes, content_type: str,
                            caption: str = "") -> str:
        """Upload and return the Telegram `file_id`."""
        url = f"{self._base}/bot{self._token}/sendDocument"
        try:
            async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as c:
                res = await c.post(url, data={"chat_id": str(chat_id), "caption": caption[:200]},
                                   files={"document": (filename, content, content_type)})
            body = res.json()
            file_id = body["result"]["document"]["file_id"]
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            raise UploadFailed("upload_failed", "could not store the document") from None
        if not res.is_success or not file_id:
            raise UploadFailed("upload_failed", "could not store the document")
        return file_id
