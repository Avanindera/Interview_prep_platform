import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.database.database import engine
from app.database.base import Base
from app.database.seed import seed_data
import app.models  # ensure all models are registered
from app.routers import (
    auth_router,
    profile_router,
    resumes_router,
    subjects_router,
    interviews_router,
    questions_router,
    dashboard_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure uploads and audio directories exist
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(os.path.join(settings.UPLOAD_DIR, "audio"), exist_ok=True)

    # Create tables automatically if not present
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"Error creating database tables: {e}")

    # Seed initial test user and development questions on startup
    try:
        seed_data()
    except Exception as e:
        print(f"Error during auto-seed: {e}")
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "message": "AI-Powered Technical & Speech Interview Platform is running!",
        "docs_url": "/docs",
        "api_v1": settings.API_V1_STR,
    }


# Mount Routers under /api/v1
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(profile_router, prefix=settings.API_V1_STR)
app.include_router(resumes_router, prefix=settings.API_V1_STR)
app.include_router(subjects_router, prefix=settings.API_V1_STR)
app.include_router(interviews_router, prefix=settings.API_V1_STR)
app.include_router(questions_router, prefix=settings.API_V1_STR)
app.include_router(dashboard_router, prefix=settings.API_V1_STR)
