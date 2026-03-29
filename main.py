from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from pathlib import Path

from app.database import connect_db, close_db
from app.routes.user_id import router as user_id_router
from app.routes.course_name_generator import router as course_router
from app.routes.course_lecture import router as course_lecture_router
from app.routes.course_assistant import router as course_assistant_router
from app.routes.quiz import router as quiz_router
from app.routes.embeddings import router as embeddings_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    yield
    await close_db()


app = FastAPI(
    title="User ID Generator API",
    description=(
        "A FastAPI service that generates and manages unique User IDs.\n\n"
        "## Features\n"
        "- ✅ Generate globally unique User IDs (format: `USR-XXXXXXXX`)\n"
        "- ✅ Store User IDs in MongoDB (`User_id table` collection)\n"
        "- ✅ Retrieve all stored User IDs\n"
        "- ✅ Look up a specific User ID\n"
        "- ✅ Delete a User ID\n"
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create static directory if it doesn't exist (use absolute path)
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
AUDIO_DIR = STATIC_DIR / "audio"

# Ensure directories exist
STATIC_DIR.mkdir(exist_ok=True)
AUDIO_DIR.mkdir(exist_ok=True)

print(f"📁 Static directory: {STATIC_DIR}")
print(f"🔊 Audio directory: {AUDIO_DIR}")

# Mount static files to serve audio
app.mount("/audio", StaticFiles(directory=str(AUDIO_DIR)), name="audio")

# Routers
app.include_router(user_id_router, prefix="/api/v1")
app.include_router(course_router, prefix="/api/v1")
app.include_router(course_lecture_router, prefix="/api/v1")
app.include_router(course_assistant_router, prefix="/api/v1")
app.include_router(quiz_router, prefix="/api/v1")
app.include_router(embeddings_router, prefix="/api/v1")

@app.get("/", tags=["Health"])
async def root():
    return {
        "service": "User ID Generator API",
        "status": "running",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy"}


# testing for git issue
