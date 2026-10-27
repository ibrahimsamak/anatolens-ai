import time
from typing import Literal
import bcrypt
import jwt
from app.core.config import settings

_ALG = "HS256"
TokenKind = Literal["access", "refresh"]

class TokenError(Exception):
    pass

def hash_password(p: str) -> str:
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()

def verify_password(p: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(p.encode(), h.encode())
    except ValueError:
        return False

def create_token(sub: str, role: str, ttl_seconds: int | None = None, kind: TokenKind = "access") -> str:
    if ttl_seconds is None:
        ttl_seconds = settings.access_token_ttl if kind == "access" else settings.refresh_token_ttl
    now = int(time.time())
    return jwt.encode({"sub": sub, "role": role, "type": kind, "iat": now, "exp": now + ttl_seconds},
                      settings.jwt_secret, _ALG)

def decode_token(token: str, kind: TokenKind = "access") -> dict:
    try:
        claims = jwt.decode(token, settings.jwt_secret, algorithms=[_ALG], options={"require": ["sub", "role", "exp"]})
    except jwt.PyJWTError as e:
        raise TokenError(str(e)) from e
    if claims.get("type") != kind:
        raise TokenError(f"expected a {kind} token")
    return claims
