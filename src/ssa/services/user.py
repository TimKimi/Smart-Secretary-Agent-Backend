from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ssa.core.security import create_access_token, hash_password, verify_password
from src.ssa.models.user import TokenBlacklist, User, UserCreate


class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def register(self, data: UserCreate) -> User:
        result = await self.db.execute(select(User).where(User.username == data.username))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already taken")

        result = await self.db.execute(select(User).where(User.email == data.email))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

        user = User(
            username=data.username,
            email=data.email,
            hashed_password=hash_password(data.password),
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def authenticate(self, username: str, password: str) -> str:
        result = await self.db.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()
        if not user or not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )
        return create_access_token({"sub": str(user.id)})

    async def get_by_id(self, user_id: int) -> User:
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return user

    async def get_by_username(self, username: str) -> User | None:
        result = await self.db.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    async def is_token_blacklisted(self, jti: str) -> bool:
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            select(TokenBlacklist).where(
                TokenBlacklist.jti == jti,
                TokenBlacklist.expires_at > now,
            )
        )
        return result.scalar_one_or_none() is not None

    async def blacklist_token(self, jti: str, expires_at: datetime) -> None:
        self.db.add(TokenBlacklist(jti=jti, expires_at=expires_at))
        await self.db.commit()

    async def delete_account(self, user: User) -> None:
        await self.db.delete(user)
        await self.db.commit()
