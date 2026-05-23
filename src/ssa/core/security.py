import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import jwt

from src.ssa.config import settings


def hash_password(password: str) -> str:
    password_bytes = password.encode()
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    plain_bytes = plain_password.encode()
    if len(plain_bytes) > 72:
        plain_bytes = plain_bytes[:72]
    return bcrypt.checkpw(plain_bytes, hashed_password.encode())


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    to_encode.setdefault("jti", str(uuid.uuid4()))
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
