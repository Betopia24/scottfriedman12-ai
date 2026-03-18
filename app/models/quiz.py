# app/models/quiz.py
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class QuizOption(BaseModel):
    """A single option for a multiple-choice question."""
    option_letter: str = Field(..., description="A, B, C, or D")
    option_text: str = Field(..., description="The text of this option")


class QuizQuestionModel(BaseModel):
    """
    A single quiz question document stored in Quiz_question table.
    Each question belongs to a user and session.
    """
    unique_user_id: str = Field(..., description="User ID who generated this quiz")
    unique_session_id: str = Field(..., description="Session ID from Course_lecture_generator")
    question_id: str = Field(..., description="Unique question ID e.g. QUZ-XXXXXXXXXX")
    question_number: int = Field(..., description="Question number (1-10)")
    question_text: str = Field(..., description="The quiz question text")
    options: List[QuizOption] = Field(..., description="List of 4 options (A, B, C, D)")
    correct_answer: str = Field(..., description="The correct option letter (A, B, C, or D)")
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat(), description="ISO timestamp")


class QuizAnswerModel(BaseModel):
    """
    A single user answer document stored in Quiz_answer table.
    Records the user's selected answer for a specific question.
    """
    unique_user_id: str = Field(..., description="User ID who submitted this answer")
    unique_session_id: str = Field(..., description="Session ID from Course_lecture_generator")
    question_id: str = Field(..., description="Question ID this answer corresponds to")
    selected_answer: str = Field(..., description="User's selected option (A, B, C, or D)")
    is_correct: bool = Field(..., description="Whether the answer is correct")
    submitted_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat(), description="ISO timestamp")
