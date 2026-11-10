"""Decision 58: dumps are encrypted here and only ciphertext goes to R2; one copy is kept; nothing is re-uploaded."""
import os
from datetime import datetime, timedelta

import pytest
from tulporgo_core import offsite
from tulporgo_core.config import Settings

SECRET = b"PG-DUMP passport AA1234567 +998901234567 "


@pytest.fixture
def key():
    return offsite.parse_key(offsite.new_key())


@pytest.mark.parametrize("size", [0, 1, 99, 100, 101, 1000])
def test_round_trip_any_size(tmp_path, key, size):
    src, enc, out = tmp_path / "a.dump", tmp_path / "a.enc", tmp_path / "a.out"
    data = (SECRET * 40)[:size]
    src.write_bytes(data)
    offsite.encrypt_file(src, enc, key, chunk=100)                 # small chunks: many frames
    offsite.decrypt_file(enc, out, key)
    assert out.read_bytes() == data


def test_ciphertext_hides_the_content(tmp_path, key):
    src, enc = tmp_path / "a.dump", tmp_path / "a.enc"
    src.write_bytes(SECRET * 100)
    offsite.encrypt_file(src, enc, key)
    blob = enc.read_bytes()
    assert b"passport" not in blob and b"+998" not in blob and blob.startswith(offsite.MAGIC)


def _enc(tmp_path, key, data=SECRET * 30):
    src, enc = tmp_path / "a.dump", tmp_path / "a.enc"
    src.write_bytes(data)
    offsite.encrypt_file(src, enc, key, chunk=100)
    return enc


def test_tampered_byte_is_refused(tmp_path, key):
    enc = _enc(tmp_path, key)
    b = bytearray(enc.read_bytes())
    b[40] ^= 1
    enc.write_bytes(bytes(b))
    with pytest.raises(offsite.OffsiteError):
        offsite.decrypt_file(enc, tmp_path / "o", key)


def test_truncated_file_is_refused(tmp_path, key):
    enc = _enc(tmp_path, key)
    enc.write_bytes(enc.read_bytes()[:-50])                         # cut inside the last frame
    with pytest.raises(offsite.OffsiteError):
        offsite.decrypt_file(enc, tmp_path / "o", key)


def test_dropped_last_chunk_is_refused(tmp_path, key):
    # negative: whole frames removed at the end still fail (the last-chunk flag is authenticated)
    enc = _enc(tmp_path, key)
    blob = enc.read_bytes()
    first = 12 + 5 + int.from_bytes(blob[12:16], "big")
    enc.write_bytes(blob[:first])
    with pytest.raises(offsite.OffsiteError, match="truncated"):
        offsite.decrypt_file(enc, tmp_path / "o", key)


def test_wrong_key_is_refused(tmp_path, key):
    enc = _enc(tmp_path, key)
    with pytest.raises(offsite.OffsiteError):
        offsite.decrypt_file(enc, tmp_path / "o", offsite.parse_key(offsite.new_key()))


def test_bad_keys_are_rejected():
    with pytest.raises(offsite.OffsiteError):
        offsite.parse_key("c2hvcnQ=")                               # 5 bytes


class FakeR2:
    def __init__(self):
        self.objects: dict[str, tuple[bytes, datetime]] = {}
        self.t = datetime(2026, 11, 1)

    def upload_file(self, Filename, Bucket, Key):
        self.t += timedelta(minutes=1)
        self.objects[Key] = (open(Filename, "rb").read(), self.t)

    def list_objects_v2(self, **kw):
        return {"Contents": [{"Key": k, "LastModified": t} for k, (_, t) in self.objects.items()
                             if k.startswith(kw["Prefix"])]}

    def delete_object(self, **kw):
        self.objects.pop(kw["Key"])


def _cfg(key, keep=1):
    return offsite.R2Config("https://x.r2.cloudflarestorage.com", "b", "id", "secret", "tulporgo/", keep, key)


def _dump(d, name, data=SECRET, age=0):
    p = d / name
    p.write_bytes(data)
    t = 1_800_000_000 - age
    os.utime(p, (t, t))
    return p


def test_newest_dump_copied_once_and_only_one_copy_kept(tmp_path, key):
    backups, state = tmp_path / "b", tmp_path / "s"
    backups.mkdir(), state.mkdir()
    r2, cfg = FakeR2(), _cfg(key)
    _dump(backups, "tulporgo-1.dump", age=100)
    _dump(backups, "tulporgo-2.dump", age=10)
    assert offsite.process_once(backups, state, cfg, r2) == "tulporgo/tulporgo-2.dump.enc"
    assert offsite.process_once(backups, state, cfg, r2) is None       # negative: never uploaded twice
    _dump(backups, "tulporgo-3.dump", age=1)
    offsite.process_once(backups, state, cfg, r2)
    assert list(r2.objects) == ["tulporgo/tulporgo-3.dump.enc"]       # decision 58: one copy
    blob = r2.objects["tulporgo/tulporgo-3.dump.enc"][0]
    assert SECRET not in blob                                          # only ciphertext left the server
    out_enc, out = tmp_path / "r.enc", tmp_path / "r.dump"
    out_enc.write_bytes(blob)
    offsite.decrypt_file(out_enc, out, key)
    assert out.read_bytes() == SECRET
    assert not list(state.glob("*.part"))                              # no plaintext/ciphertext left behind


def test_not_configured_does_nothing(tmp_path):
    backups = tmp_path / "b"
    backups.mkdir()
    _dump(backups, "tulporgo-1.dump")
    assert offsite.R2Config.from_settings(Settings.model_validate({})) is None
    assert offsite.process_once(backups, tmp_path, None, None) is None


def test_config_needs_the_key_too():
    s = Settings.model_validate({"r2_endpoint": "https://x", "r2_bucket": "b", "r2_access_key_id": "i",
                                 "r2_secret_access_key": "s"})
    assert offsite.R2Config.from_settings(s) is None                   # negative: never upload unencrypted


def test_upload_failure_leaves_no_temp_file(tmp_path, key):
    class Broken(FakeR2):
        def upload_file(self, **kw):
            raise ConnectionError("network")
    backups, state = tmp_path / "b", tmp_path / "s"
    backups.mkdir(), state.mkdir()
    _dump(backups, "tulporgo-1.dump")
    with pytest.raises(ConnectionError):
        offsite.process_once(backups, state, _cfg(key), Broken())
    assert not list(state.iterdir())                                   # not marked as uploaded, no leftovers
