import os
import re
from typing import Any, Dict, List, Optional, Tuple
import requests

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000/api/v1")
HEALTH_URL = os.getenv("HEALTH_URL", "http://127.0.0.1:8000/")


def _safe_json(resp: requests.Response, default_msg: str = "Request failed") -> Any:
    """Safely extracts JSON or meaningful error text from a response without raising JSONDecodeError."""
    try:
        return resp.json()
    except Exception:
        text = resp.text.strip() if hasattr(resp, "text") else ""
        if text:
            # Strip HTML tags if HTML error page
            clean_text = re.sub(r"<[^>]+>", " ", text).strip()
            clean_text = re.sub(r"\s+", " ", clean_text)
            return {"detail": clean_text[:250] if clean_text else default_msg}
        return {"detail": f"{default_msg} (HTTP {resp.status_code})"}


def check_backend_online() -> bool:
    try:
        resp = requests.get(HEALTH_URL, timeout=3)
        return resp.status_code == 200
    except Exception:
        return False


def _get_headers(token: Optional[str] = None) -> Dict[str, str]:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def login(email: str, password: str) -> Tuple[bool, Any]:
    try:
        resp = requests.post(
            f"{API_BASE_URL}/auth/login",
            json={"email": email, "password": password},
            timeout=8,
        )
        if resp.status_code == 200:
            return True, resp.json()
        data = resp.json()
        return False, data.get("detail", "Login failed")
    except Exception as e:
        return False, f"Could not connect to backend: {str(e)}"


def register(name: str, email: str, password: str) -> Tuple[bool, Any]:
    try:
        resp = requests.post(
            f"{API_BASE_URL}/auth/register",
            json={"name": name, "email": email, "password": password},
            timeout=8,
        )
        if resp.status_code in (200, 201):
            return True, resp.json()
        data = resp.json()
        return False, data.get("detail", "Registration failed")
    except Exception as e:
        return False, f"Could not connect to backend: {str(e)}"


def get_current_user(token: str) -> Tuple[bool, Any]:
    try:
        resp = requests.get(
            f"{API_BASE_URL}/auth/me",
            headers=_get_headers(token),
            timeout=8,
        )
        if resp.status_code == 200:
            return True, resp.json()
        return False, resp.json().get("detail", "Session invalid")
    except Exception as e:
        return False, str(e)


def get_profile(token: str) -> Tuple[bool, Any]:
    try:
        resp = requests.get(
            f"{API_BASE_URL}/profile",
            headers=_get_headers(token),
            timeout=8,
        )
        if resp.status_code == 200:
            return True, resp.json()
        return False, resp.json().get("detail", "Could not fetch profile")
    except Exception as e:
        return False, str(e)


def update_profile(token: str, profile_data: dict) -> Tuple[bool, Any]:
    try:
        resp = requests.put(
            f"{API_BASE_URL}/profile",
            json=profile_data,
            headers=_get_headers(token),
            timeout=8,
        )
        if resp.status_code == 200:
            return True, resp.json()
        return False, resp.json().get("detail", "Failed to update profile")
    except Exception as e:
        return False, str(e)


def get_resumes(token: str) -> Tuple[bool, Any]:
    try:
        resp = requests.get(
            f"{API_BASE_URL}/resumes",
            headers=_get_headers(token),
            timeout=8,
        )
        if resp.status_code == 200:
            return True, resp.json()
        return False, resp.json().get("detail", "Failed to fetch resumes")
    except Exception as e:
        return False, str(e)


def upload_resume(token: str, file_bytes: bytes, filename: str, content_type: str) -> Tuple[bool, Any]:
    try:
        files = {"file": (filename, file_bytes, content_type)}
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.post(
            f"{API_BASE_URL}/resumes",
            files=files,
            headers=headers,
            timeout=15,
        )
        if resp.status_code in (200, 201):
            return True, resp.json()
        return False, resp.json().get("detail", "Failed to upload resume")
    except Exception as e:
        return False, str(e)


def delete_resume(token: str, resume_id: int) -> Tuple[bool, Any]:
    try:
        resp = requests.delete(
            f"{API_BASE_URL}/resumes/{resume_id}",
            headers=_get_headers(token),
            timeout=8,
        )
        if resp.status_code == 200:
            return True, resp.json()
        return False, resp.json().get("detail", "Failed to delete resume")
    except Exception as e:
        return False, str(e)


def get_subjects(token: str) -> Tuple[bool, Any]:
    try:
        resp = requests.get(
            f"{API_BASE_URL}/subjects",
            headers=_get_headers(token),
            timeout=8,
        )
        if resp.status_code == 200:
            return True, resp.json()
        return False, resp.json().get("detail", "Failed to load subjects")
    except Exception as e:
        return False, str(e)


def get_topics(token: str, subject_id: int) -> Tuple[bool, Any]:
    try:
        resp = requests.get(
            f"{API_BASE_URL}/subjects/{subject_id}/topics",
            headers=_get_headers(token),
            timeout=8,
        )
        if resp.status_code == 200:
            return True, resp.json()
        return False, resp.json().get("detail", "Failed to load topics")
    except Exception as e:
        return False, str(e)


def start_interview(
    token: str,
    subject_id: Optional[int] = None,
    topic_id: Optional[int] = None,
    generation_mode: str = "CURATED",
    custom_topic: Optional[str] = None,
    question_count: int = 3,
) -> Tuple[bool, Any]:
    try:
        payload = {
            "generation_mode": generation_mode,
            "question_count": question_count,
        }
        if subject_id:
            payload["subject_id"] = subject_id
        if topic_id:
            payload["topic_id"] = topic_id
        if custom_topic:
            payload["custom_topic"] = custom_topic

        resp = requests.post(
            f"{API_BASE_URL}/interviews",
            json=payload,
            headers=_get_headers(token),
            timeout=90,
        )
        data = _safe_json(resp, "Failed to start interview")
        if resp.status_code in (200, 201):
            return True, data
        detail = data.get("detail", "Failed to start interview") if isinstance(data, dict) else str(data)
        return False, detail
    except requests.exceptions.Timeout:
        return False, "Generation timed out while synthesizing RAG questions with Gemini. Please try again or select fewer questions."
    except requests.exceptions.ConnectionError:
        return False, "Could not connect to FastAPI Backend on http://127.0.0.1:8000. Please ensure 'start_platform.bat' or 'run_backend.bat' is running."
    except Exception as e:
        return False, str(e)


def get_interviews(token: str) -> Tuple[bool, Any]:
    try:
        resp = requests.get(
            f"{API_BASE_URL}/interviews",
            headers=_get_headers(token),
            timeout=10,
        )
        if resp.status_code == 200:
            return True, resp.json()
        return False, resp.json().get("detail", "Failed to load interview history")
    except Exception as e:
        return False, str(e)


def get_interview_detail(token: str, interview_id: int) -> Tuple[bool, Any]:
    try:
        resp = requests.get(
            f"{API_BASE_URL}/interviews/{interview_id}",
            headers=_get_headers(token),
            timeout=10,
        )
        if resp.status_code == 200:
            return True, resp.json()
        return False, resp.json().get("detail", "Failed to fetch interview")
    except Exception as e:
        return False, str(e)


def get_interview_questions(token: str, interview_id: int) -> Tuple[bool, Any]:
    try:
        resp = requests.get(
            f"{API_BASE_URL}/interviews/{interview_id}/questions",
            headers=_get_headers(token),
            timeout=10,
        )
        if resp.status_code == 200:
            return True, resp.json()
        return False, resp.json().get("detail", "Failed to fetch interview questions")
    except Exception as e:
        return False, str(e)


def submit_answer(token: str, interview_id: int, question_id: int, answer_text: str) -> Tuple[bool, Any]:
    try:
        resp = requests.post(
            f"{API_BASE_URL}/interviews/{interview_id}/questions/{question_id}/answer",
            json={"answer_text": answer_text},
            headers=_get_headers(token),
            timeout=60,
        )
        data = _safe_json(resp, "Failed to submit answer")
        if resp.status_code in (200, 201):
            return True, data
        detail = data.get("detail", "Failed to submit answer") if isinstance(data, dict) else str(data)
        return False, detail
    except requests.exceptions.Timeout:
        return False, "Evaluation timed out. Please try again."
    except Exception as e:
        return False, str(e)


def submit_audio_answer(
    token: str,
    interview_id: int,
    question_id: int,
    audio_bytes: bytes,
    filename: str = "audio.wav",
    content_type: str = "audio/wav",
) -> Tuple[bool, Any]:
    try:
        files = {"file": (filename, audio_bytes, content_type)}
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.post(
            f"{API_BASE_URL}/interviews/{interview_id}/questions/{question_id}/audio-answer",
            files=files,
            headers=headers,
            timeout=90,
        )
        data = _safe_json(resp, "Failed to evaluate audio answer")
        if resp.status_code in (200, 201):
            return True, data
        detail = data.get("detail", "Failed to evaluate audio answer") if isinstance(data, dict) else str(data)
        return False, detail
    except requests.exceptions.Timeout:
        return False, "Whisper transcription / evaluation timed out. Please try a shorter recording or type your answer."
    except Exception as e:
        return False, str(e)


def submit_follow_up(
    token: str,
    interview_id: int,
    question_id: int,
    follow_up_answer: str,
) -> Tuple[bool, Any]:
    try:
        resp = requests.post(
            f"{API_BASE_URL}/interviews/{interview_id}/questions/{question_id}/follow-up",
            json={"follow_up_answer": follow_up_answer},
            headers=_get_headers(token),
            timeout=60,
        )
        data = _safe_json(resp, "Failed to submit follow-up answer")
        if resp.status_code in (200, 201):
            return True, data
        detail = data.get("detail", "Failed to submit follow-up answer") if isinstance(data, dict) else str(data)
        return False, detail
    except requests.exceptions.Timeout:
        return False, "Follow-up evaluation timed out. Please retry."
    except Exception as e:
        return False, str(e)


def submit_follow_up_audio(
    token: str,
    interview_id: int,
    question_id: int,
    audio_bytes: bytes,
    filename: str = "follow_up.wav",
    content_type: str = "audio/wav",
) -> Tuple[bool, Any]:
    try:
        files = {"file": (filename, audio_bytes, content_type)}
        headers = _get_headers(token)
        headers.pop("Content-Type", None)
        resp = requests.post(
            f"{API_BASE_URL}/interviews/{interview_id}/questions/{question_id}/follow-up-audio",
            files=files,
            headers=headers,
            timeout=90,
        )
        data = _safe_json(resp, "Failed to submit follow-up audio")
        if resp.status_code in (200, 201):
            return True, data
        detail = data.get("detail", "Failed to submit follow-up audio") if isinstance(data, dict) else str(data)
        return False, detail
    except requests.exceptions.Timeout:
        return False, "Follow-up audio evaluation timed out. Please retry."
    except Exception as e:
        return False, str(e)


def complete_interview(token: str, interview_id: int) -> Tuple[bool, Any]:
    try:
        resp = requests.post(
            f"{API_BASE_URL}/interviews/{interview_id}/complete",
            headers=_get_headers(token),
            timeout=15,
        )
        data = _safe_json(resp, "Failed to complete interview")
        if resp.status_code == 200:
            return True, data
        detail = data.get("detail", "Failed to complete interview") if isinstance(data, dict) else str(data)
        return False, detail
    except Exception as e:
        return False, str(e)


def get_dashboard(token: str) -> Tuple[bool, Any]:
    try:
        resp = requests.get(
            f"{API_BASE_URL}/dashboard",
            headers=_get_headers(token),
            timeout=15,
        )
        data = _safe_json(resp, "Failed to fetch dashboard")
        if resp.status_code == 200:
            return True, data
        detail = data.get("detail", "Failed to fetch dashboard") if isinstance(data, dict) else str(data)
        return False, detail
    except Exception as e:
        return False, str(e)
