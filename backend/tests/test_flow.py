import io
import json
import mimetypes
import sys
import uuid
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE_URL = "http://127.0.0.1:8000"


def make_request(method, path, data=None, headers=None, is_json=True):
    url = f"{BASE_URL}{path}"
    headers = headers or {}
    encoded_data = None

    if data is not None:
        if is_json:
            headers["Content-Type"] = "application/json"
            encoded_data = json.dumps(data).encode("utf-8")
        elif isinstance(data, dict):
            encoded_data = urlencode(data).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        elif isinstance(data, bytes):
            encoded_data = data

    req = Request(url, data=encoded_data, headers=headers, method=method)
    try:
        with urlopen(req) as resp:
            status_code = resp.status
            content = resp.read().decode("utf-8")
            try:
                parsed = json.loads(content)
            except Exception:
                parsed = content
            return status_code, parsed
    except HTTPError as e:
        err_body = e.read().decode("utf-8")
        try:
            parsed_err = json.loads(err_body)
        except Exception:
            parsed_err = err_body
        return e.code, parsed_err


def encode_multipart_formdata(fields, files):
    boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
    buf = io.BytesIO()

    for name, value in fields.items():
        buf.write(f"--{boundary}\r\n".encode("utf-8"))
        buf.write(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
        buf.write(f"{value}\r\n".encode("utf-8"))

    for name, (filename, file_bytes, content_type) in files.items():
        buf.write(f"--{boundary}\r\n".encode("utf-8"))
        buf.write(
            f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode("utf-8")
        )
        buf.write(f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"))
        buf.write(file_bytes)
        buf.write(b"\r\n")

    buf.write(f"--{boundary}--\r\n".encode("utf-8"))
    content_type = f"multipart/form-data; boundary={boundary}"
    return content_type, buf.getvalue()


def run_full_flow_test():
    print("==================================================")
    print("STARTING END-TO-END FLOW VERIFICATION")
    print("==================================================")

    # 1. Health check & Docs
    status, res = make_request("GET", "/")
    assert status == 200, f"Root failed: {status} {res}"
    print("[PASS] Root endpoint / -> 200 OK")

    status, res = make_request("GET", "/docs")
    assert status == 200, f"/docs failed: {status}"
    print("[PASS] Swagger /docs endpoint -> 200 OK")

    # Step 1: Login using test account (JSON)
    print("\n--- Step 1: Login with Test Account (JSON) ---")
    status, login_res = make_request(
        "POST",
        "/api/v1/auth/login",
        data={"email": "test@example.com", "password": "Test@12345"},
    )
    assert status == 200, f"Login failed: {status} {login_res}"
    assert "access_token" in login_res, "No access token in response"
    token = login_res["access_token"]
    auth_header = {"Authorization": f"Bearer {token}"}
    print(f"[PASS] JSON Login succeeded! Access token obtained.")

    # Step 1b: Verify OAuth2 form login (for Swagger Authorize button)
    print("\n--- Step 1b: Login with Test Account (Form Data for Swagger Authorize) ---")
    status, form_login_res = make_request(
        "POST",
        "/api/v1/auth/login",
        data={"username": "test@example.com", "password": "Test@12345"},
        is_json=False,
    )
    assert status == 200, f"Form login failed: {status} {form_login_res}"
    assert "access_token" in form_login_res
    print("[PASS] Form Login (Swagger Authorize) succeeded!")

    # Step 2: Verify current user
    print("\n--- Step 2: View Current User (/auth/me) ---")
    status, me_res = make_request("GET", "/api/v1/auth/me", headers=auth_header)
    assert status == 200, f"Auth me failed: {status} {me_res}"
    assert me_res["email"] == "test@example.com"
    print(f"[PASS] Current user: {me_res['name']} ({me_res['email']})")

    # Step 3: View profile
    print("\n--- Step 3: View Student Profile ---")
    status, profile_res = make_request("GET", "/api/v1/profile", headers=auth_header)
    assert status == 200, f"Get profile failed: {status} {profile_res}"
    print(f"[PASS] Profile retrieved: College={profile_res.get('college')}, CGPA={profile_res.get('cgpa')}")

    # Step 4: Update profile
    print("\n--- Step 4: Update Student Profile ---")
    status, updated_profile = make_request(
        "PUT",
        "/api/v1/profile",
        data={
            "college": "Apex Institute of Tech",
            "branch": "Artificial Intelligence",
            "graduation_year": 2026,
            "cgpa": 9.1,
            "phone": "+91-9988776655",
            "linkedin": "https://linkedin.com/in/test-updated",
            "github": "https://github.com/test-updated",
        },
        headers=auth_header,
    )
    assert status == 200, f"Update profile failed: {status} {updated_profile}"
    assert updated_profile["college"] == "Apex Institute of Tech"
    assert updated_profile["cgpa"] == 9.1
    print(f"[PASS] Profile updated successfully: {updated_profile['college']}, CGPA={updated_profile['cgpa']}")

    # Step 5: Resume upload
    print("\n--- Step 5: Upload Resume ---")
    sample_resume_content = b"%PDF-1.4 Mock resume content for testing."
    content_type, body = encode_multipart_formdata(
        fields={},
        files={"file": ("sample_resume.pdf", sample_resume_content, "application/pdf")},
    )
    headers = {"Authorization": f"Bearer {token}", "Content-Type": content_type}
    status, resume_res = make_request("POST", "/api/v1/resumes", data=body, headers=headers, is_json=False)
    assert status == 201, f"Resume upload failed: {status} {resume_res}"
    resume_id = resume_res["id"]
    print(f"[PASS] Resume uploaded: ID={resume_id}, filename={resume_res['filename']}, size={resume_res['file_size']} bytes")

    # Step 6: View resumes
    print("\n--- Step 6: View Resumes ---")
    status, resumes_list = make_request("GET", "/api/v1/resumes", headers=auth_header)
    assert status == 200, f"Get resumes failed: {status} {resumes_list}"
    assert any(r["id"] == resume_id for r in resumes_list), "Uploaded resume not found in list"
    print(f"[PASS] Resumes list retrieved: Total resumes = {len(resumes_list)}")

    # Step 7: View subjects
    print("\n--- Step 7: View Subjects ---")
    status, subjects = make_request("GET", "/api/v1/subjects", headers=auth_header)
    assert status == 200, f"Get subjects failed: {status} {subjects}"
    assert len(subjects) > 0, "No subjects found"
    python_subject = next((s for s in subjects if s["name"] == "Python"), subjects[0])
    subject_id = python_subject["id"]
    print(f"[PASS] Subjects retrieved: Found {len(subjects)} subjects. Selected '{python_subject['name']}' (ID={subject_id})")

    # Step 8: View topics for subject
    print("\n--- Step 8: View Topics for Subject ---")
    status, topics = make_request("GET", f"/api/v1/subjects/{subject_id}/topics", headers=auth_header)
    assert status == 200, f"Get topics failed: {status} {topics}"
    assert len(topics) > 0, "No topics found"
    topic_id = topics[0]["id"]
    print(f"[PASS] Topics retrieved: Found {len(topics)} topics. Selected '{topics[0]['name']}' (ID={topic_id})")

    # Step 9: Start an interview
    print("\n--- Step 9: Start Interview ---")
    status, interview_res = make_request(
        "POST",
        "/api/v1/interviews",
        data={"subject_id": subject_id, "topic_id": topic_id},
        headers=auth_header,
    )
    assert status == 201, f"Start interview failed: {status} {interview_res}"
    interview_id = interview_res["id"]
    print(f"[PASS] Interview created: ID={interview_id}, Status={interview_res['status']}")

    # Step 10: Get interview questions
    print("\n--- Step 10: Get Interview Questions ---")
    status, questions = make_request(
        "GET",
        f"/api/v1/interviews/{interview_id}/questions",
        headers=auth_header,
    )
    assert status == 200, f"Get questions failed: {status} {questions}"
    assert len(questions) > 0, "No questions assigned to interview"
    print(f"[PASS] Retrieved {len(questions)} interview questions:")
    for q in questions:
        print(f"       Q{q['order']}: {q['question_text']}")

    # Step 11: Submit answers
    print("\n--- Step 11: Submit Answers ---")
    first_q = questions[0]
    answer_text = "Inheritance allows a class to inherit attributes and methods from another class, promoting code reusability."
    status, ans_res = make_request(
        "POST",
        f"/api/v1/interviews/{interview_id}/questions/{first_q['question_id']}/answer",
        data={"answer_text": answer_text},
        headers=auth_header,
    )
    assert status == 201, f"Submit answer failed: {status} {ans_res}"
    assert ans_res["answer_text"] == answer_text
    print(f"[PASS] Answer submitted for Question #{first_q['order']}: ID={ans_res['id']}")

    # Step 12: Complete interview
    print("\n--- Step 12: Complete Interview ---")
    status, completed_res = make_request(
        "POST",
        f"/api/v1/interviews/{interview_id}/complete",
        headers=auth_header,
    )
    assert status == 200, f"Complete interview failed: {status} {completed_res}"
    assert completed_res["status"] == "COMPLETED"
    assert completed_res["completed_at"] is not None
    print(f"[PASS] Interview #{interview_id} completed at {completed_res['completed_at']}")

    # Step 13: View interview history
    print("\n--- Step 13: View Interview History ---")
    status, history = make_request("GET", "/api/v1/interviews", headers=auth_header)
    assert status == 200, f"Get interview history failed: {status} {history}"
    assert any(i["id"] == interview_id for i in history), "Interview not found in history"
    print(f"[PASS] Interview history contains {len(history)} session(s)")

    # Step 14: View dashboard
    print("\n--- Step 14: View Dashboard ---")
    status, dashboard_res = make_request("GET", "/api/v1/dashboard", headers=auth_header)
    assert status == 200, f"Get dashboard failed: {status} {dashboard_res}"
    assert dashboard_res["total_interviews"] >= 1
    assert dashboard_res["completed_interviews"] >= 1
    assert dashboard_res["questions_answered"] >= 1
    print(f"[PASS] Dashboard data verified:")
    print(f"       Total Interviews:     {dashboard_res['total_interviews']}")
    print(f"       Completed:            {dashboard_res['completed_interviews']}")
    print(f"       In Progress:          {dashboard_res['in_progress_interviews']}")
    print(f"       Questions Answered:   {dashboard_res['questions_answered']}")
    print(f"       Recent Interviews:    {len(dashboard_res['recent_interviews'])}")

    # Clean up uploaded resume
    print("\n--- Cleanup: Delete uploaded resume ---")
    status, del_res = make_request("DELETE", f"/api/v1/resumes/{resume_id}", headers=auth_header)
    assert status == 200, f"Delete resume failed: {status} {del_res}"
    print("[PASS] Resume deleted successfully.")

    # User registration check
    print("\n--- Additional Check: User Registration ---")
    new_email = f"student_{uuid.uuid4().hex[:6]}@example.com"
    status, reg_res = make_request(
        "POST",
        "/api/v1/auth/register",
        data={"name": "New Candidate", "email": new_email, "password": "Password@123"},
    )
    assert status == 201, f"Registration failed: {status} {reg_res}"
    print(f"[PASS] Successfully registered new candidate: {new_email}")

    # Login with new candidate
    status, new_login = make_request(
        "POST",
        "/api/v1/auth/login",
        data={"email": new_email, "password": "Password@123"},
    )
    assert status == 200, f"New candidate login failed: {status} {new_login}"
    new_token = new_login["access_token"]
    new_auth_header = {"Authorization": f"Bearer {new_token}"}

    # Verify candidate dashboard is clean (0 interviews)
    status, new_dash = make_request("GET", "/api/v1/dashboard", headers=new_auth_header)
    assert status == 200
    assert new_dash["total_interviews"] == 0
    print("[PASS] Candidate isolation verified: Dashboard starts clean at 0 interviews.")

    print("\n==================================================")
    print("ALL 14 STEPS OF THE USER FLOW COMPLETED SUCCESSFULLY!")
    print("==================================================")


if __name__ == "__main__":
    run_full_flow_test()

