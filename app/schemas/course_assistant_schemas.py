from pydantic import BaseModel, Field


class CourseAssistantChatInput(BaseModel):
    id: str = Field(..., min_length=1, description="Unique module or content ID")
    question: str = Field(..., min_length=1, description="Student question")
    thread_id: str = Field(
        default="",
        description="Existing thread ID to continue a conversation. Leave empty to start a new thread.",
    )


class CourseAssistantChatData(BaseModel):
    thread_id: str
    answer: str
    is_new_thread: bool


class CourseAssistantChatResponse(BaseModel):
    success: bool
    message: str
    data: CourseAssistantChatData
