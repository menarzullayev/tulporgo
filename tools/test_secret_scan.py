import base64

from secret_scan import findings, private_values

FAKE_TOKEN = "1234567890:" + "A" * 35                       # shape of a bot token, not a real one


def test_each_kind_is_caught():
    # negative: every pattern must fire on a sample
    text = "\n".join([
        f"TOKEN={FAKE_TOKEN}",
        "TELEGRAM_API_HASH=" + "0123456789abcdef" * 2,
        "1" + "B" * 360,
        "phone +99" + "8 93 418 72 05",                     # samples are assembled at run time so this file
        "-----BEGIN RSA " + "PRIVATE KEY-----",              # itself does not trip the scan
        '{"access_' + 'hash": 296952612360151391}',
    ])
    kinds = {k for k, _ in findings(text)}
    assert kinds == {"telegram bot token", "telegram api hash", "telethon/gramjs session string",
                     "uzbek phone number", "private key", "access hash"}


def test_line_numbers():
    assert findings(f"ok\nok\nx {FAKE_TOKEN}") == [("telegram bot token", 3)]


def test_embedded_images_are_not_findings():
    blob = base64.b64encode(bytes(range(256)) * 20).decode()
    assert findings(f'<img src="data:image/png;base64,1{blob}">') == []


def test_placeholder_numbers_allowed_real_looking_flagged():
    assert findings("example: +99" + "8 90 123 45 67, 99" + "8901234567, +99" + "8 99 999 99 99") == []
    # negative: a number that is not an obvious placeholder is still personal data
    assert findings("call +99" + "8 93 418 72 05") == [("uzbek phone number", 1)]


def test_clean_text_passes():
    assert findings("TulporGo — taksini Telegram'dan chaqirish. chat id -1004318662356, user 1808327630") == []


def test_owner_values_from_secrets_are_caught(tmp_path):
    (tmp_path / "operator.env").write_text(
        "# Full name\nTULPORGO_OPERATOR_NAME=Testov Test Testovich\nTULPORGO_OPERATOR_ADDRESS=\n", encoding="utf-8")
    (tmp_path / "r2.env").write_text(
        "TULPORGO_R2_BUCKET=tulporgo-backup\nTULPORGO_R2_SECRET_ACCESS_KEY=abcdef0123456789\n", encoding="utf-8")
    private = private_values(tmp_path)
    assert set(private) == {"testov test testovich", "abcdef0123456789"}   # bucket name is not secret, empty is skipped
    found = findings("ok\nOperator: TESTOV Test Testovich\nkey abcdef0123456789\n", private)
    assert found == [("value of TULPORGO_OPERATOR_NAME from .secrets/operator.env", 2),
                     ("value of TULPORGO_R2_SECRET_ACCESS_KEY from .secrets/r2.env", 3)]
    assert findings("Operator: `[ega: F.I.Sh.]`", private) == []           # negative: the placeholder is fine


def test_no_secrets_dir_means_no_private_values(tmp_path):
    assert private_values(tmp_path / "missing") == {}
