from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.security import hash_password, verify_password
from app.models.device import Device
from app.models.filter import Filter
from app.models.user import User
from app.schemas.user import UpdateProfileRequest, UserResponse

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> UserResponse:
    filter_count = await db.scalar(select(func.count()).where(Filter.user_id == user.id)) or 0
    device_count = await db.scalar(select(func.count()).where(Device.user_id == user.id)) or 0
    data = UserResponse.model_validate(user)
    data.filter_count = filter_count
    data.device_count = device_count
    return data


@router.patch("/me", response_model=UserResponse)
async def update_me(
    body: UpdateProfileRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    if body.timezone is not None:
        user.timezone = body.timezone

    if body.new_password is not None:
        if not body.current_password:
            raise HTTPException(status_code=422, detail="current_password required to change password")
        if not verify_password(body.current_password, user.hashed_password):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
        user.hashed_password = hash_password(body.new_password)

    await db.commit()
    await db.refresh(user)

    filter_count = await db.scalar(select(func.count()).where(Filter.user_id == user.id)) or 0
    device_count = await db.scalar(select(func.count()).where(Device.user_id == user.id)) or 0
    data = UserResponse.model_validate(user)
    data.filter_count = filter_count
    data.device_count = device_count
    return data


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> None:
    await db.delete(user)
    await db.commit()
