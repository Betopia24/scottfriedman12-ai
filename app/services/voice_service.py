# app/services/voice_service.py
import uuid
import asyncio
import re
from datetime import datetime, timezone
from pathlib import Path
from openai import AsyncOpenAI
from app.database.database import settings

# ── Audio Storage Configuration ───────────────────────────────────────────────
# Audio files are saved to: static/audio/{session_id}/module_{n}.mp3
# 
# FOLDER STRUCTURE:
#   static/
#     audio/
#       SES-XXXX/
#         module_1.mp3
#         module_2.mp3
#         ...
#
# ACCESS IN PRODUCTION:
#   URL: http://your-domain.com/audio/{session_id}/module_{n}.mp3
#   Example: http://localhost:8003/audio/SES-ABC123/module_1.mp3
#
# The static folder is mounted in main.py as:
#   app.mount("/audio", StaticFiles(directory="static/audio"), name="audio")
# ──────────────────────────────────────────────────────────────────────────────

# Get absolute path to ensure it works regardless of execution directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent
AUDIO_DIR = BASE_DIR / "static" / "audio"

# Ensure base audio directory exists
try:
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    print(f"✅ Audio directory initialized: {AUDIO_DIR}")
except Exception as e:
    print(f"⚠️ Failed to create audio directory: {e}")


def _sanitize_part_key(part_key: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_\-]+", "_", part_key.strip())
    return cleaned.strip("_") or "part"


def _estimate_duration_seconds(text: str) -> float:
    word_count = len(text.split())
    return round((word_count / 150) * 60, 1)


def _collect_module_audio_parts(module: dict) -> list[dict]:
    """Build an ordered list of individual module sections for separate TTS files."""
    parts: list[dict] = []

    title = (module.get("title") or "").strip()
    if title:
        parts.append(
            {
                "part_key": "title",
                "part_label": "Module Title",
                "text": title,
            }
        )

    introduction = (module.get("introduction") or "").strip()
    if introduction:
        parts.append(
            {
                "part_key": "introduction",
                "part_label": "Introduction",
                "text": introduction,
            }
        )

    for index, topic in enumerate(module.get("study_topics", []), start=1):
        topic_name = (topic.get("topic_name") or "").strip()
        topic_data = topic.get("topic_wise_study_data") or {}
        summary = (topic_data.get("summary") or "").strip()
        detailed_explanation = (topic_data.get("detailed_explanation") or "").strip()

        if topic_name:
            parts.append(
                {
                    "part_key": f"topic_{index}_name",
                    "part_label": f"Topic {index} Name",
                    "text": topic_name,
                }
            )

        if summary:
            parts.append(
                {
                    "part_key": f"topic_{index}_summary",
                    "part_label": f"Topic {index} Summary",
                    "text": summary,
                }
            )

        if detailed_explanation:
            parts.append(
                {
                    "part_key": f"topic_{index}_detailed_explanation",
                    "part_label": f"Topic {index} Detailed Explanation",
                    "text": detailed_explanation,
                }
            )

    if not parts:
        module_n = module.get("module_number", "")
        parts.append(
            {
                "part_key": "fallback",
                "part_label": "Fallback",
                "text": f"Module {module_n}. Content coming soon.",
            }
        )

    return parts


async def generate_voice_for_module(
    module: dict,
    session_id: str,
) -> dict:
    """
    Generates separate TTS audio files for each module section using OpenAI tts-1.
    Saves files to static/audio/{session_id}/module_{n}_part_{idx}_{part_key}.mp3
    Returns a voice metadata dict.
    """
    voice_id  = f"vox-{uuid.uuid4().hex[:10].upper()}"
    module_n  = module.get("module_number", 0)
    generated_at = datetime.now(timezone.utc).isoformat()

    if not settings.OPENAI_API_KEY:
        return {
            "voice_id": voice_id,
            "generated_at": generated_at,
            "audio_url": None,
            "duration_seconds": None,
            "status": "failed",
        }

    try:
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        parts = _collect_module_audio_parts(module)

        print(f"🎤 Generating TTS parts for module {module_n}...")
        print(f"🧩 Total parts to generate: {len(parts)}")
        print(f"📂 Base audio directory: {AUDIO_DIR}")

        # Create session-specific audio directory
        session_audio_dir = AUDIO_DIR / session_id
        
        # Ensure directory exists - create it if not
        try:
            session_audio_dir.mkdir(parents=True, exist_ok=True)
            print(f"📁 Created/verified directory: {session_audio_dir}")
        except Exception as dir_error:
            print(f"❌ Failed to create directory: {dir_error}")
            raise
        
        audio_parts = []
        total_duration_seconds = 0.0

        for idx, part in enumerate(parts, start=1):
            part_key = _sanitize_part_key(part["part_key"])
            part_label = part["part_label"]
            part_text = part["text"]

            print(f"🎧 Generating part {idx}/{len(parts)}: {part_key}")

            try:
                response = await client.audio.speech.create(
                    model="tts-1",
                    voice="alloy",  # options: alloy, echo, fable, onyx, nova, shimmer
                    input=part_text[:4096],  # OpenAI TTS max input is 4096 chars per call
                    response_format="mp3",
                )

                file_name = f"module_{module_n}_part_{idx:02d}_{part_key}.mp3"
                file_path = session_audio_dir / file_name

                audio_bytes = response.content
                file_path.write_bytes(audio_bytes)

                if not file_path.exists():
                    raise RuntimeError(f"Audio file not found after saving: {file_name}")

                duration_seconds = _estimate_duration_seconds(part_text)
                total_duration_seconds += duration_seconds
                audio_url = f"/audio/{session_id}/{file_name}"

                audio_parts.append(
                    {
                        "part_key": part_key,
                        "part_label": part_label,
                        "audio_url": audio_url,
                        "duration_seconds": duration_seconds,
                        "status": "completed",
                    }
                )

                print(f"✅ Saved part audio: {audio_url}")
            except Exception as part_error:
                print(f"❌ Failed part '{part_key}' for module {module_n}: {part_error}")
                audio_parts.append(
                    {
                        "part_key": part_key,
                        "part_label": part_label,
                        "audio_url": None,
                        "duration_seconds": None,
                        "status": "failed",
                    }
                )

        first_success_url = next(
            (part.get("audio_url") for part in audio_parts if part.get("status") == "completed"),
            None,
        )
        overall_status = (
            "completed"
            if audio_parts and all(part.get("status") == "completed" for part in audio_parts)
            else "failed"
        )

        return {
            "voice_id": voice_id,
            "generated_at": generated_at,
            "audio_url": first_success_url,
            "duration_seconds": round(total_duration_seconds, 1) if total_duration_seconds else None,
            "audio_parts": audio_parts,
            "total_parts": len(audio_parts),
            "status": overall_status,
        }

    except Exception as e:
        print(f"❌ TTS failed for module {module_n}: {e}")
        return {
            "voice_id": voice_id,
            "generated_at": generated_at,
            "audio_url": None,
            "duration_seconds": None,
            "audio_parts": [],
            "total_parts": 0,
            "status": "failed",
        }


async def generate_voices_for_all_modules(
    modules: list[dict],
    session_id: str,
) -> list[dict]:
    """
    Generates TTS audio for all modules concurrently.
    Returns the modules list with voice data populated.
    """
    tasks = [
        generate_voice_for_module(module, session_id)
        for module in modules
    ]
    voice_results = await asyncio.gather(*tasks)

    for module, voice_data in zip(modules, voice_results):
        module["voice"] = voice_data

    return modules