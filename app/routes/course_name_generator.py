# app/routers/course.py
import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException, status

from app.database.database import get_db
from app.schemas.course_schemas import (
    CourseInput,
    CourseDataResponse,
    GenerateCourseResponse,
    GetCourseSessionResponse,
)
from app.services.course_name_generator import generate_course_name

router = APIRouter(
    prefix="/course",
    tags=["Course Name Generator"],
)

COLLECTION_NAME = "course_name_generator"


def generate_session_id() -> str:
    """Generate a unique session ID prefixed with SES-"""
    return f"SES-{uuid.uuid4().hex[:12].upper()}"


# ─────────────────────────────────────────────────────────────
# POST /course/generate
# ─────────────────────────────────────────────────────────────
@router.post(
    "/generate",
    response_model=GenerateCourseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a course name using AI and save course configuration",
    description=(
        "Validates that the provided `unique_user_id` exists in the **User_id table**, "
        "calls OpenAI GPT-4.1 to generate a professional course title, "
        "creates a unique session ID, and persists all course data to the "
        "**course_name_generator** collection."
    ),
)
async def generate_course(payload: CourseInput):
    db = get_db()

    # ── 1. Validate that the unique_user_id exists and is active ──────────
    user_collection = db["User_id table"]
    existing_user = await user_collection.find_one(
        {"user_id": payload.unique_user_id, "is_active": True}
    )
    if not existing_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User ID '{payload.unique_user_id}' not found or is inactive. "
                   "Please generate a valid User ID first.",
        )

    # ── 2. Generate course name via OpenAI GPT-4.1 ────────────────────────
    try:
        generated_name = await generate_course_name(
            course_name=payload.course_name,
            subject=payload.subject,
            target_grade_level=payload.target_grade_level,
            course_length=payload.course_length,
            semester_count=payload.semester_count,
            total_modules=payload.total_modules,
            estimated_duration_min_per_class=payload.estimated_duration_min_per_class,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"OpenAI service error: {str(e)}",
        )

    # ── 3. Build session ID and document ──────────────────────────────────
    unique_session_id = generate_session_id()
    created_at = datetime.utcnow()
    
    # Calculate total_number_created based on course_length
    total_number_created = 10 if "year" in payload.course_length.lower() else 5

    course_document = {
        "unique_session_id": unique_session_id,
        "unique_user_id": payload.unique_user_id,
        "course_name": payload.course_name,
        "subject": payload.subject,
        "target_grade_level": payload.target_grade_level,
        "course_length": payload.course_length,
        "semester_count": payload.semester_count,
        "diagnostic_test_before_course": payload.diagnostic_test_before_course,
        "retesting_allowed": payload.retesting_allowed,
        "retesting_count": payload.retesting_count,
        "quizzes_per_module": payload.quizzes_per_module,
        "midterm_examination": payload.midterm_examination,
        "final_examination": payload.final_examination,
        "total_quiz_questions": payload.total_quiz_questions,
        "mastery_requirement": payload.mastery_requirement,
        "total_modules": payload.total_modules,
        "estimated_duration_min_per_class": payload.estimated_duration_min_per_class,
        "generated_course_name": generated_name,
        "total_number_created": total_number_created,
        "created_at": created_at,
    }

    # ── 4. Persist to MongoDB ──────────────────────────────────────────────
    course_collection = db[COLLECTION_NAME]
    await course_collection.insert_one(course_document)

    # ── 5. Build response ─────────────────────────────────────────────────
    response_data = CourseDataResponse(
        unique_session_id=unique_session_id,
        unique_user_id=payload.unique_user_id,
        course_name=payload.course_name,
        subject=payload.subject,
        target_grade_level=payload.target_grade_level,
        course_length=payload.course_length,
        semester_count=payload.semester_count,
        diagnostic_test_before_course=payload.diagnostic_test_before_course,
        retesting_allowed=payload.retesting_allowed,
        retesting_count=payload.retesting_count,
        quizzes_per_module=payload.quizzes_per_module,
        midterm_examination=payload.midterm_examination,
        final_examination=payload.final_examination,
        total_quiz_questions=payload.total_quiz_questions,
        mastery_requirement=payload.mastery_requirement,
        total_modules=payload.total_modules,
        estimated_duration_min_per_class=payload.estimated_duration_min_per_class,
        generated_course_name=generated_name,
        total_number_created=total_number_created,
        created_at=created_at,
    )

    return GenerateCourseResponse(
        success=True,
        message="Course configuration saved and course name generated successfully.",
        unique_id=payload.unique_user_id,
        unique_session_id=unique_session_id,
        name_of_the_course=generated_name,
        data=response_data,
    )


# ─────────────────────────────────────────────────────────────
# GET /course/session/{unique_session_id}
# ─────────────────────────────────────────────────────────────
@router.get(
    "/session/{unique_session_id}",
    response_model=GetCourseSessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve a course session by session ID",
    description="Fetches all course configuration data stored under a specific `unique_session_id`.",
)
async def get_course_by_session(unique_session_id: str):
    db = get_db()
    course_collection = db[COLLECTION_NAME]

    document = await course_collection.find_one(
        {"unique_session_id": unique_session_id},
        {"_id": 0},
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No course session found with ID '{unique_session_id}'.",
        )

    return GetCourseSessionResponse(
        success=True,
        message="Course session retrieved successfully.",
        data=CourseDataResponse(**document),
    )


# ─────────────────────────────────────────────────────────────
# GET /course/user/{unique_user_id}
# ─────────────────────────────────────────────────────────────
@router.get(
    "/user/{unique_user_id}",
    status_code=status.HTTP_200_OK,
    summary="Retrieve all course sessions for a user",
    description="Fetches all course sessions linked to a given `unique_user_id`.",
)
async def get_courses_by_user(unique_user_id: str):
    db = get_db()
    course_collection = db[COLLECTION_NAME]

    cursor = course_collection.find(
        {"unique_user_id": unique_user_id},
        {"_id": 0},
    )
    documents = await cursor.to_list(length=None)

    if not documents:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No course sessions found for user ID '{unique_user_id}'.",
        )

    return {
        "success": True,
        "total": len(documents),
        "unique_user_id": unique_user_id,
        "data": [CourseDataResponse(**doc) for doc in documents],
    }