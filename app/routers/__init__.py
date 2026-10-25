from app.routers.auth import router as auth_router
from app.routers.profile import router as profile_router
from app.routers.resumes import router as resumes_router
from app.routers.subjects import router as subjects_router
from app.routers.interviews import router as interviews_router
from app.routers.questions import router as questions_router
from app.routers.dashboard import router as dashboard_router

__all__ = [
    "auth_router",
    "profile_router",
    "resumes_router",
    "subjects_router",
    "interviews_router",
    "questions_router",
    "dashboard_router",
]

