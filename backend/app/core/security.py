import time
import bcrypt
import jwt
from app.core.config import settings

ALGORITHM = "HS256"


class TokenError(Exception):
    pass


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def create_token(sub: str, role: str, ttl_seconds: int | None = None, kind: str = "access") -> str:
    if ttl_seconds is None:
        if kind == "access":
            ttl_seconds = settings.access_token_ttl
        else:
            ttl_seconds = settings.refresh_token_ttl

    now = int(time.time())
    payload = {"sub": sub, "role": role, "type": kind, "iat": now, "exp": now + ttl_seconds}
    return jwt.encode(payload, settings.jwt_secret, ALGORITHM)


def decode_token(token: str, kind: str = "access") -> dict:
    try:
        claims = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM],
                            options={"require": ["sub", "role", "exp"]})
    except jwt.PyJWTError as e:
        raise TokenError(str(e)) from e

    if claims.get("type") != kind:
        raise TokenError(f"expected a {kind} token")
    return claims
