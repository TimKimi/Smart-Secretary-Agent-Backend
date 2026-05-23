from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from src.ssa.core.security import decode_access_token
from src.ssa.db.session import get_db
from src.ssa.models.user import Token, UserCreate, UserLogin, UserResponse
from src.ssa.services.user import UserService

router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)
):
    try:
        payload = decode_access_token(token)
        user_id = int(payload.get("sub"))
    except (JWTError, ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        )

    jti = payload.get("jti")
    service = UserService(db)
    if jti and await service.is_token_blacklisted(jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
        )

    return await service.get_by_id(user_id)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(data: UserCreate, db: AsyncSession = Depends(get_db)):
    service = UserService(db)
    return await service.register(data)


@router.post("/login", response_model=Token)
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    service = UserService(db)
    access_token = await service.authenticate(data.username, data.password)
    return Token(access_token=access_token)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user=Depends(get_current_user)):
    return current_user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    payload = decode_access_token(token)
    jti = payload.get("jti")
    if jti:
        expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        service = UserService(db)
        await service.blacklist_token(jti, expires_at)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    payload = decode_access_token(token)
    jti = payload.get("jti")
    service = UserService(db)
    if jti:
        expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        await service.blacklist_token(jti, expires_at)
    await service.delete_account(current_user)
