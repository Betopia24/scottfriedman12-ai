import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

import httpx
from fastapi import HTTPException, status
from openai import AsyncOpenAI

from app.database.database import get_db, settings


THREAD_COLLECTION = "course_assistant_threads"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _pick(source: dict, *keys: str, default: Any = "") -> Any:
    for key in keys:
        if key in source and source[key] is not None:
            return source[key]
    return default


def _normalize_topic(topic: dict) -> dict:
    if "topic_wise_study_data" in topic and isinstance(topic["topic_wise_study_data"], dict):
        topic_data = topic["topic_wise_study_data"]
    else:
        topic_data = {
            "summary": _pick(topic, "summary"),
            "detailed_explanation": _pick(topic, "detailed_explanation", "detailedExplanation"),
            "resources": _pick(topic, "resources", default=[]),
        }

    return {
        "topic_name": _pick(topic, "topic_name", "topicName"),
        "topic_wise_study_data": {
            "summary": _pick(topic_data, "summary"),
            "detailed_explanation": _pick(
                topic_data,
                "detailed_explanation",
                "detailedExplanation",
            ),
            "resources": _pick(topic_data, "resources", default=[]),
        },
    }


def _normalize_context_payload(payload: dict, source_id: str) -> dict:
    raw = payload.get("data") if isinstance(payload.get("data"), dict) else payload

    module = {
        "id": _pick(raw, "id", default=source_id),
        "module_number": _pick(raw, "module_number", "moduleNumber", default=0),
        "title": _pick(raw, "title", "module_title", "moduleTitle"),
        "introduction": _pick(raw, "introduction"),
        "resources": _pick(raw, "resources", default=[]),
        "study_topics": [
            _normalize_topic(topic)
            for topic in _pick(raw, "study_topics", "studyTopics", default=[])
            if isinstance(topic, dict)
        ],
        "quiz_questions": _pick(raw, "quizQuestions", "quiz_questions", default=[]),
        "voice_data": _pick(raw, "voiceData", "voice_data", default={}),
    }

    return {
        "source_id": source_id,
        "unique_session_id": _pick(raw, "unique_session_id", "uniqueSessionId"),
        "generated_course_name": _pick(
            raw,
            "generated_course_name",
            "generatedCourseName",
            "course_name",
            "courseName",
            default=module["title"],
        ),
        "subject": _pick(raw, "subject"),
        "target_grade_level": _pick(raw, "target_grade_level", "targetGradeLevel"),
        "rag_context": _pick(raw, "rag_context", "ragContext"),
        "module": module,
    }


def _build_module_context(context: dict) -> str:
    module = context.get("module", {})

    resource_lines = []
    for resource in module.get("resources", []):
        if not isinstance(resource, dict):
            continue
        title = resource.get("title", "")
        res_type = resource.get("type", "")
        description = resource.get("description", "")
        resource_lines.append(f"- {title} ({res_type}): {description}".strip())

    topic_lines = []
    for index, topic in enumerate(module.get("study_topics", []), start=1):
        if not isinstance(topic, dict):
            continue
        topic_name = topic.get("topic_name", "")
        topic_data = topic.get("topic_wise_study_data") or {}
        summary = topic_data.get("summary", "")
        detailed_explanation = topic_data.get("detailed_explanation", "")

        topic_resources = []
        for resource in topic_data.get("resources", []):
            if not isinstance(resource, dict):
                continue
            title = resource.get("title", "")
            res_type = resource.get("type", "")
            description = resource.get("description", "")
            topic_resources.append(f"- {title} ({res_type}): {description}".strip())

        topic_lines.append(
            "\n".join(
                [
                    f"Topic {index}: {topic_name}",
                    f"Summary: {summary}",
                    f"Detailed Explanation: {detailed_explanation}",
                    "Topic Resources:",
                    *(topic_resources or ["- None"]),
                ]
            )
        )

    return "\n\n".join(
        [
            f"Course: {context.get('generated_course_name', '')}",
            f"Subject: {context.get('subject', '')}",
            f"Target Level: {context.get('target_grade_level', '')}",
            f"Module Title: {module.get('title', '')}",
            f"Module Introduction: {module.get('introduction', '')}",
            "Module Resources:",
            *(resource_lines or ["- None"]),
            "Study Topics:",
            *(topic_lines or ["No study topics available."]),
            f"Reference Context:\n{context.get('rag_context') or 'None'}",
        ]
    )


async def _fetch_context_from_source(source_id: str) -> dict:
    base_url = (settings.COURSE_ASSISTANT_BASE_URL or "").strip()
    if not base_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="COURSE_ASSISTANT_BASE_URL is not configured.",
        )

    url = f"{base_url.rstrip('/')}/course/module/{source_id}"

    headers = {"Accept": "application/json"}
    bearer_token = (settings.COURSE_ASSISTANT_CONTEXT_TOKEN or "").strip()
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"

    timeout = httpx.Timeout(30.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to fetch module context from source endpoint: {exc}",
            ) from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Source endpoint did not return valid JSON.",
        ) from exc

    if not payload.get("success", False):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=payload.get("message") or "Source endpoint returned an unsuccessful response.",
        )

    return _normalize_context_payload(payload, source_id)


async def _ensure_thread_indexes() -> None:
    db = get_db()
    await db[THREAD_COLLECTION].create_index("thread_id", unique=True)
    await db[THREAD_COLLECTION].create_index("source_id")
    await db[THREAD_COLLECTION].create_index("updated_at")


async def _load_thread(thread_id: str) -> dict | None:
    db = get_db()
    return await db[THREAD_COLLECTION].find_one({"thread_id": thread_id}, {"_id": 0})


async def _save_thread(
    thread_id: str,
    source_id: str,
    context: dict,
    messages: List[Dict[str, str]],
) -> None:
    db = get_db()
    now = _utcnow()
    await db[THREAD_COLLECTION].update_one(
        {"thread_id": thread_id},
        {
            "$set": {
                "source_id": source_id,
                "context": context,
                "messages": messages,
                "updated_at": now,
            },
            "$setOnInsert": {
                "thread_id": thread_id,
                "created_at": now,
            },
        },
        upsert=True,
    )


async def generate_course_assistant_answer(
    source_id: str,
    question: str,
    thread_id: str = "",
) -> dict:
    if not settings.OPENAI_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OPENAI_API_KEY is not configured in .env",
        )

    await _ensure_thread_indexes()

    is_new_thread = not bool(thread_id.strip())
    resolved_thread_id = thread_id.strip() or f"THR-{uuid.uuid4().hex[:16].upper()}"

    existing_thread = await _load_thread(resolved_thread_id)
    if existing_thread and existing_thread.get("source_id") and existing_thread["source_id"] != source_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="thread_id does not belong to the provided id.",
        )

    context = (existing_thread or {}).get("context")
    if not isinstance(context, dict) or not context:
        context = await _fetch_context_from_source(source_id)
    previous_messages = list((existing_thread or {}).get("messages", []))

    system_prompt = (
        "You are a patient tutor helping a student understand a course module. "
        "Use the provided course and module context first. "
        "Explain in simple, supportive language. "
        "Give one short example when useful. "
        "If the student asks a follow-up, continue the same discussion naturally. "
        "Do not mention internal JSON, database fields, APIs, or implementation details."
        "Do not answer any question that is not related with the course module"
    )

    messages_for_model: List[Dict[str, str]] = [
        {"role": "system", "content": system_prompt},
        {"role": "system", "content": _build_module_context(context)},
    ]
    messages_for_model.extend(
        msg
        for msg in previous_messages
        if msg.get("role") in {"user", "assistant"} and msg.get("content")
    )
    messages_for_model.append({"role": "user", "content": question})

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages_for_model,
        temperature=0.3,
        max_tokens=700,
    )

    answer = (response.choices[0].message.content or "").strip()
    if not answer:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Assistant did not return an answer.",
        )

    updated_messages = previous_messages + [
        {"role": "user", "content": question},
        {"role": "assistant", "content": answer},
    ]
    await _save_thread(
        thread_id=resolved_thread_id,
        source_id=source_id,
        context=context,
        messages=updated_messages,
    )

    return {
        "thread_id": resolved_thread_id,
        "answer": answer,
        "is_new_thread": is_new_thread,
    }
