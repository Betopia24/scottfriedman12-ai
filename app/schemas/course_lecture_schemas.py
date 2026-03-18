# app/schemas/course_lecture_schemas.py
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from enum import Enum


class VoiceStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class VoicePartData(BaseModel):
    part_key: str
    part_label: str
    audio_url: Optional[str] = None
    duration_seconds: Optional[float] = None
    status: VoiceStatus = VoiceStatus.PENDING


class VoiceData(BaseModel):
    voice_id: str
    generated_at: Optional[str] = None
    audio_url: Optional[str] = None
    duration_seconds: Optional[float] = None
    audio_parts: List[VoicePartData] = Field(default_factory=list)
    total_parts: int = 0
    status: VoiceStatus = VoiceStatus.PENDING


class ResourceItem(BaseModel):
    title: str
    type: str
    description: Optional[str] = None


class StudyTopic(BaseModel):
    topic_name: str
    topic_wise_study_data: Dict[str, Any]


class ModuleData(BaseModel):
    module_number: int
    title: str
    introduction: str
    resources: List[ResourceItem] = Field(default_factory=list)
    study_topics: List[StudyTopic]
    voice: VoiceData


class LectureVariables(BaseModel):
    unique_id: str
    unique_session_id: str
    generated_course_name: str


class LectureApiResponse(BaseModel):
    variables: LectureVariables
    modules: List[ModuleData]


class GenerateLectureResponse(BaseModel):
    success: bool
    message: str
    api_response: LectureApiResponse


# ── Input ──────────────────────────────────────────────────────────────────────
class GenerateLectureInput(BaseModel):
    unique_id: str
    unique_session_id: str

    class Config:
        json_schema_extra = {
            "example": {
                "unique_id": "USR-A1B2C3D4",
                "unique_session_id": "SES-ABCD12345678",
            }
        }


# ── Retrieve ───────────────────────────────────────────────────────────────────
class GetLectureResponse(BaseModel):
    success: bool
    message: str
    api_response: Optional[LectureApiResponse] = None


# ── Single Module Generation ───────────────────────────────────────────────────
class GenerateSingleModuleInput(BaseModel):
    unique_session_id: str
    module_number: int

    class Config:
        json_schema_extra = {
            "example": {
                "unique_session_id": "SES-ABCD12345678",
                "module_number": 1,
            }
        }


class GenerateSingleModuleResponse(BaseModel):
    success: bool
    message: str
    module: ModuleData
    unique_session_id: str
    module_number: int
    total_modules: int