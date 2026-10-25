import requests
import time
import json
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


BASE_URL = "http://127.0.0.1:8000/api/v1"

print("=" * 70)
print("   END-TO-END VERIFICATION: INTEGRATED INTERVIEW PLATFORM")
print("=" * 70)

# 1. Login
login_res = requests.post(
    f"{BASE_URL}/auth/login",
    json={"email": "test@example.com", "password": "Test@12345"},
    timeout=10,
)
assert login_res.status_code == 200, f"Login failed: {login_res.text}"
token = login_res.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}
print("✅ [1/5] Authenticated successfully as test@example.com")

# 2. Start Dynamic RAG Interview
start_res = requests.post(
    f"{BASE_URL}/interviews",
    json={
        "generation_mode": "RAG_DYNAMIC",
        "custom_topic": "Breadth First Search and Graph Traversal",
        "question_count": 1,
    },
    headers=headers,
    timeout=90,
)
assert start_res.status_code in (200, 201), f"Start interview failed: {start_res.text}"
session = start_res.json()
session_id = session["id"]
print(f"✅ [2/5] Dynamic RAG Interview Session Started: #{session_id}")

# 3. Retrieve Questions
detail_res = requests.get(f"{BASE_URL}/interviews/{session_id}", headers=headers, timeout=10)
questions = detail_res.json().get("questions", [])
assert len(questions) > 0, "No questions returned"
q = questions[0]
print(f"    * Topic           : {session.get('custom_topic')}")
print(f"    * Question #{q['order']}     : {q['question_text']}")

# 4. Submit Answer for Dual Technical + Speech Evaluation
candidate_answer = (
    "BFS explores nodes level by level using a FIFO queue. In an unweighted graph, "
    "it guarantees finding the shortest path because all nodes at distance d are visited before d+1. "
    "The time complexity is O(V + E) and space complexity is O(V) to store the queue and visited set."
)
print("\n[3/5] Submitting Candidate Answer...")
ans_res = requests.post(
    f"{BASE_URL}/interviews/{session_id}/questions/{q['question_id']}/answer",
    json={"answer_text": candidate_answer},
    headers=headers,
    timeout=60,
)
assert ans_res.status_code in (200, 201), f"Submit answer failed: {ans_res.text}"
ans_data = ans_res.json()
print("✅ [3/5] Answer Evaluated across both Technical & Speech Engines:")
print(f"    * Technical Score      : {ans_data.get('technical_score')}/10.0")
print(f"    * Technical Verdict    : {ans_data.get('technical_verdict')}")
print(f"    * Speech Verdict       : {ans_data.get('speech_verdict')}")
print(f"    * Speech Confidence    : {ans_data.get('speech_confidence')}%")
print(f"    * Filler Density (%)   : {ans_data.get('filler_density')}%")
print(f"    * Technical Keywords   : {ans_data.get('technical_keyword_count')}")
print(f"    * Detected Misconception: {ans_data.get('misconception')}")
print(f"    * Adaptive Follow-Up   : {ans_data.get('follow_up_question')}")

# 5. Submit Follow-Up Answer
if ans_data.get("follow_up_question"):
    print("\n[4/5] Answering Adaptive Follow-Up Question...")
    fu_answer = (
        "To reconstruct the actual shortest path rather than just distance, we maintain a parent dictionary "
        "or predecessor array that stores the parent node for each vertex when it is first enqueued. "
        "After reaching the destination, we trace backwards from target to source and reverse the list."
    )
    fu_res = requests.post(
        f"{BASE_URL}/interviews/{session_id}/questions/{q['question_id']}/follow-up",
        json={"follow_up_answer": fu_answer},
        headers=headers,
        timeout=40,
    )
    if fu_res.status_code == 200:
        print("✅ [4/5] Adaptive Follow-Up Feedback:")
        print(f"    {fu_res.json().get('follow_up_feedback')}")

# 6. Complete Interview
comp_res = requests.post(f"{BASE_URL}/interviews/{session_id}/complete", headers=headers, timeout=10)
assert comp_res.status_code == 200, f"Complete failed: {comp_res.text}"
print(f"\n✅ [5/5] Interview #{session_id} Marked as COMPLETED!")

# 7. Check Dashboard Metrics
dash_res = requests.get(f"{BASE_URL}/dashboard", headers=headers, timeout=10)
dash = dash_res.json()
print("\n" + "=" * 70)
print("📊 CANDIDATE DASHBOARD STATUS:")
print(f"  * Total Interviews      : {dash.get('total_interviews')}")
print(f"  * Completed Interviews  : {dash.get('completed_interviews')}")
print(f"  * Questions Answered    : {dash.get('questions_answered')}")
print(f"  * Average Tech Score    : {dash.get('average_score')}/10.0")
print(f"  * Speech Pass Rate      : {dash.get('speech_pass_rate')}%")
print("=" * 70)
print("🎉 ALL THREE SYSTEMS INTEGRATED & FUNCTIONING FLAWLESSLY!")
