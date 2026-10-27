import pytest
from app.core.security import hash_password, verify_password, create_token, decode_token, TokenError

def test_password_roundtrip():
    h = hash_password("secret")
    assert verify_password("secret", h) and not verify_password("x", h)

def test_verify_garbage_hash_is_false():
    assert not verify_password("secret", "not-a-bcrypt-hash")

def test_token_roundtrip_and_role():
    tok = create_token("u1", "STUDENT", ttl_seconds=60)
    claims = decode_token(tok)
    assert claims["sub"] == "u1" and claims["role"] == "STUDENT" and claims["type"] == "access"

def test_expired_token_rejected():
    tok = create_token("u1", "STUDENT", ttl_seconds=-1)
    with pytest.raises(TokenError):
        decode_token(tok)

def test_forged_token_rejected():
    with pytest.raises(TokenError):
        decode_token("not.a.jwt")

def test_token_signed_with_other_secret_rejected():
    import jwt
    forged = jwt.encode({"sub": "u1", "role": "SUPER_ADMIN", "type": "access", "exp": 9999999999}, "attacker-controlled-secret-32-bytes-long", "HS256")
    with pytest.raises(TokenError):
        decode_token(forged)

def test_refresh_token_cannot_be_used_as_access():
    tok = create_token("u1", "STUDENT", ttl_seconds=60, kind="refresh")
    with pytest.raises(TokenError):
        decode_token(tok)
    assert decode_token(tok, kind="refresh")["sub"] == "u1"
