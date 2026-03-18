# app/database/database.py
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    MONGO_URI: str
    DB_NAME: str
    OPENAI_API_KEY: Optional[str] = None  # Optional so existing .env doesn't break

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()


class Database:
    client: AsyncIOMotorClient = None
    db = None


db_instance = Database()


async def connect_db():
    db_instance.client = AsyncIOMotorClient(settings.MONGO_URI)
    db_instance.db = db_instance.client[settings.DB_NAME]
    print(f"✅ Connected to MongoDB — Database: {settings.DB_NAME}")

    # ── User_id table ──────────────────────────────────────────────────────
    user_collection = db_instance.db["User_id table"]
    await user_collection.create_index("user_id", unique=True)
    print("✅ Unique index on 'user_id' ensured.")

    # ── course_name_generator ──────────────────────────────────────────────
    course_collection = db_instance.db["course_name_generator"]
    await course_collection.create_index("unique_session_id", unique=True)
    print("✅ Unique index on 'unique_session_id' in course_name_generator ensured.")
    await course_collection.create_index("unique_user_id")
    print("✅ Index on 'unique_user_id' in course_name_generator ensured.")

    # ── Course_lecture_generator ───────────────────────────────────────────
    lecture_collection = db_instance.db["Course_lecture_generator"]
    await lecture_collection.create_index("unique_session_id", unique=True)
    print("✅ Unique index on 'unique_session_id' in Course_lecture_generator ensured.")
    await lecture_collection.create_index("unique_id")
    print("✅ Index on 'unique_id' in Course_lecture_generator ensured.")

    # ── Quiz_question ──────────────────────────────────────────────────────
    quiz_question_collection = db_instance.db["Quiz_question"]
    await quiz_question_collection.create_index("question_id", unique=True)
    print("✅ Unique index on 'question_id' in Quiz_question ensured.")
    await quiz_question_collection.create_index("unique_user_id")
    print("✅ Index on 'unique_user_id' in Quiz_question ensured.")
    await quiz_question_collection.create_index("unique_session_id")
    print("✅ Index on 'unique_session_id' in Quiz_question ensured.")

    # ── Quiz_answer ────────────────────────────────────────────────────────
    quiz_answer_collection = db_instance.db["Quiz_answer"]
    await quiz_answer_collection.create_index(
        [("unique_user_id", 1), ("unique_session_id", 1), ("question_id", 1)],
        unique=True
    )
    print("✅ Compound unique index on Quiz_answer ensured.")
    await quiz_answer_collection.create_index("unique_user_id")
    print("✅ Index on 'unique_user_id' in Quiz_answer ensured.")


async def close_db():
    if db_instance.client:
        db_instance.client.close()
        print("🔌 MongoDB connection closed.")


def get_db():
    return db_instance.db