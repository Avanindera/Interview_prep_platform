import os
from typing import Any, Dict, List, Optional, Tuple
import requests

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000/api/v1")
HEALTH_URL = os.getenv("HEALTH_URL", "http://127.0.0.1:8000/")


def check_backend_online() -> bool:
    try:
        resp = requests.get(HEALTH_URL, timeout=2)
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
            timeout=5,
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
            timeout=5,
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
            timeout=5,
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
            timeout=5,
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
            timeout=5,
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
            timeout=5,
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
            timeout=10,
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
            timeout=5,
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
            timeout=5,
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
            timeout=5,
        )
        if resp.status_code == 200:
            return True, resp.json()
        return False, resp.json().get("detail", "Failed to load topics")
    except Exception as e:
        return False, str(e)


def start_interview(token: str, subject_id: int, topic_id: Optional[int] = None) -> Tuple[bool, Any]:
    try:
        payload = {"subject_id": subject_id}
        if topic_id:
            payload["topic_id"] = topic_id
        resp = requests.post(
            f"{API_BASE_URL}/interviews",
            json=payload,
            headers=_get_headers(token),
            timeout=5,
        )
        if resp.status_code in (200, 201):
            return True, resp.json()
        return False, resp.json().get("detail", "Failed to start interview")
    except Exception as e:
        return False, str(e)


def get_interviews(token: str) -> Tuple[bool, Any]:
    try:
        resp = requests.get(
            f"{API_BASE_URL}/interviews",
            headers=_get_headers(token),
            timeout=5,
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
            timeout=5,
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
            timeout=5,
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
            timeout=5,
        )
        if resp.status_code in (200, 201):
            return True, resp.json()
        return False, resp.json().get("detail", "Failed to submit answer")
    except Exception as e:
        return False, str(e)


def complete_interview(token: str, interview_id: int) -> Tuple[bool, Any]:
    try:
        resp = requests.post(
            f"{API_BASE_URL}/interviews/{interview_id}/complete",
            headers=_get_headers(token),
            timeout=5,
        )
        if resp.status_code == 200:
            return True, resp.json()
        return False, resp.json().get("detail", "Failed to complete interview")
    except Exception as e:
        return False, str(e)


def get_dashboard(token: str) -> Tuple[bool, Any]:
    try:
        resp = requests.get(
            f"{API_BASE_URL}/dashboard",
            headers=_get_headers(token),
            timeout=5,
        )
        if resp.status_code == 200:
            return True, resp.json()
        return False, resp.json().get("detail", "Failed to fetch dashboard")
    except Exception as e:
        return False, str(e)

