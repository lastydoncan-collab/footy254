import hashlib
import hmac
import os

os.environ.setdefault("JWT_SECRET_KEY", "x" * 48)

from security import totp  # noqa: E402
from security.secret_box import seal, unseal  # noqa: E402


def test_totp_rfc6238_vector():
    import base64

    secret = base64.b32encode(b"12345678901234567890").decode().rstrip("=")
    assert totp._code_for_step(secret, 59 // 30) == "287082"


def test_totp_single_use_and_drift():
    secret = totp.new_secret()
    now = 1_700_000_000
    step = totp.current_step(now)
    code = totp._code_for_step(secret, step)
    assert totp.verify(secret, code, 0, now) == step
    assert totp.verify(secret, code, step, now) is None  # replay rejected
    previous = totp._code_for_step(secret, step - 1)
    assert totp.verify(secret, previous, 0, now) == step - 1  # one step of drift
    assert totp.verify(secret, "000000", 0, now) in (None, step)  # wrong code


def test_recovery_codes_hash_normalisation():
    code = totp.new_recovery_codes(1)[0]
    assert totp.hash_recovery_code(code) == totp.hash_recovery_code(code.lower().replace("-", " "))


def test_secret_box_roundtrip():
    assert unseal(seal("ABC123")) == "ABC123"
    assert unseal("garbage") is None


def test_paystack_signature(monkeypatch):
    from services import card_service

    monkeypatch.setattr(card_service, "PAYSTACK_SECRET_KEY", "sk_test_abc")
    body = b'{"event":"charge.success"}'
    good = hmac.new(b"sk_test_abc", body, hashlib.sha512).hexdigest()
    assert card_service.valid_signature(body, good)
    assert not card_service.valid_signature(body, "bad")
    assert not card_service.valid_signature(body, None)
