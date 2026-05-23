from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt

from src.ssa.config import settings
from src.ssa.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


class TestPasswordHashing:
    def test_hash_password_returns_different_from_input(self):
        hashed = hash_password("my-secret-password")
        assert hashed != "my-secret-password"
        assert hashed.startswith("$2b$")

    def test_verify_password_success(self):
        hashed = hash_password("correct-horse-battery-staple")
        assert verify_password("correct-horse-battery-staple", hashed) is True

    def test_verify_password_failure(self):
        hashed = hash_password("correct-horse-battery-staple")
        assert verify_password("wrong-password", hashed) is False

    def test_hash_is_salted(self):
        h1 = hash_password("password")
        h2 = hash_password("password")
        assert h1 != h2


class TestJWT:
    def test_create_access_token_contains_claims(self):
        token = create_access_token({"sub": "42"})
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        assert payload["sub"] == "42"
        assert "exp" in payload

    def test_decode_access_token_returns_payload(self):
        token = create_access_token({"sub": "7"})
        payload = decode_access_token(token)
        assert payload["sub"] == "7"

    def test_decode_expired_token_raises(self):
        expire = datetime.now(timezone.utc) - timedelta(minutes=1)
        token = jwt.encode(
            {"sub": "1", "exp": expire},
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )
        with pytest.raises(jwt.ExpiredSignatureError):
            decode_access_token(token)

    def test_decode_token_wrong_secret_raises(self):
        token = jwt.encode({"sub": "1"}, "wrong-secret-key", algorithm=settings.jwt_algorithm)
        with pytest.raises(jwt.JWTError):
            decode_access_token(token)
