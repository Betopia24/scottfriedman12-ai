# app/schemas/course_schemas.py
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class CourseInput(BaseModel):
    unique_user_id: str = Field(..., description="Previously generated unique user ID from User_id table")
    course_name: str = Field(..., description="Name of the course")
    subject: str = Field(..., description="Subject area")
    target_grade_level: str = Field(..., description="Target grade or academic level")
    course_length: str = Field(..., description="Duration of the course (e.g., '1 Semester', '1 Year')")
    semester_count: int = Field(..., ge=1, description="Number of semesters")
    diagnostic_test_before_course: bool = Field(..., description="Enable diagnostic test before course starts")
    retesting_allowed: bool = Field(..., description="Allow retesting")
    retesting_count: int = Field(..., ge=0, description="Number of retests allowed")
    quizzes_per_module: int = Field(..., ge=0, description="Number of quizzes per module")
    midterm_examination: bool = Field(..., description="Include midterm examination")
    final_examination: bool = Field(..., description="Include final examination")
    total_quiz_questions: int = Field(..., ge=1, description="Total number of quiz questions")
    mastery_requirement: float = Field(..., ge=0, le=100, description="Mastery requirement percentage (0-100)")
    total_modules: int = Field(..., ge=1, description="Total number of modules")
    estimated_duration_min_per_class: int = Field(..., ge=1, description="Estimated duration in minutes per class")

    class Config:
        json_schema_extra = {
            "example": {
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
            }
        }


class CourseDataResponse(BaseModel):
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
    total_number_created: int
    created_at: datetime


class GenerateCourseResponse(BaseModel):
    success: bool
    message: str
    unique_id: str
    unique_session_id: str
    name_of_the_course: str
    data: Optional[CourseDataResponse] = None


class GetCourseSessionResponse(BaseModel):
    success: bool
    message: str
    data: Optional[CourseDataResponse] = None