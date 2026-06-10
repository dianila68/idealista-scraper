from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.device import Device
from app.models.user import User
from app.schemas.device import DeviceRegister, DeviceResponse

router = APIRouter()


@router.post("/register", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
async def register_device(
    body: DeviceRegister,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Device).where(Device.fcm_token == body.fcm_token))
    existing = result.scalar_one_or_none()
    if existing:
        # Token already registered — re-associate with current user if needed
        if existing.user_id != user.id:
            existing.user_id = user.id
            await db.commit()
            await db.refresh(existing)
        return DeviceResponse.model_validate(existing)

    device = Device(user_id=user.id, fcm_token=body.fcm_token, platform=body.platform)
    db.add(device)
    await db.commit()
    await db.refresh(device)
    return DeviceResponse.model_validate(device)


@router.delete("/{fcm_token}", status_code=status.HTTP_204_NO_CONTENT)
async def unregister_device(
    fcm_token: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Device).where(Device.fcm_token == fcm_token, Device.user_id == user.id)
    )
    device = result.scalar_one_or_none()
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    await db.delete(device)
    await db.commit()
