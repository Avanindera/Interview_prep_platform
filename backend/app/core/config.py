import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# Robust Root Directory Detection
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
env_path = ROOT_DIR / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path, override=True)
else:
    load_dotenv(override=True)


# Default to absolute paths in project root so running from any directory works identically
_raw_db = os.getenv("DATABASE_URL", "")
if not _raw_db or _raw_db == "sqlite:///./interview_platform.db":
    _db_path = (ROOT_DIR / "interview_platform.db").resolve()
    # Normalize Windows backslashes for sqlite URL
    _db_url = f"sqlite:///{_db_path.as_posix()}"
else:
    _db_url = _raw_db

_raw_upload = os.getenv("UPLOAD_DIR", "uploads")
if not os.path.isabs(_raw_upload):
    _upload_path = str((ROOT_DIR / _raw_upload).resolve())
else:
    _upload_path = _raw_upload


class Settings(BaseSettings):
    PROJECT_NAME: str = "AI-Powered Technical & Speech Interview Platform"
    VERSION: str = "2.0.0"
    API_V1_STR: str = "/api/v1"

    DATABASE_URL: str = _db_url
    SECRET_KEY: str = os.getenv(
        "SECRET_KEY", "phase1-super-secret-jwt-key-for-interview-platform-2025"
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    UPLOAD_DIR: str = _upload_path

    # Gemini & RAG configurations
    GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY")
    GEMINI_MODEL: Optional[str] = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")
    GITHUB_TOKEN: Optional[str] = os.getenv("GITHUB_TOKEN")

    class Config:
        case_sensitive = True
        env_file = str(ROOT_DIR / ".env")
        extra = "ignore"


settings = Settings()

