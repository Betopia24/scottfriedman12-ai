# app/models/course_lecture.py
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum
from pydantic import BaseModel, Field


# ── Enums ──────────────────────────────────────────────────────────────────────

class VoiceStatus(str, Enum):
    PENDING    = "pending"
    PROCESSING = "processing"
    COMPLETED  = "completed"
    FAILED     = "failed"


# ── Sub-document models ────────────────────────────────────────────────────────

class VoiceModel(BaseModel):
    """
    Stores TTS audio metadata for a single module.
    Audio files are saved at: static/audio/{session_id}/module_{n}.mp3
    """
    voice_id: str = Field(..., description="Unique voice job ID e.g. VOX-XXXXXXXXXX")
    generated_at: Optional[str] = Field(None, description="ISO timestamp of TTS generation")
    audio_url: Optional[str] = Field(None, description="Relative URL path to the .mp3 file")
    duration_seconds: Optional[float] = Field(None, description="Estimated audio duration in seconds")
    status: VoiceStatus = Field(default=VoiceStatus.PENDING, description="TTS generation status")


class StudyTopicModel(BaseModel):
    """
    A single study topic within a module.
    topic_wise_study_data contains GPT-generated rich content:
    summary, key_concepts, detailed_explanation, examples, practice_questions, further_reading
    """
    topic_name: str = Field(..., description="Name of the study topic")
    topic_wise_study_data: Dict[str, Any] = Field(
        ...,
        description=(
            "AI-generated topic content including: summary, key_concepts, "
            "detailed_explanation, examples, practice_questions, further_reading"
        )
    )


class ModuleModel(BaseModel):
    """
    A single course module containing AI-generated course details,
    study topics, and TTS voice narration metadata.
    course_details contains: module_title, module_description, learning_objectives,
    prerequisites, estimated_classes, difficulty_level, key_skills, assessment_info
    """
    module_number: int = Field(..., ge=1, description="Sequential module number starting from 1")
    course_details: Dict[str, Any] = Field(
        ...,
        description=(
            "AI-generated module metadata including: module_title, module_description, "
            "learning_objectives, prerequisites, estimated_classes, "
            "difficulty_level, key_skills, assessment_info"
        )
    )
    study_topics: List[StudyTopicModel] = Field(
        ...,
        description="List of study topics with detailed AI-generated content"
    )
    voice: VoiceModel = Field(..., description="TTS voice narration metadata for this module")


# ── Top-level collection document model ───────────────────────────────────────

class CourseLectureModel(BaseModel):
    """
    Represents a document in the 'Course_lecture_generator' collection.
    Linked to course_name_generator via unique_session_id and unique_id.
    """
    unique_id: str = Field(..., description="Reference to User_id table — user_id")
    unique_session_id: str = Field(..., description="Reference to course_name_generator — unique_session_id")
    generated_course_name: str = Field(..., description="AI-generated course title from course_name_generator")
    modules: List[ModuleModel] = Field(..., description="All generated course modules")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        use_enum_values = True
        json_schema_extra = {
            "example": {
                "unique_id": "USR-A1B2C3D4",
                "unique_session_id": "SES-ABCD12345678",
                "generated_course_name": "Mastering Advanced Mathematics: A Comprehensive Journey",
                "modules": [
                    {
                        "module_number": 1,
                        "course_details": {
                            "module_title": "Foundations of Algebra",
                            "module_description": "Introduction to core algebraic concepts.",
                            "learning_objectives": ["Understand variables", "Solve linear equations"],
                            "prerequisites": ["None"],
                            "estimated_classes": 4,
                            "difficulty_level": "Beginner",
                            "key_skills": ["Equation solving", "Variable manipulation"],
                            "assessment_info": {
                                "quiz_count": 3,
                                "quiz_questions_per_quiz": 7,
                                "mastery_required": 80.0
                            }
                        },
                        "study_topics": [
                            {
                                "topic_name": "Introduction to Variables",
                                "topic_wise_study_data": {
                                    "summary": "Variables are symbols used to represent unknown values.",
                                    "key_concepts": ["Variable", "Constant", "Expression"],
                                    "detailed_explanation": "A variable is a letter that stands in for an unknown number...",
                                    "examples": ["x + 5 = 10", "2y = 8"],
                                    "practice_questions": [
                                        {"question": "Solve for x: x + 3 = 7", "answer": "x = 4"}
                                    ],
                                    "further_reading": ["Algebra I Textbook Chapter 1"]
                                }
                            }
                        ],
                        "voice": {
                            "voice_id": "VOX-AB12CD34EF",
                            "generated_at": "2024-01-01T00:00:00+00:00",
                            "audio_url": "/audio/SES-ABCD12345678/module_1.mp3",
                            "duration_seconds": 142.5,
                            "status": "completed"
                        }
                    }
                ],
                "created_at": "2024-01-01T00:00:00"
            }
        }