from fastapi import APIRouter

from app.schemas.course_assistant_schemas import (
    CourseAssistantChatData,
    CourseAssistantChatInput,
    CourseAssistantChatResponse,
)
from app.services.course_assistant_service import generate_course_assistant_answer


router = APIRouter(
    prefix="/course-assistant",
    tags=["Course Assistant"],
)


@router.post(
    "/chat",
    response_model=CourseAssistantChatResponse,
    summary="Answer student questions about a generated module",
)
async def chat_with_course_assistant(payload: CourseAssistantChatInput):
    result = await generate_course_assistant_answer(
        source_id=payload.id,
        question=payload.question,
        thread_id=payload.thread_id,
    )

    return CourseAssistantChatResponse(
        success=True,
        message="Assistant response generated successfully.",
        data=CourseAssistantChatData(**result),
    )
