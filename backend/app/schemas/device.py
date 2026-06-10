from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class DeviceRegister(BaseModel):
    fcm_token: str = Field(..., min_length=1, max_length=512)
    platform: Literal["android", "ios"] = "android"


class DeviceResponse(BaseModel):
    id: UUID
    fcm_token: str
    platform: str
    created_at: datetime

    model_config = {"from_attributes": True}
