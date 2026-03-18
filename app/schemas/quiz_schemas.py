# app/schemas/quiz_schemas.py
from typing import List
from pydantic import BaseModel


class QuizOption(BaseModel):
    """Schema for a quiz option."""
    option_letter: str
    option_text: str


class QuizQuestion(BaseModel):
    """Schema for a single quiz question."""
    question_id: str
    question_number: int
    question_text: str
    options: List[QuizOption]


class GenerateQuizInput(BaseModel):
    """Input schema for generating a quiz."""
    unique_session_id: str
    unique_user_id: str


class GenerateQuizResponse(BaseModel):
    """Response schema for quiz generation."""
    success: bool
    message: str
    quiz_questions: List[QuizQuestion]
    total_questions: int


class SubmitAnswerInput(BaseModel):
    """Input schema for submitting a quiz answer."""
    unique_user_id: str
    unique_session_id: str
    question_id: str
    selected_answer: str


class SubmitAnswerResponse(BaseModel):
    """Response schema for answer submission."""
    success: bool
    message: str
    is_correct: bool
    correct_answer: str


class GetQuizResultsResponse(BaseModel):
    """Response schema for getting quiz results."""
    success: bool
    total_questions: int
    answered_questions: int
    correct_answers: int
    score_percentage: float
