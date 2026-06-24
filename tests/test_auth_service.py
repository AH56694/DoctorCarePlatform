from backend.app.services.auth import hash_password, verify_password


def test_password_hash_roundtrip():
    password_hash = hash_password("secret123")

    assert password_hash.startswith("pbkdf2_sha256$")
    assert verify_password("secret123", password_hash) is True
    assert verify_password("wrong", password_hash) is False


def test_empty_or_invalid_hash_fails():
    assert verify_password("secret123", "") is False
    assert verify_password("secret123", "not-a-valid-hash") is False
