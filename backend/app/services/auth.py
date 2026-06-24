import hashlib
import secrets

HASH_NAME = "sha256"
ITERATIONS = 210_000
SALT_BYTES = 16


def hash_password(password: str) -> str:
    salt = secrets.token_hex(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        HASH_NAME,
        password.encode("utf-8"),
        bytes.fromhex(salt),
        ITERATIONS,
    ).hex()
    return f"pbkdf2_{HASH_NAME}${ITERATIONS}${salt}${digest}"


def verify_password(password: str, password_hash: str) -> bool:
    if not password_hash:
        return False

    try:
        algorithm, iterations, salt, expected = password_hash.split("$", 3)
        hash_name = algorithm.removeprefix("pbkdf2_")
        computed = hashlib.pbkdf2_hmac(
            hash_name,
            password.encode("utf-8"),
            bytes.fromhex(salt),
            int(iterations),
        ).hex()
    except (TypeError, ValueError):
        return False

    return secrets.compare_digest(computed, expected)
