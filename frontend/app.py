import datetime
import os
import sys

# Ensure both project root and frontend directory are in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CURRENT_DIR = os.path.abspath(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

try:
    import api_client as api
except ImportError:
    import frontend.api_client as api

import streamlit as st

# ---------------------------------------------------------
# Page Configuration & Styling
# ---------------------------------------------------------
st.set_page_config(
    page_title="InterviewPrep - AI & Placement Platform",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for modern styling
st.markdown(
    """
    <style>
        .main-header {
            font-size: 2.2rem;
            font-weight: 700;
            color: #1E3A8A;
            margin-bottom: 0.2rem;
        }
        .sub-header {
            font-size: 1.05rem;
            color: #64748B;
            margin-bottom: 1.5rem;
        }
        .metric-card {
            background: #F8FAFC;
            border: 1px solid #E2E8F0;
            border-radius: 12px;
            padding: 18px;
            text-align: center;
        }
        .metric-num {
            font-size: 2rem;
            font-weight: 700;
            color: #0F172A;
        }
        .metric-label {
            font-size: 0.9rem;
            color: #64748B;
            font-weight: 500;
        }
        .badge-completed {
            background-color: #DEF7EC;
            color: #03543F;
            padding: 4px 10px;
            border-radius: 9999px;
            font-weight: 600;
            font-size: 0.8rem;
        }
        .badge-progress {
            background-color: #FEF08A;
            color: #854D0E;
            padding: 4px 10px;
            border-radius: 9999px;
            font-weight: 600;
            font-size: 0.8rem;
        }
        .badge-easy {
            background-color: #DCFCE7;
            color: #166534;
            padding: 3px 8px;
            border-radius: 6px;
            font-size: 0.75rem;
            font-weight: 600;
        }
        .badge-medium {
            background-color: #FEF9C3;
            color: #854D0E;
            padding: 3px 8px;
            border-radius: 6px;
            font-size: 0.75rem;
            font-weight: 600;
        }
        .badge-hard {
            background-color: #FEE2E2;
            color: #991B1B;
            padding: 3px 8px;
            border-radius: 6px;
            font-size: 0.75rem;
            font-weight: 600;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------
# State Initialization
# ---------------------------------------------------------
if "token" not in st.session_state:
    st.session_state.token = None
if "user" not in st.session_state:
    st.session_state.user = None
if "active_interview_id" not in st.session_state:
    st.session_state.active_interview_id = None
if "current_question_index" not in st.session_state:
    st.session_state.current_question_index = 0


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------
def logout():
    st.session_state.token = None
    st.session_state.user = None
    st.session_state.active_interview_id = None
    st.session_state.current_question_index = 0
    st.rerun()


def format_dt(dt_str):
    if not dt_str:
        return "-"
    try:
        dt = datetime.datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y %I:%M %p")
    except Exception:
        return str(dt_str)


# ---------------------------------------------------------
# Check Backend Health
# ---------------------------------------------------------
backend_online = api.check_backend_online()
if not backend_online:
    st.error(
        "⚠️ **FastAPI Backend is Offline!**\n\n"
        "Please ensure the backend is running at `http://127.0.0.1:8000`. You can start it with:\n"
        "```powershell\n"
        ".\\venv\\Scripts\\uvicorn.exe app.main:app --reload\n"
        "```"
    )

# ---------------------------------------------------------
# View: Authentication (Login / Register)
# ---------------------------------------------------------
if not st.session_state.token:
    st.markdown("<div class='main-header'>🎯 AI Interview & Placement Platform</div>", unsafe_allow_html=True)
    st.markdown("<div class='sub-header'>Streamlit Client connected to FastAPI Backend</div>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        auth_tab1, auth_tab2 = st.tabs(["🔐 Sign In", "📝 Create Account"])

        with auth_tab1:
            st.write("### Login to your account")

            # Quick fill button for development testing
            if st.button("⚡ Quick Fill Test Account (`test@example.com`)", use_container_width=True):
                st.session_state["login_email"] = "test@example.com"
                st.session_state["login_password"] = "Test@12345"

            email_val = st.session_state.get("login_email", "")
            pwd_val = st.session_state.get("login_password", "")

            with st.form("login_form"):
                email = st.text_input("Email", value=email_val, placeholder="candidate@example.com")
                password = st.text_input("Password", value=pwd_val, type="password")
                submit_login = st.form_submit_button("Sign In", type="primary", use_container_width=True)

                if submit_login:
                    if not email or not password:
                        st.error("Please enter both email and password.")
                    else:
                        with st.spinner("Authenticating..."):
                            success, result = api.login(email.strip(), password)
                            if success:
                                token = result.get("access_token")
                                st.session_state.token = token
                                # Fetch user info
                                user_ok, user_data = api.get_current_user(token)
                                if user_ok:
                                    st.session_state.user = user_data
                                st.success("Signed in successfully!")
                                st.rerun()
                            else:
                                st.error(f"Login failed: {result}")

        with auth_tab2:
            st.write("### Register New Candidate")
            with st.form("register_form"):
                reg_name = st.text_input("Full Name", placeholder="Jane Doe")
                reg_email = st.text_input("Email Address", placeholder="jane@example.com")
                reg_password = st.text_input("Password", type="password", help="Must be at least 6 characters")
                submit_reg = st.form_submit_button("Create Account", type="primary", use_container_width=True)

                if submit_reg:
                    if not reg_name or not reg_email or not reg_password:
                        st.error("All fields are required.")
                    elif len(reg_password) < 6:
                        st.error("Password must be at least 6 characters.")
                    else:
                        with st.spinner("Registering..."):
                            success, result = api.register(reg_name.strip(), reg_email.strip(), reg_password)
                            if success:
                                st.success("Account created successfully! Please sign in using your credentials.")
                            else:
                                st.error(f"Registration failed: {result}")

    st.stop()


# ---------------------------------------------------------
# Sidebar Navigation (When Authenticated)
# ---------------------------------------------------------
user = st.session_state.user or {}
user_name = user.get("name", "Candidate")
user_email = user.get("email", "")

with st.sidebar:
    st.markdown("### 🎯 InterviewPrep")
    st.markdown(f"**Welcome, {user_name}!**")
    st.caption(f"📧 {user_email}")
    st.divider()

    menu = st.radio(
        "Navigation",
        [
            "📊 Dashboard",
            "🎯 Take Interview",
            "📜 Interview History",
            "👤 Student Profile",
            "📄 Resume Management",
        ],
        index=0,
    )

    st.divider()
    if st.button("🚪 Logout", use_container_width=True):
        logout()


# ---------------------------------------------------------
# View 1: 📊 Dashboard
# ---------------------------------------------------------
if menu == "📊 Dashboard":
    st.markdown("<div class='main-header'>Candidate Dashboard</div>", unsafe_allow_html=True)
    st.markdown("<div class='sub-header'>Real-time summary of your interview progress and practice history</div>", unsafe_allow_html=True)

    success, dash = api.get_dashboard(st.session_state.token)
    if not success:
        st.error(f"Unable to load dashboard data: {dash}")
    else:
        # Top Metrics
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(
                f"""
                <div class='metric-card'>
                    <div class='metric-num'>{dash.get('total_interviews', 0)}</div>
                    <div class='metric-label'>Total Interviews</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with c2:
            st.markdown(
                f"""
                <div class='metric-card'>
                    <div class='metric-num' style='color: #059669;'>{dash.get('completed_interviews', 0)}</div>
                    <div class='metric-label'>Completed</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with c3:
            st.markdown(
                f"""
                <div class='metric-card'>
                    <div class='metric-num' style='color: #D97706;'>{dash.get('in_progress_interviews', 0)}</div>
                    <div class='metric-label'>In Progress</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with c4:
            st.markdown(
                f"""
                <div class='metric-card'>
                    <div class='metric-num' style='color: #2563EB;'>{dash.get('questions_answered', 0)}</div>
                    <div class='metric-label'>Answers Submitted</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.write("---")

        # Recent Interviews Section
        st.subheader("Recent Interview Sessions")
        recent = dash.get("recent_interviews", [])
        if not recent:
            st.info("You haven't taken any interviews yet. Select **Take Interview** from the sidebar to begin!")
        else:
            recent_table = []
            for item in recent:
                status_badge = (
                    "✅ Completed" if item["status"] == "COMPLETED" else "⏳ In Progress"
                )
                recent_table.append(
                    {
                        "Session ID": item["id"],
                        "Subject": item["subject"],
                        "Topic": item["topic"] or "All Topics",
                        "Status": status_badge,
                        "Started At": format_dt(item["started_at"]),
                        "Completed At": format_dt(item["completed_at"]),
                    }
                )
            st.dataframe(recent_table, use_container_width=True, hide_index=True)


# ---------------------------------------------------------
# View 2: 🎯 Take Interview
# ---------------------------------------------------------
elif menu == "🎯 Take Interview":
    st.markdown("<div class='main-header'>Interview Simulation</div>", unsafe_allow_html=True)
    st.markdown("<div class='sub-header'>Practice questions curated for your technical topics</div>", unsafe_allow_html=True)

    # Check if an interview session is already active in session_state
    active_id = st.session_state.active_interview_id

    if not active_id:
        st.write("### Start a New Interview Session")
        st.write("Select a subject and topic to begin your practice session:")

        # Fetch subjects
        subj_ok, subjects = api.get_subjects(st.session_state.token)
        if not subj_ok or not subjects:
            st.warning("No interview subjects found. Please make sure database is seeded.")
        else:
            subject_options = {s["name"]: s["id"] for s in subjects}
            selected_subject_name = st.selectbox("Select Subject", list(subject_options.keys()))
            selected_subject_id = subject_options[selected_subject_name]

            # Fetch topics for selected subject
            top_ok, topics = api.get_topics(st.session_state.token, selected_subject_id)
            topic_options = {"All Topics": None}
            if top_ok and topics:
                for t in topics:
                    topic_options[t["name"]] = t["id"]

            selected_topic_name = st.selectbox("Select Topic (Optional)", list(topic_options.keys()))
            selected_topic_id = topic_options[selected_topic_name]

            st.write("")
            if st.button("🚀 Start Interview", type="primary", use_container_width=True):
                with st.spinner("Preparing your interview session..."):
                    start_ok, session_data = api.start_interview(
                        st.session_state.token,
                        subject_id=selected_subject_id,
                        topic_id=selected_topic_id,
                    )
                    if start_ok:
                        st.session_state.active_interview_id = session_data["id"]
                        st.session_state.current_question_index = 0
                        st.success(f"Interview #{session_data['id']} started!")
                        st.rerun()
                    else:
                        st.error(f"Error starting interview: {session_data}")

    else:
        # Active Interview Flow
        int_ok, session_data = api.get_interview_detail(st.session_state.token, active_id)
        if not int_ok or not session_data:
            st.error("Could not fetch active interview session.")
            if st.button("Reset Session"):
                st.session_state.active_interview_id = None
                st.rerun()
        else:
            questions = session_data.get("questions", [])
            total_q = len(questions)

            # Session info header
            col_info1, col_info2, col_info3 = st.columns([2, 1, 1])
            with col_info1:
                st.subheader(f"Session #{active_id}: {session_data.get('subject_name')} ({session_data.get('topic_name') or 'General'})")
            with col_info2:
                status_str = session_data.get("status", "IN_PROGRESS")
                st.write(f"Status: **{status_str}**")
            with col_info3:
                if st.button("🛑 Exit to Selection", help="Go back to subject selection"):
                    st.session_state.active_interview_id = None
                    st.rerun()

            if not questions:
                st.warning("No questions found for this interview session.")
            else:
                # Progress bar
                curr_idx = st.session_state.current_question_index
                if curr_idx >= total_q:
                    curr_idx = total_q - 1
                    st.session_state.current_question_index = curr_idx

                progress_val = (curr_idx + 1) / total_q
                st.progress(progress_val)
                st.write(f"**Question {curr_idx + 1} of {total_q}**")

                current_q = questions[curr_idx]

                # Question Card
                difficulty = current_q.get("difficulty", "EASY").upper()
                diff_class = f"badge-{difficulty.lower()}"
                st.markdown(
                    f"""
                    <div style='background: #F1F5F9; border-radius: 10px; padding: 18px; margin-bottom: 15px;'>
                        <span class='{diff_class}'>{difficulty}</span>
                        <h4 style='margin-top: 10px; color: #0F172A;'>{current_q.get('question_text')}</h4>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                # Existing Answer if previously submitted
                existing_ans = current_q.get("answer")
                prev_text = existing_ans.get("answer_text", "") if existing_ans else ""

                if current_q.get("is_answered"):
                    st.info(f"✅ Previously answered at {format_dt(existing_ans.get('submitted_at'))}")

                with st.form(key=f"answer_form_{current_q['id']}"):
                    user_answer = st.text_area(
                        "Your Answer:",
                        value=prev_text,
                        height=140,
                        placeholder="Type your answer clearly here...",
                    )
                    submit_ans = st.form_submit_button("💾 Save / Update Answer", type="primary")

                    if submit_ans:
                        if not user_answer.strip():
                            st.error("Please provide an answer before submitting.")
                        else:
                            with st.spinner("Submitting answer..."):
                                ans_ok, ans_res = api.submit_answer(
                                    st.session_state.token,
                                    interview_id=active_id,
                                    question_id=current_q["question_id"],
                                    answer_text=user_answer.strip(),
                                )
                                if ans_ok:
                                    st.success("Answer saved successfully!")
                                    # Auto advance if not on last question
                                    if curr_idx < total_q - 1:
                                        st.session_state.current_question_index += 1
                                    st.rerun()
                                else:
                                    st.error(f"Failed to submit: {ans_res}")

                # Navigation between questions
                st.write("")
                col_prev, col_nav, col_next = st.columns([1, 2, 1])
                with col_prev:
                    if curr_idx > 0:
                        if st.button("⬅️ Previous Question", use_container_width=True):
                            st.session_state.current_question_index -= 1
                            st.rerun()
                with col_nav:
                    q_labels = [f"Q{i+1}" + (" ✅" if q.get("is_answered") else "") for i, q in enumerate(questions)]
                    selected_q_label = st.selectbox(
                        "Jump to question:",
                        q_labels,
                        index=curr_idx,
                        key="jump_q_select",
                    )
                    target_idx = q_labels.index(selected_q_label)
                    if target_idx != curr_idx:
                        st.session_state.current_question_index = target_idx
                        st.rerun()
                with col_next:
                    if curr_idx < total_q - 1:
                        if st.button("Next Question ➡️", use_container_width=True):
                            st.session_state.current_question_index += 1
                            st.rerun()

                st.write("---")
                # Complete Interview Action
                st.write("### Finish Practice Session")
                if st.button("🏁 Complete Interview Session", type="primary", use_container_width=True):
                    with st.spinner("Finalizing session..."):
                        comp_ok, comp_res = api.complete_interview(st.session_state.token, active_id)
                        if comp_ok:
                            st.balloons()
                            st.success(f"🎉 Interview #{active_id} marked as COMPLETED!")
                            st.session_state.active_interview_id = None
                            st.session_state.current_question_index = 0
                            st.rerun()
                        else:
                            st.error(f"Failed to complete interview: {comp_res}")


# ---------------------------------------------------------
# View 3: 📜 Interview History
# ---------------------------------------------------------
elif menu == "📜 Interview History":
    st.markdown("<div class='main-header'>Interview History</div>", unsafe_allow_html=True)
    st.markdown("<div class='sub-header'>Review all your previous interview sessions and submitted answers</div>", unsafe_allow_html=True)

    success, interviews = api.get_interviews(st.session_state.token)
    if not success:
        st.error(f"Could not load interview history: {interviews}")
    elif not interviews:
        st.info("No interview history found yet. Head over to **Take Interview** to start your first session!")
    else:
        for item in interviews:
            is_done = item["status"] == "COMPLETED"
            status_badge = "✅ COMPLETED" if is_done else "⏳ IN PROGRESS"
            subj_title = f"{item.get('subject_name', 'General')} — {item.get('topic_name') or 'All Topics'}"

            with st.expander(f"Interview #{item['id']}: {subj_title} ({status_badge})"):
                c_a, c_b, c_c = st.columns(3)
                c_a.write(f"**Started:** {format_dt(item.get('started_at'))}")
                c_b.write(f"**Completed:** {format_dt(item.get('completed_at'))}")
                c_c.write(f"**Status:** {status_badge}")

                # Fetch detailed session questions & answers
                detail_ok, detail = api.get_interview_detail(st.session_state.token, item["id"])
                if detail_ok and detail.get("questions"):
                    st.write("#### Questions & Answers:")
                    for q in detail["questions"]:
                        ans_obj = q.get("answer")
                        ans_text = ans_obj.get("answer_text") if ans_obj else "*No answer submitted*"
                        st.markdown(
                            f"""
                            **Q{q['order']}: {q['question_text']}**  
                            `Difficulty: {q.get('difficulty', 'EASY')}`  
                            > 💬 **Submitted Answer:** {ans_text}
                            """
                        )
                st.write("")


# ---------------------------------------------------------
# View 4: 👤 Student Profile
# ---------------------------------------------------------
elif menu == "👤 Student Profile":
    st.markdown("<div class='main-header'>Student Profile</div>", unsafe_allow_html=True)
    st.markdown("<div class='sub-header'>Keep your academic and contact details up-to-date</div>", unsafe_allow_html=True)

    success, profile = api.get_profile(st.session_state.token)
    if not success:
        st.error(f"Could not load profile: {profile}")
        profile = {}

    with st.form("profile_form"):
        col1, col2 = st.columns(2)
        with col1:
            college = st.text_input("College / University", value=profile.get("college") or "")
            branch = st.text_input("Branch / Major", value=profile.get("branch") or "")
            grad_year = st.number_input(
                "Graduation Year",
                min_value=2000,
                max_value=2035,
                value=int(profile.get("graduation_year") or 2025),
                step=1,
            )
            cgpa = st.number_input(
                "CGPA (out of 10.0)",
                min_value=0.0,
                max_value=10.0,
                value=float(profile.get("cgpa") or 8.5),
                step=0.05,
            )
        with col2:
            phone = st.text_input("Phone Number", value=profile.get("phone") or "")
            linkedin = st.text_input("LinkedIn Profile URL", value=profile.get("linkedin") or "")
            github = st.text_input("GitHub Profile URL", value=profile.get("github") or "")

        submit_profile = st.form_submit_button("💾 Save Profile Changes", type="primary")

        if submit_profile:
            payload = {
                "college": college.strip() or None,
                "branch": branch.strip() or None,
                "graduation_year": int(grad_year) if grad_year else None,
                "cgpa": float(cgpa) if cgpa else None,
                "phone": phone.strip() or None,
                "linkedin": linkedin.strip() or None,
                "github": github.strip() or None,
            }
            with st.spinner("Updating profile..."):
                update_ok, updated = api.update_profile(st.session_state.token, payload)
                if update_ok:
                    st.success("Profile updated successfully!")
                    st.rerun()
                else:
                    st.error(f"Failed to update profile: {updated}")


# ---------------------------------------------------------
# View 5: 📄 Resume Management
# ---------------------------------------------------------
elif menu == "📄 Resume Management":
    st.markdown("<div class='main-header'>Resume Management</div>", unsafe_allow_html=True)
    st.markdown("<div class='sub-header'>Upload, view, and manage your resumes stored in the platform</div>", unsafe_allow_html=True)

    # Upload Section
    st.write("### Upload a Resume")
    uploaded_file = st.file_uploader("Choose a resume file", type=["pdf", "docx", "txt"])

    if uploaded_file is not None:
        if st.button("📤 Upload Resume", type="primary"):
            with st.spinner("Uploading to server..."):
                file_bytes = uploaded_file.read()
                content_type = uploaded_file.type or "application/octet-stream"
                up_ok, up_res = api.upload_resume(
                    st.session_state.token,
                    file_bytes=file_bytes,
                    filename=uploaded_file.name,
                    content_type=content_type,
                )
                if up_ok:
                    st.success(f"Resume '{uploaded_file.name}' uploaded successfully!")
                    st.rerun()
                else:
                    st.error(f"Failed to upload: {up_res}")

    st.write("---")
    st.write("### Uploaded Resumes")
    res_ok, resumes = api.get_resumes(st.session_state.token)
    if not res_ok:
        st.error(f"Could not load resumes: {resumes}")
    elif not resumes:
        st.info("No resumes uploaded yet.")
    else:
        for r in resumes:
            size_kb = round(r.get("file_size", 0) / 1024, 2)
            c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
            with c1:
                st.write(f"📄 **{r.get('filename')}**")
            with c2:
                st.write(f"Size: `{size_kb} KB`")
            with c3:
                st.write(f"Uploaded: {format_dt(r.get('uploaded_at'))}")
            with c4:
                if st.button("🗑️ Delete", key=f"del_res_{r['id']}"):
                    with st.spinner("Deleting..."):
                        del_ok, del_res = api.delete_resume(st.session_state.token, r["id"])
                        if del_ok:
                            st.success("Deleted!")
                            st.rerun()
                        else:
                            st.error(f"Failed to delete: {del_res}")
            st.divider()

