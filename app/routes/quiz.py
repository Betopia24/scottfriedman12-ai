# app/routes/quiz.py
from fastapi import APIRouter, HTTPException, status
from app.database.database import get_db
from app.schemas.quiz_schemas import (
    GenerateQuizInput,
    GenerateQuizResponse,
    QuizQuestion,
    QuizOption,
    SubmitAnswerInput,
    SubmitAnswerResponse,
    GetQuizResultsResponse,
)
from app.services.quiz_generator_service import generate_quiz_questions

router = APIRouter(
    prefix="/quiz",
    tags=["Quiz"],
)

QUIZ_QUESTION_COLLECTION = "Quiz_question"
QUIZ_ANSWER_COLLECTION = "Quiz_answer"
LECTURE_COLLECTION = "Course_lecture_generator"
COURSE_COLLECTION = "course_name_generator"


@router.post("/generate", response_model=GenerateQuizResponse)
async def generate_quiz(input_data: GenerateQuizInput):
    """
    Generate 10 quiz questions based on course lecture content.
    
    - Fetches course data from Course_lecture_generator using unique_session_id
    - Generates 10 quiz questions using OpenAI
    - Saves questions to Quiz_question collection
    """
    db = get_db()
    
    # Fetch course lecture data using unique_session_id
    lecture_doc = await db[LECTURE_COLLECTION].find_one(
        {"unique_session_id": input_data.unique_session_id}
    )
    
    if not lecture_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No course lecture found for session_id: {input_data.unique_session_id}"
        )
    
    course_config = await db[COURSE_COLLECTION].find_one(
        {"unique_session_id": input_data.unique_session_id},
        {"_id": 0},
    )

    # Check if quiz already exists for this session and user
    existing_quiz = await db[QUIZ_QUESTION_COLLECTION].find_one(
        {
            "unique_session_id": input_data.unique_session_id,
            "unique_user_id": input_data.unique_user_id
        }
    )
    
    if existing_quiz:
        # Return existing quiz
        existing_questions = await db[QUIZ_QUESTION_COLLECTION].find(
            {
                "unique_session_id": input_data.unique_session_id,
                "unique_user_id": input_data.unique_user_id
            }
        ).sort("question_number", 1).to_list(length=10)
        
        quiz_questions = [
            QuizQuestion(
                question_id=q["question_id"],
                question_number=q["question_number"],
                question_text=q["question_text"],
                options=[QuizOption(**opt) for opt in q["options"]]
            )
            for q in existing_questions
        ]
        
        return GenerateQuizResponse(
            success=True,
            message="Quiz already exists for this session",
            quiz_questions=quiz_questions,
            total_questions=len(quiz_questions)
        )
    
    # Generate quiz questions using OpenAI
    questions = await generate_quiz_questions(
        lecture_doc,
        knowledge_bases=(course_config or {}).get("knowledge_bases"),
        user_instration=(course_config or {}).get("user_instration"),
    )
    
    # Save questions to database
    quiz_documents = []
    for question in questions:
        quiz_doc = {
            "unique_user_id": input_data.unique_user_id,
            "unique_session_id": input_data.unique_session_id,
            "question_id": question["question_id"],
            "question_number": question["question_number"],
            "question_text": question["question_text"],
            "options": question["options"],
            "correct_answer": question["correct_answer"],
        }
        quiz_documents.append(quiz_doc)
    
    # Insert all questions
    await db[QUIZ_QUESTION_COLLECTION].insert_many(quiz_documents)
    
    # Build response (exclude correct_answer from response)
    quiz_questions = [
        QuizQuestion(
            question_id=q["question_id"],
            question_number=q["question_number"],
            question_text=q["question_text"],
            options=[QuizOption(**opt) for opt in q["options"]]
        )
        for q in questions
    ]
    
    return GenerateQuizResponse(
        success=True,
        message="Quiz generated successfully",
        quiz_questions=quiz_questions,
        total_questions=len(quiz_questions)
    )


@router.post("/submit-answer", response_model=SubmitAnswerResponse)
async def submit_quiz_answer(input_data: SubmitAnswerInput):
    """
    Submit an answer to a quiz question.
    
    - Validates the question exists
    - Checks if answer is correct
    - Saves answer to Quiz_answer collection
    """
    db = get_db()
    
    # Find the question
    question = await db[QUIZ_QUESTION_COLLECTION].find_one(
        {
            "question_id": input_data.question_id,
            "unique_session_id": input_data.unique_session_id,
            "unique_user_id": input_data.unique_user_id
        }
    )
    
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question not found: {input_data.question_id}"
        )
    
    # Validate selected answer
    valid_options = ["A", "B", "C", "D"]
    if input_data.selected_answer not in valid_options:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid answer. Must be one of: {', '.join(valid_options)}"
        )
    
    # Check if answer is correct
    correct_answer = question["correct_answer"]
    is_correct = input_data.selected_answer == correct_answer
    
    # Check if answer already exists
    existing_answer = await db[QUIZ_ANSWER_COLLECTION].find_one(
        {
            "question_id": input_data.question_id,
            "unique_user_id": input_data.unique_user_id,
            "unique_session_id": input_data.unique_session_id
        }
    )
    
    if existing_answer:
        # Update existing answer
        await db[QUIZ_ANSWER_COLLECTION].update_one(
            {
                "question_id": input_data.question_id,
                "unique_user_id": input_data.unique_user_id,
                "unique_session_id": input_data.unique_session_id
            },
            {
                "$set": {
                    "selected_answer": input_data.selected_answer,
                    "is_correct": is_correct
                }
            }
        )
    else:
        # Save new answer
        answer_doc = {
            "unique_user_id": input_data.unique_user_id,
            "unique_session_id": input_data.unique_session_id,
            "question_id": input_data.question_id,
            "selected_answer": input_data.selected_answer,
            "is_correct": is_correct,
        }
        await db[QUIZ_ANSWER_COLLECTION].insert_one(answer_doc)
    
    return SubmitAnswerResponse(
        success=True,
        message="Answer submitted successfully",
        is_correct=is_correct,
        correct_answer=correct_answer
    )


@router.get("/results/{unique_session_id}/{unique_user_id}", response_model=GetQuizResultsResponse)
async def get_quiz_results(unique_session_id: str, unique_user_id: str):
    """
    Get quiz results for a user and session.
    
    - Returns total questions, answered questions, correct answers, and score percentage
    """
    db = get_db()
    
    # Get total questions
    total_questions = await db[QUIZ_QUESTION_COLLECTION].count_documents(
        {
            "unique_session_id": unique_session_id,
            "unique_user_id": unique_user_id
        }
    )
    
    if total_questions == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No quiz found for this session and user"
        )
    
    # Get all answers
    answers = await db[QUIZ_ANSWER_COLLECTION].find(
        {
            "unique_session_id": unique_session_id,
            "unique_user_id": unique_user_id
        }
    ).to_list(length=None)
    
    answered_questions = len(answers)
    correct_answers = sum(1 for ans in answers if ans.get("is_correct", False))
    
    score_percentage = (correct_answers / total_questions * 100) if total_questions > 0 else 0.0
    
    return GetQuizResultsResponse(
        success=True,
        total_questions=total_questions,
        answered_questions=answered_questions,
        correct_answers=correct_answers,
        score_percentage=round(score_percentage, 2)
    )
