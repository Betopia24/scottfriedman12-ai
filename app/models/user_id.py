#app/models/user_id.py
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class UserIdModel(BaseModel):
    user_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = True

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "user_id": "USR-A1B2C3D4",
                "created_at": "2024-01-01T00:00:00",
                "is_active": True,
            }
        }