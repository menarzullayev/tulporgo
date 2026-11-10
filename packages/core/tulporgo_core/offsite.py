"""Off-site copy of database backups (decision 58): the newest dump is encrypted ON THIS SERVER and copied to
Cloudflare R2; only the newest `offsite_keep_count` objects stay there (default 1).

The key never leaves Uzbekistan: R2 only ever receives ciphertext. Format "TGB1": streaming AES-256-GCM in 4 MiB chunks
(constant memory for any dump size). Every chunk is authenticated with its index and a "last chunk" flag, so a
tampered, reordered or truncated file is refused on decrypt.

    python -m tulporgo_core.offsite watch            # the `offsite` service: copy each new dump once
    python -m tulporgo_core.offsite upload FILE      # one file now
    python -m tulporgo_core.offsite decrypt IN OUT   # restore path: R2 object -> pg_dump file
    python -m tulporgo_core.offsite keygen           # a new key for TULPORGO_BACKUP_ENCRYPTION_KEY
"""
import argparse
import base64
import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .config import Settings, get_settings

log = logging.getLogger(__name__)

MAGIC = b"TGB1"
CHUNK = 4 * 1024 * 1024
STATE_FILE = "offsite.json"


class OffsiteError(Exception):
    pass


def new_key() -> str:
    return base64.urlsafe_b64encode(AESGCM.generate_key(bit_length=256)).decode()


def parse_key(value: str) -> bytes:
    try:
        raw = base64.urlsafe_b64decode(value.encode())
    except ValueError as e:
        raise OffsiteError("backup key is not base64") from e
    if len(raw) != 32:
        raise OffsiteError("backup key must be 32 bytes (use `python -m tulporgo_core.offsite keygen`)")
    return raw


def _ad(index: int, last: bool) -> bytes:
    return index.to_bytes(4, "big") + (b"\x01" if last else b"\x00")


def encrypt_file(src: Path, dst: Path, key: bytes, chunk: int = CHUNK) -> None:
    aes, prefix = AESGCM(key), os.urandom(8)
    with open(src, "rb") as fi, open(dst, "wb") as fo:
        fo.write(MAGIC + prefix)
        index, block = 0, fi.read(chunk)
        while True:
            following = fi.read(chunk)
            last = not following
            ct = aes.encrypt(prefix + index.to_bytes(4, "big"), block, _ad(index, last))
            fo.write(len(ct).to_bytes(4, "big") + (b"\x01" if last else b"\x00") + ct)
            if last:
                return
            block, index = following, index + 1


def decrypt_file(src: Path, dst: Path, key: bytes) -> None:
    aes = AESGCM(key)
    with open(src, "rb") as fi, open(dst, "wb") as fo:
        head = fi.read(12)
        if len(head) != 12 or head[:4] != MAGIC:
            raise OffsiteError("not a TulporGo encrypted backup")
        prefix, index = head[4:], 0
        while True:
            frame = fi.read(5)
            if len(frame) < 5:
                raise OffsiteError("truncated backup (last chunk missing)")
            size, last = int.from_bytes(frame[:4], "big"), frame[4] == 1
            ct = fi.read(size)
            if len(ct) != size:
                raise OffsiteError("truncated backup")
            try:
                fo.write(aes.decrypt(prefix + index.to_bytes(4, "big"), ct, _ad(index, last)))
            except Exception as e:  # cryptography.exceptions.InvalidTag
                raise OffsiteError("backup is corrupted, tampered with or the key is wrong") from e
            if last:
                if fi.read(1):
                    raise OffsiteError("unexpected data after the last chunk")
                return
            index += 1


class S3Like(Protocol):
    def upload_file(self, Filename: str, Bucket: str, Key: str) -> None: ...
    def list_objects_v2(self, **kw: Any) -> dict: ...
    def delete_object(self, **kw: Any) -> Any: ...


@dataclass
class R2Config:
    endpoint: str
    bucket: str
    access_key_id: str
    secret_access_key: str
    prefix: str
    keep: int
    key: bytes

    @classmethod
    def from_settings(cls, s: Settings) -> "R2Config | None":
        if not (s.r2_endpoint and s.r2_bucket and s.r2_access_key_id and s.r2_secret_access_key
                and s.backup_encryption_key):
            return None
        return cls(s.r2_endpoint, s.r2_bucket, s.r2_access_key_id, s.r2_secret_access_key, s.r2_prefix,
                   max(1, s.offsite_keep_count), parse_key(s.backup_encryption_key))


def r2_client(cfg: R2Config) -> S3Like:
    import boto3
    return boto3.client("s3", endpoint_url=cfg.endpoint, aws_access_key_id=cfg.access_key_id,
                        aws_secret_access_key=cfg.secret_access_key, region_name="auto")


def prune_remote(client: S3Like, cfg: R2Config) -> list[str]:
    objs = client.list_objects_v2(Bucket=cfg.bucket, Prefix=cfg.prefix).get("Contents", [])
    objs.sort(key=lambda o: o["LastModified"], reverse=True)
    gone = [o["Key"] for o in objs[cfg.keep:]]
    for k in gone:
        client.delete_object(Bucket=cfg.bucket, Key=k)
    return gone


def _state(state_dir: Path) -> dict:
    try:
        return json.loads((state_dir / STATE_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"uploaded": []}


def upload(client: S3Like, cfg: R2Config, dump: Path, work_dir: Path) -> str:
    enc = work_dir / (dump.name + ".enc.part")
    try:
        encrypt_file(dump, enc, cfg.key)
        key = cfg.prefix + dump.name + ".enc"
        client.upload_file(Filename=str(enc), Bucket=cfg.bucket, Key=key)
    finally:
        enc.unlink(missing_ok=True)
    prune_remote(client, cfg)
    return key


def process_once(backups: Path, state_dir: Path, cfg: R2Config | None, client: S3Like | None) -> str | None:
    """Copy the newest dump if it has not been copied yet. Returns the R2 key, or None when there is nothing to do."""
    if cfg is None or client is None:
        return None
    dumps = sorted(backups.glob("tulporgo-*.dump"), key=lambda p: p.stat().st_mtime)
    if not dumps:
        return None
    newest, state = dumps[-1], _state(state_dir)
    if newest.name in state["uploaded"]:
        return None
    key = upload(client, cfg, newest, state_dir)
    state["uploaded"] = (state["uploaded"] + [newest.name])[-50:]
    (state_dir / STATE_FILE).write_text(json.dumps(state), encoding="utf-8")
    log.info("offsite: %s -> r2://%s/%s", newest.name, cfg.bucket, key)
    return key


def watch(backups: Path, state_dir: Path, settings: Settings, interval: int = 600) -> None:
    cfg = R2Config.from_settings(settings)
    if cfg is None:
        log.warning("offsite: R2 or TULPORGO_BACKUP_ENCRYPTION_KEY not configured — nothing is copied")
    client = r2_client(cfg) if cfg else None
    while True:
        try:
            process_once(backups, state_dir, cfg, client)
        except Exception:  # noqa: BLE001 — retry on the next tick; a failed copy must not stop the service
            log.exception("offsite: copy failed, will retry")
        time.sleep(interval)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    p = argparse.ArgumentParser(prog="tulporgo_core.offsite")
    sub = p.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("watch")
    w.add_argument("--backups", default="/backups")
    w.add_argument("--state", default="/app/state")
    u = sub.add_parser("upload")
    u.add_argument("file")
    u.add_argument("--state", default="/app/state")
    d = sub.add_parser("decrypt")
    d.add_argument("src")
    d.add_argument("dst")
    sub.add_parser("keygen")
    a = p.parse_args(argv)
    if a.cmd == "keygen":
        print(new_key())
        return 0
    settings = get_settings()
    if a.cmd == "decrypt":
        decrypt_file(Path(a.src), Path(a.dst), parse_key(settings.backup_encryption_key))
        print(f"decrypted: {a.dst}")
        return 0
    if a.cmd == "upload":
        cfg = R2Config.from_settings(settings)
        if cfg is None:
            print("offsite: not configured", file=sys.stderr)
            return 2
        print(upload(r2_client(cfg), cfg, Path(a.file), Path(a.state)))
        return 0
    watch(Path(a.backups), Path(a.state), settings)
    return 0


if __name__ == "__main__":
    sys.exit(main())
