#app/schemas/schemas.py
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class UserIdResponse(BaseModel):
    user_id: str
    created_at: datetime
    is_active: bool

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "USR-550e8400-e29b-41d4-a716-446655440000",
                "created_at": "2024-01-01T00:00:00",
                "is_active": True,
            }
        }


class GenerateUserIdResponse(BaseModel):
    success: bool
    message: str
    data: Optional[UserIdResponse] = None


class AllUserIdsResponse(BaseModel):
    success: bool
    total: int
    data: list[UserIdResponse]