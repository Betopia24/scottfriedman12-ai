# app/routers/course_lecture.py
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, HTTPException, status

from app.database.database import get_db
from app.schemas.course_lecture_schemas import (
    GenerateSingleModuleInput,
    GenerateSingleModuleResponse,
    GetLectureResponse,
    LectureApiResponse,
    LectureVariables,
    ModuleData,
    ResourceItem,
    StudyTopic,
    VoiceData,
    VoicePartData,
    VoiceStatus,
)
from app.services.course_generator_service import generate_single_module
from app.services.voice_service import generate_voices_for_all_modules

router = APIRouter(
    prefix="/course-lecture",
    tags=["Course Lecture Generator"],
)

COLLECTION_NAME = "Course_lecture_generator"
SOURCE_COLLECTION = "course_name_generator"


def _build_module_objects(raw_modules: list[dict]) -> list[ModuleData]:
    """Converts raw GPT dicts → validated ModuleData pydantic objects."""
    result = []
    for mod in raw_modules:
        study_topics = [
            StudyTopic(
                topic_name=t.get("topic_name", ""),
                topic_wise_study_data=t.get("topic_wise_study_data", {}),
            )
            for t in mod.get("study_topics", [])
        ]
        voice_raw = mod.get("voice", {})
        audio_parts = [
            VoicePartData(
                part_key=part.get("part_key", ""),
                part_label=part.get("part_label", ""),
                audio_url=part.get("audio_url"),
                duration_seconds=part.get("duration_seconds"),
                status=VoiceStatus(part.get("status", "pending")),
            )
            for part in voice_raw.get("audio_parts", [])
        ]
        voice = VoiceData(
            voice_id=voice_raw.get("voice_id", ""),
            generated_at=voice_raw.get("generated_at"),
            audio_url=voice_raw.get("audio_url"),
            duration_seconds=voice_raw.get("duration_seconds"),
            audio_parts=audio_parts,
            total_parts=voice_raw.get("total_parts", len(audio_parts)),
            status=VoiceStatus(voice_raw.get("status", "pending")),
        )
        resources = [
            ResourceItem(
                title=r.get("title", ""),
                type=r.get("type", ""),
                description=r.get("description"),
            )
            for r in mod.get("resources", [])
        ]
        result.append(
            ModuleData(
                module_number=mod.get("module_number", 0),
                title=mod.get("title", ""),
                introduction=mod.get("introduction", ""),
                resources=resources,
                study_topics=study_topics,
                voice=voice,
            )
        )
    return result


# ─────────────────────────────────────────────────────────────────────────────
# POST /course-lecture/generate-module
# ─────────────────────────────────────────────────────────────────────────────
@router.post(
    "/generate-module",
    response_model=GenerateSingleModuleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a single course module with AI content and TTS voice",
    description=(
        "Generates a single module for an existing course configuration. "
        "Fetches course configuration from **course_name_generator** using the provided "
        "`unique_session_id` and generates content for the specified `module_number` using **GPT-4.1**. "
        "Then calls **OpenAI TTS** to generate voice narration for the module. "
        "The module is saved or updated in **Course_lecture_generator**."
    ),
)
async def generate_single_course_module(payload: GenerateSingleModuleInput):
    db = get_db()

    # ── 1. Fetch course data from course_name_generator ──────────────────
    source_col = db[SOURCE_COLLECTION]
    course_data = await source_col.find_one(
        {"unique_session_id": payload.unique_session_id},
        {"_id": 0},
    )
    if not course_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"No course found with unique_session_id='{payload.unique_session_id}'. "
                "Please generate a course first via POST /course/generate."
            ),
        )

    total_modules = course_data.get("total_modules", 5)
    
    # Validate module number
    if payload.module_number < 1 or payload.module_number > total_modules:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid module_number. Must be between 1 and {total_modules}.",
        )

    generated_course_name = course_data.get("generated_course_name", course_data.get("course_name", ""))
    unique_id = course_data.get("unique_user_id", "")

    # ── 2. Generate single module content via GPT-4.1 ─────────────────────
    try:
        raw_module = await generate_single_module(course_data, payload.module_number)
        print(f"📚 Generated module {payload.module_number} from GPT")
        
        # Validate module has content
        if not raw_module.get("introduction") or not raw_module.get("study_topics"):
            raise ValueError("Generated module has empty introduction or study_topics")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"GPT module generation failed: {str(e)}",
        )

    # ── 3. Generate TTS voice for the module ──────────────────────────────
    try:
        # Wrap in list for voice generation, then unwrap
        modules_with_voice = await generate_voices_for_all_modules(
            [raw_module], payload.unique_session_id
        )
        raw_module = modules_with_voice[0] if modules_with_voice else raw_module
    except Exception as e:
        # Voice failure is non-fatal — mark as failed and continue
        print(f"⚠️ Voice generation error for module {payload.module_number}: {e}")
        raw_module["voice"] = {
            "voice_id": "",
            "generated_at": None,
            "audio_url": None,
            "duration_seconds": None,
            "audio_parts": [],
            "total_parts": 0,
            "status": "failed",
        }

    # ── 4. Save or update module in Course_lecture_generator ──────────────
    lecture_col = db[COLLECTION_NAME]
    
    # Check if lecture document exists
    existing = await lecture_col.find_one(
        {"unique_session_id": payload.unique_session_id},
        {"_id": 0},
    )

    if existing:
        # Update existing document - replace or add the module
        existing_modules = existing.get("modules", [])
        
        # Find and replace if module number exists, otherwise append
        module_found = False
        for i, mod in enumerate(existing_modules):
            if mod.get("module_number") == payload.module_number:
                existing_modules[i] = raw_module
                module_found = True
                break
        
        if not module_found:
            existing_modules.append(raw_module)
        
        # Sort modules by module_number
        existing_modules.sort(key=lambda x: x.get("module_number", 0))
        
        await lecture_col.update_one(
            {"unique_session_id": payload.unique_session_id},
            {
                "$set": {
                    "modules": existing_modules,
                    "updated_at": datetime.utcnow(),
                }
            },
        )
        print(f"✅ Updated module {payload.module_number} in existing lecture")
    else:
        # Create new lecture document with this first module
        document = {
            "unique_id": unique_id,
            "unique_session_id": payload.unique_session_id,
            "generated_course_name": generated_course_name,
            "modules": [raw_module],
            "created_at": datetime.utcnow(),
        }
        await lecture_col.insert_one(document)
        print(f"✅ Created new lecture with module {payload.module_number}")

    # ── 5. Build and return response ──────────────────────────────────────
    module_object = _build_module_objects([raw_module])[0]

    return GenerateSingleModuleResponse(
        success=True,
        message=f"Successfully generated module {payload.module_number} of {total_modules}.",
        module=module_object,
        unique_session_id=payload.unique_session_id,
        module_number=payload.module_number,
        total_modules=total_modules,
    )


# ─────────────────────────────────────────────────────────────────────────────
# GET /course-lecture/{unique_session_id}
# ─────────────────────────────────────────────────────────────────────────────
@router.get(
    "/{unique_session_id}",
    response_model=GetLectureResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve a generated course lecture by session ID",
)
async def get_course_lecture(unique_session_id: str):
    db = get_db()
    lecture_col = db[COLLECTION_NAME]

    doc = await lecture_col.find_one(
        {"unique_session_id": unique_session_id},
        {"_id": 0},
    )
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No lecture found for session ID '{unique_session_id}'.",
        )

    generated_course_name = doc.get("generated_course_name", "")
    module_objects = _build_module_objects(doc.get("modules", []))

    api_resp = LectureApiResponse(
        variables=LectureVariables(
            unique_id=doc.get("unique_id", ""),
            unique_session_id=unique_session_id,
            generated_course_name=generated_course_name,
        ),
        modules=module_objects,
    )

    return GetLectureResponse(
        success=True,
        message="Course lecture retrieved successfully.",
        api_response=api_resp,
    )


# ─────────────────────────────────────────────────────────────────────────────
# DELETE /course-lecture/{unique_session_id}
# ─────────────────────────────────────────────────────────────────────────────
@router.delete(
    "/{unique_session_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a cached course lecture by session ID",
    description="Removes the cached lecture from the database so it can be regenerated.",
)
async def delete_course_lecture(unique_session_id: str):
    db = get_db()
    lecture_col = db[COLLECTION_NAME]

    result = await lecture_col.delete_one(
        {"unique_session_id": unique_session_id}
    )
    
    if result.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No lecture found for session ID '{unique_session_id}'.",
        )

    return {
        "success": True,
        "message": f"Successfully deleted lecture for session '{unique_session_id}'. You can now regenerate it.",
    }


# ─────────────────────────────────────────────────────────────────────────────
# GET /course-lecture/debug/audio-files/{unique_session_id}
# ─────────────────────────────────────────────────────────────────────────────
@router.get(
    "/debug/audio-files/{unique_session_id}",
    status_code=status.HTTP_200_OK,
    summary="Debug: List audio files for a session",
    description="Lists all audio files in the static/audio folder for debugging purposes.",
)
async def debug_audio_files(unique_session_id: str):
    from pathlib import Path
    
    audio_dir = Path("static/audio") / unique_session_id
    
    if not audio_dir.exists():
        return {
            "success": False,
            "message": f"Audio directory does not exist for session '{unique_session_id}'",
            "expected_path": str(audio_dir.absolute()),
            "files": []
        }
    
    files = []
    for file_path in audio_dir.glob("*.mp3"):
        files.append({
            "filename": file_path.name,
            "size_bytes": file_path.stat().st_size,
            "url": f"/audio/{unique_session_id}/{file_path.name}",
            "full_path": str(file_path.absolute())
        })
    
    return {
        "success": True,
        "session_id": unique_session_id,
        "audio_directory": str(audio_dir.absolute()),
        "total_files": len(files),
        "files": files
    }