import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt

from backend.app.core.config import settings

HASH_NAME = "sha256"
ITERATIONS = 210_000
SALT_BYTES = 16
JWT_ALGORITHM = "HS256"


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


def issue_access_token(user_id: str) -> str:
    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=settings.auth_token_expire_minutes)
    return jwt.encode(
        {
            "sub": user_id,
            "iss": settings.auth_issuer,
            "type": "access",
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
            "jti": str(uuid4()),
        },
        settings.auth_secret_key,
        algorithm=JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(
            token,
            settings.auth_secret_key,
            algorithms=[JWT_ALGORITHM],
            issuer=settings.auth_issuer,
            options={"require": ["exp", "iat", "sub", "jti"]},
        )
    except jwt.InvalidTokenError:
        return None
    if payload.get("type") != "access":
        return None
    subject = payload.get("sub")
    return str(subject) if subject else None
