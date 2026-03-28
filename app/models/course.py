# app/models/course.py
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class CourseModel(BaseModel):
    unique_session_id: str
    unique_user_id: str
    course_name: str
    subject: str
    target_grade_level: str
    course_length: str
    semester_count: int
    diagnostic_test_before_course: bool
    retesting_allowed: bool
    retesting_count: int
    quizzes_per_module: int
    midterm_examination: bool
    final_examination: bool
    total_quiz_questions: int
    mastery_requirement: float
    total_modules: int
    estimated_duration_min_per_class: int
    generated_course_name: str
    knowledge_bases: Optional[List[str]] = None
    user_instration: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "unique_session_id": "SES-A1B2C3D4",
                "unique_user_id": "USR-A1B2C3D4",
                "course_name": "Advanced Mathematics",
                "subject": "Mathematics",
                "target_grade_level": "Grade 10",
                "course_length": "1 Year",
                "semester_count": 2,
                "diagnostic_test_before_course": True,
                "retesting_allowed": True,
                "retesting_count": 2,
                "quizzes_per_module": 3,
                "midterm_examination": True,
                "final_examination": True,
                "total_quiz_questions": 20,
                "mastery_requirement": 80.0,
                "total_modules": 12,
                "estimated_duration_min_per_class": 45,
                "generated_course_name": "Mastering Advanced Mathematics: A Comprehensive Journey",
            }
        }
