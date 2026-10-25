import datetime
import os
import sys
import json
import re

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
    page_title="InterviewPrep - AI Technical & Speech Platform",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
        .main-header {
            font-size: 2.2rem;
            font-weight: 800;
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
            padding: 16px;
            text-align: center;
        }
        .metric-num {
            font-size: 1.8rem;
            font-weight: 700;
            color: #0F172A;
        }
        .metric-label {
            font-size: 0.85rem;
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
        .badge-good {
            background-color: #DCFCE7;
            color: #166534;
            padding: 4px 10px;
            border-radius: 8px;
            font-weight: 700;
            font-size: 0.85rem;
        }
        .badge-improve {
            background-color: #FEE2E2;
            color: #991B1B;
            padding: 4px 10px;
            border-radius: 8px;
            font-weight: 700;
            font-size: 0.85rem;
        }
        .eval-card {
            background: #FFFFFF;
            border: 1px solid #CBD5E1;
            border-radius: 12px;
            padding: 20px;
            margin-top: 15px;
            margin-bottom: 15px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.04);
        }
        .diagnostic-chip {
            display: inline-block;
            background: #F1F5F9;
            color: #334155;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 0.8rem;
            margin: 3px 2px;
            font-weight: 600;
        }
        .follow-up-card {
            background: linear-gradient(135deg, #FFFBEB 0%, #FEF3C7 100%);
            border: 1.5px solid #F59E0B;
            border-left: 6px solid #D97706;
            border-radius: 12px;
            padding: 22px;
            margin-bottom: 20px;
            box-shadow: 0 4px 12px rgba(217, 119, 6, 0.08);
        }
        .main-q-card {
            background: #F8FAFC;
            border: 1px solid #E2E8F0;
            border-left: 6px solid #2563EB;
            border-radius: 12px;
            padding: 22px;
            margin-bottom: 20px;
            box-shadow: 0 4px 12px rgba(37, 99, 235, 0.05);
        }
        .turn-stepper-pill {
            display: inline-block;
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: 700;
            margin-right: 8px;
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
        "uvicorn app.main:app --reload\n"
        "```"
    )

# ---------------------------------------------------------
# View: Authentication (Login / Register)
# ---------------------------------------------------------
if not st.session_state.token:
    st.markdown("<div class='main-header'>🎯 AI Technical & Speech Interview Platform</div>", unsafe_allow_html=True)
    st.markdown("<div class='sub-header'>Integrated Dual-Source RAG + AI Speech Delivery Evaluator</div>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        auth_tab1, auth_tab2 = st.tabs(["🔐 Sign In", "📝 Create Account"])

        with auth_tab1:
            st.write("### Login to your account")

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
                reg_name = st.text_input("Full Name", placeholder="Aryan Yadav")
                reg_email = st.text_input("Email Address", placeholder="candidate@example.com")
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
    st.markdown("### 🎯 InterviewPrep AI")
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
    st.markdown("**Platform Engines:**")
    st.caption("✅ Dual-Source Offline+Online RAG")
    st.caption("✅ OpenAI Whisper STT")
    st.caption("✅ Speech Delivery ML Evaluator")
    st.divider()
    if st.button("🚪 Logout", use_container_width=True):
        logout()


# ---------------------------------------------------------
# View 1: 📊 Dashboard
# ---------------------------------------------------------
if menu == "📊 Dashboard":
    st.markdown("<div class='main-header'>Candidate Analytics & Dashboard</div>", unsafe_allow_html=True)
    st.markdown("<div class='sub-header'>Comprehensive metrics on technical performance and speech delivery</div>", unsafe_allow_html=True)

    success, dash = api.get_dashboard(st.session_state.token)
    if not success:
        st.error(f"Unable to load dashboard data: {dash}")
    else:
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(
                f"""
                <div class='metric-card'>
                    <div class='metric-num'>{dash.get('total_interviews', 0)}</div>
                    <div class='metric-label'>Total Practice Sessions</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with c2:
            st.markdown(
                f"""
                <div class='metric-card'>
                    <div class='metric-num' style='color: #059669;'>{dash.get('completed_interviews', 0)}</div>
                    <div class='metric-label'>Sessions Completed</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with c3:
            st.markdown(
                f"""
                <div class='metric-card'>
                    <div class='metric-num' style='color: #2563EB;'>{dash.get('questions_answered', 0)}</div>
                    <div class='metric-label'>Answers Evaluated</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.write("")
        c4, c5 = st.columns(2)
        with c4:
            avg_score = dash.get("average_score")
            avg_str = f"{avg_score:.1f} / 10.0" if avg_score is not None else "N/A"
            st.markdown(
                f"""
                <div class='metric-card' style='border-left: 5px solid #2563EB;'>
                    <div class='metric-num' style='color: #1E3A8A;'>{avg_str}</div>
                    <div class='metric-label'>Average Technical Score (RAG Evaluator)</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with c5:
            pass_rate = dash.get("speech_pass_rate")
            pass_str = f"{pass_rate:.1f}%" if pass_rate is not None else "N/A"
            st.markdown(
                f"""
                <div class='metric-card' style='border-left: 5px solid #059669;'>
                    <div class='metric-num' style='color: #059669;'>{pass_str}</div>
                    <div class='metric-label'>Speech Delivery Fluency Pass Rate (AI Speech Evaluator)</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.write("---")
        st.subheader("Recent Practice Sessions")
        recent = dash.get("recent_interviews", [])
        if not recent:
            st.info("No practice sessions yet. Go to **Take Interview** to start your first session!")
        else:
            recent_table = []
            for item in recent:
                score_val = f"{item['score']:.1f}/10" if item.get("score") is not None else "Pending"
                recent_table.append(
                    {
                        "Session ID": item["id"],
                        "Topic / Subject": item["topic"] or item["subject"],
                        "Status": "✅ Completed" if item["status"] == "COMPLETED" else "⏳ In Progress",
                        "Score": score_val,
                        "Started At": format_dt(item["started_at"]),
                    }
                )
            st.dataframe(recent_table, use_container_width=True, hide_index=True)


# ---------------------------------------------------------
# View 2: 🎯 Take Interview
# ---------------------------------------------------------
elif menu == "🎯 Take Interview":
    st.markdown("<div class='main-header'>Interactive Interview Simulation</div>", unsafe_allow_html=True)
    st.markdown("<div class='sub-header'>Dynamic dual-source RAG question generation with speech & technical evaluation</div>", unsafe_allow_html=True)

    active_id = st.session_state.active_interview_id

    if not active_id:
        st.write("### Choose Interview Mode")
        mode_tab1, mode_tab2 = st.tabs(["🧠 AI Dynamic RAG Mode (Any Topic)", "📚 Curated Subjects Bank"])

        # TAB 1: DYNAMIC RAG INTERVIEW
        with mode_tab1:
            st.markdown(
                """
                **AI Dual-Source Knowledge Engine:**
                - Searches local offline FAISS vector database (DSA & System Design topics).
                - Discovers GitHub repositories and GeeksforGeeks articles dynamically if offline miss.
                - Synthesizes targeted interview questions with Gemini.
                """
            )

            # Quick suggestion buttons
            st.caption("Quick Topic Suggestions:")
            sug_col1, sug_col2, sug_col3, sug_col4 = st.columns(4)
            chosen_suggestion = None
            if sug_col1.button("BFS & Graphs"):
                chosen_suggestion = "Breadth First Search and Graph Traversal"
            if sug_col2.button("LRU Cache"):
                chosen_suggestion = "System Design: LRU Cache Implementation"
            if sug_col3.button("B+ Trees"):
                chosen_suggestion = "Database Indexing and B+ Trees"
            if sug_col4.button("Kafka Streaming"):
                chosen_suggestion = "Kafka Event-Driven Architecture and Sharding"

            default_topic = chosen_suggestion or st.session_state.get("custom_topic_input", "")
            custom_topic = st.text_input(
                "Enter Any Technical Topic or Keyword:",
                value=default_topic,
                placeholder="e.g. Trie Data Structure, Redis Distributed Locking, Binary Search Invariants...",
                key="custom_topic_input",
            )
            q_count = st.slider("Number of Questions:", min_value=1, max_value=5, value=3)

            if st.button("🚀 Launch AI Dynamic Interview", type="primary", use_container_width=True):
                topic_to_use = custom_topic.strip() or "Data Structures and Algorithms"
                with st.spinner(f"Retrieving knowledge & generating questions for '{topic_to_use}'..."):
                    start_ok, session_data = api.start_interview(
                        st.session_state.token,
                        generation_mode="RAG_DYNAMIC",
                        custom_topic=topic_to_use,
                        question_count=q_count,
                    )
                    if start_ok:
                        st.session_state.active_interview_id = session_data["id"]
                        st.session_state.current_question_index = 0
                        st.success(f"Dynamic Interview #{session_data['id']} ready!")
                        st.rerun()
                    else:
                        st.error(f"Error starting interview: {session_data}")

        # TAB 2: CURATED SUBJECTS
        with mode_tab2:
            st.write("Select from standard curated interview topics:")
            subj_ok, subjects = api.get_subjects(st.session_state.token)
            if not subj_ok or not subjects:
                st.warning("No subjects found.")
            else:
                subject_options = {s["name"]: s["id"] for s in subjects}
                selected_subject_name = st.selectbox("Select Subject", list(subject_options.keys()))
                selected_subject_id = subject_options[selected_subject_name]

                top_ok, topics = api.get_topics(st.session_state.token, selected_subject_id)
                topic_options = {"All Topics": None}
                if top_ok and topics:
                    for t in topics:
                        topic_options[t["name"]] = t["id"]

                selected_topic_name = st.selectbox("Select Topic (Optional)", list(topic_options.keys()))
                selected_topic_id = topic_options[selected_topic_name]

                if st.button("🚀 Start Curated Interview", type="primary", use_container_width=True):
                    with st.spinner("Preparing your interview session..."):
                        start_ok, session_data = api.start_interview(
                            st.session_state.token,
                            subject_id=selected_subject_id,
                            topic_id=selected_topic_id,
                            generation_mode="CURATED",
                        )
                        if start_ok:
                            st.session_state.active_interview_id = session_data["id"]
                            st.session_state.current_question_index = 0
                            st.success(f"Interview #{session_data['id']} started!")
                            st.rerun()
                        else:
                            st.error(f"Error starting interview: {session_data}")

    else:
        # ACTIVE INTERVIEW IN PROGRESS
        int_ok, session_data = api.get_interview_detail(st.session_state.token, active_id)
        if not int_ok or not session_data:
            st.error("Could not fetch active interview session.")
            if st.button("Reset Session"):
                st.session_state.active_interview_id = None
                st.rerun()
        else:
            questions = session_data.get("questions", [])
            total_q = len(questions)

            # Header info
            c_h1, c_h2, c_h3 = st.columns([3, 1, 1])
            with c_h1:
                display_topic = session_data.get("custom_topic") or session_data.get("topic_name") or session_data.get("subject_name")
                st.subheader(f"Session #{active_id}: {display_topic}")
                mode_str = session_data.get("generation_mode", "CURATED")
                st.caption(f"Mode: `{mode_str}` | Started: {format_dt(session_data.get('started_at'))}")
            with c_h2:
                overall_score = session_data.get("overall_score")
                if overall_score is not None:
                    st.metric("Session Score", f"{overall_score:.1f} / 10")
            with c_h3:
                if st.button("🛑 Exit Interview"):
                    st.session_state.active_interview_id = None
                    st.rerun()

            if not questions:
                st.warning("No questions found for this session.")
            else:
                curr_idx = st.session_state.current_question_index
                if curr_idx >= total_q:
                    curr_idx = total_q - 1
                    st.session_state.current_question_index = curr_idx

                current_q = questions[curr_idx]
                difficulty = current_q.get("difficulty", "MEDIUM").upper()
                ans = current_q.get("answer")
                is_answered = current_q.get("is_answered") and ans is not None
                follow_up_q = ans.get("follow_up_question") if ans else None
                has_fu_answered = bool(ans and ans.get("follow_up_answer"))

                # Compute progress factoring both main questions and follow-ups
                progress_step = 0.0
                if is_answered:
                    progress_step = 1.0 if has_fu_answered or not follow_up_q else 0.5
                progress_val = (curr_idx + progress_step) / total_q
                progress_val = min(1.0, max(0.0, progress_val))
                st.progress(progress_val)

                # Active Turn State management
                turn_state_key = f"turn_mode_{active_id}_{current_q['id']}"
                if turn_state_key not in st.session_state:
                    if is_answered and follow_up_q and not has_fu_answered:
                        st.session_state[turn_state_key] = "follow_up"
                    else:
                        st.session_state[turn_state_key] = "main"

                # Sub-header Stepper & Turn Switcher
                col_st1, col_st2 = st.columns([3, 2])
                with col_st1:
                    if st.session_state[turn_state_key] == "follow_up" and follow_up_q:
                        fu_status_pill = "✅ COMPLETED" if has_fu_answered else "🎯 ACTIVE PROBE"
                        st.markdown(
                            f"**Question {curr_idx + 1} of {total_q}** &nbsp;•&nbsp; <span class='turn-stepper-pill' style='background:#FEF3C7; color:#92400E; border:1px solid #F59E0B;'>STEP 2: ADAPTIVE FOLLOW-UP ({fu_status_pill})</span>",
                            unsafe_allow_html=True,
                        )
                    else:
                        main_status_pill = "✅ COMPLETED" if is_answered else "⏳ IN PROGRESS"
                        st.markdown(
                            f"**Question {curr_idx + 1} of {total_q}** &nbsp;•&nbsp; <span class='turn-stepper-pill' style='background:#DBEAFE; color:#1E40AF; border:1px solid #93C5FD;'>STEP 1: MAIN QUESTION ({main_status_pill})</span>",
                            unsafe_allow_html=True,
                        )

                with col_st2:
                    if is_answered and follow_up_q:
                        t_opts = ["1. Main Question", "2. Follow-Up Question"]
                        sel_idx = 1 if st.session_state[turn_state_key] == "follow_up" else 0
                        chosen_turn = st.radio(
                            "Turn Stepper:",
                            t_opts,
                            index=sel_idx,
                            horizontal=True,
                            key=f"radio_turn_{current_q['id']}",
                            label_visibility="collapsed",
                        )
                        target_turn = "follow_up" if "2." in chosen_turn else "main"
                        if target_turn != st.session_state[turn_state_key]:
                            st.session_state[turn_state_key] = target_turn
                            st.rerun()

                st.write("")

                # -------------------------------------------------------------
                # SCENARIO A: DISPLAY ADAPTIVE FOLLOW-UP QUESTION AS THE NEXT QUESTION
                # -------------------------------------------------------------
                if st.session_state[turn_state_key] == "follow_up" and follow_up_q:
                    # Prominent Follow-Up Question Card
                    st.markdown(
                        f"""
                        <div class='follow-up-card'>
                            <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;'>
                                <span class='diagnostic-chip' style='background:#FDE68A; color:#92400E; font-weight:700;'>
                                    🎯 ADAPTIVE FOLLOW-UP QUESTION (Turn 2 of 2)
                                </span>
                                <span style='color:#B45309; font-size:0.85rem; font-weight:600;'>
                                    Deep Dive on Question #{curr_idx + 1}
                                </span>
                            </div>
                            <h2 style='color: #78350F; font-weight: 800; font-size: 1.45rem; margin-top: 8px; margin-bottom: 12px; line-height: 1.4;'>
                                {follow_up_q}
                            </h2>
                            <div style='background: rgba(254, 243, 199, 0.7); border-radius: 8px; padding: 10px 14px; font-size: 0.9rem; color: #92400E;'>
                                <strong>💡 Interviewer's Context:</strong> {ans.get('misconception') if (ans.get('misconception') and ans.get('misconception') != 'None') else 'The interviewer is assessing your conceptual precision and ability to handle edge cases or foundational invariants.'}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                    # If not answered yet, show input options
                    if not has_fu_answered:
                        st.markdown("#### Submit Your Answer to the Follow-Up:")
                        fu_tab1, fu_tab2 = st.tabs(["🎤 Spoken Voice Answer (Microphone / Upload)", "✍️ Typed Written Answer"])

                        with fu_tab1:
                            st.write("Record or upload your spoken answer to this follow-up question. Whisper will transcribe it automatically.")
                            audio_rec_fu = None
                            if hasattr(st, "audio_input"):
                                audio_rec_fu = st.audio_input("Record follow-up response with microphone:", key=f"fu_audio_mic_{current_q['id']}")

                            audio_file_fu = st.file_uploader(
                                "Or upload recorded audio file (.wav, .mp3, .m4a, .ogg):",
                                type=["wav", "mp3", "m4a", "ogg"],
                                key=f"fu_audio_upload_{current_q['id']}",
                            )

                            target_audio_fu = audio_rec_fu or audio_file_fu
                            if target_audio_fu is not None:
                                st.audio(target_audio_fu)
                                if st.button("🎙️ Transcribe & Submit Spoken Follow-Up", type="primary", key=f"btn_fu_audio_{current_q['id']}"):
                                    with st.spinner("Transcribing audio & evaluating follow-up response..."):
                                        audio_bytes = target_audio_fu.read()
                                        fname = getattr(target_audio_fu, "name", "follow_up.wav")
                                        ctype = getattr(target_audio_fu, "type", "audio/wav")
                                        ok_fu, res_fu = api.submit_follow_up_audio(
                                            st.session_state.token,
                                            interview_id=active_id,
                                            question_id=current_q["question_id"],
                                            audio_bytes=audio_bytes,
                                            filename=fname,
                                            content_type=ctype,
                                        )
                                        if ok_fu:
                                            st.success("Spoken follow-up response submitted and evaluated!")
                                            st.rerun()
                                        else:
                                            st.error(f"Follow-up submission failed: {res_fu}")

                        with fu_tab2:
                            with st.form(key=f"follow_up_form_{current_q['id']}"):
                                fu_input = st.text_area(
                                    "Type your response to the follow-up question:",
                                    height=140,
                                    placeholder="Explain your approach, why this invariant matters, or how to handle this scenario...",
                                )
                                submit_fu = st.form_submit_button("🚀 Submit Follow-Up Answer", type="primary")
                                if submit_fu:
                                    if not fu_input.strip():
                                        st.error("Please provide an answer to the follow-up question.")
                                    else:
                                        with st.spinner("Analyzing follow-up response with RAG evaluator..."):
                                            ok_fu, res_fu = api.submit_follow_up(
                                                st.session_state.token,
                                                interview_id=active_id,
                                                question_id=current_q["question_id"],
                                                follow_up_answer=fu_input.strip(),
                                            )
                                            if ok_fu:
                                                st.success("Follow-up response evaluated successfully!")
                                                st.rerun()
                                            else:
                                                st.error(f"Follow-up submission failed: {res_fu}")

                    else:
                        # Follow-Up HAS been answered
                        st.markdown(
                            f"""
                            <div style='background:#F0FDF4; border:1px solid #BBF7D0; border-radius:8px; padding:14px 18px; margin-bottom:15px;'>
                                <div style='font-size:0.85rem; color:#166534; font-weight:700;'>YOUR FOLLOW-UP RESPONSE:</div>
                                <div style='font-size:1.05rem; color:#14532D; margin-top:4px;'>{ans.get('follow_up_answer')}</div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                        if ans.get("follow_up_feedback"):
                            st.markdown(
                                f"""
                                <div style='background:#EFF6FF; border:1px solid #BFDBFE; border-left:5px solid #3B82F6; border-radius:8px; padding:16px 18px; margin-bottom:20px;'>
                                    <div style='font-weight:700; color:#1E40AF; font-size:1.05rem; margin-bottom:6px;'>🎯 Interviewer Assessment on Follow-Up:</div>
                                    <div style='color:#1E3A8A; font-size:0.98rem; line-height:1.5;'>{ans['follow_up_feedback']}</div>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )

                        # Prominent Progression Action
                        if curr_idx < total_q - 1:
                            if st.button(f"Proceed to Question {curr_idx + 2} ➡️", type="primary", use_container_width=True, key=f"btn_next_q_{current_q['id']}"):
                                st.session_state.current_question_index += 1
                                next_q_id = questions[curr_idx + 1]["id"]
                                st.session_state[f"turn_mode_{active_id}_{next_q_id}"] = "main"
                                st.rerun()
                        else:
                            st.success("🎉 You have completed all questions and follow-ups in this interview!")
                            if st.button("🏁 Finalize & Complete Interview Session", type="primary", use_container_width=True, key=f"btn_fin_q_{current_q['id']}"):
                                with st.spinner("Compiling full session evaluation..."):
                                    comp_ok, comp_res = api.complete_interview(st.session_state.token, active_id)
                                    if comp_ok:
                                        st.balloons()
                                        st.session_state.active_interview_id = None
                                        st.session_state.current_question_index = 0
                                        st.rerun()

                    # Collapsible Reference to Main Question & Scoring
                    st.write("")
                    with st.expander(f"👀 Reference: Review Your Main Answer to Question #{curr_idx + 1}"):
                        st.markdown(f"**Main Question:** {current_q.get('question_text')}")
                        st.markdown(f"> **Your Answer:** {ans.get('answer_text')}")

                    with st.expander(f"📊 Question #{curr_idx + 1} Unified Assessment Report (Technical & Speech)"):
                        col_ev1, col_ev2 = st.columns(2)
                        with col_ev1:
                            tech_score = ans.get("technical_score")
                            tech_str = f"{tech_score:.1f} / 10.0" if tech_score is not None else "N/A"
                            verdict = ans.get("technical_verdict", "Evaluated")
                            st.markdown(
                                f"""
                                <div class='metric-card' style='text-align: left; border-left: 5px solid #2563EB;'>
                                    <div style='font-size: 0.9rem; color: #64748B; font-weight: 600;'>TECHNICAL SUBSTANCE</div>
                                    <div style='font-size: 1.6rem; font-weight: 800; color: #1E3A8A;'>{tech_str}</div>
                                    <div><span class='badge-completed'>{verdict}</span></div>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )
                        with col_ev2:
                            sp_verdict = ans.get("speech_verdict", "GOOD")
                            sp_conf = ans.get("speech_confidence", 85.0)
                            sp_class = "badge-good" if sp_verdict == "GOOD" else "badge-improve"
                            st.markdown(
                                f"""
                                <div class='metric-card' style='text-align: left; border-left: 5px solid #10B981;'>
                                    <div style='font-size: 0.9rem; color: #64748B; font-weight: 600;'>SPEECH DELIVERY FLUENCY</div>
                                    <div style='font-size: 1.6rem; font-weight: 800; color: #047857;'>{sp_conf:.1f}%</div>
                                    <div><span class='{sp_class}'>{sp_verdict}</span></div>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )
                        words_cnt_ref = len(ans.get("answer_text", "").split()) if ans.get("answer_text") else 0
                        st.markdown("#### 🗣️ Speech Delivery Diagnostics:")
                        st.markdown(
                            f"""
                            <span class='diagnostic-chip'>Words: {words_cnt_ref}</span>
                            <span class='diagnostic-chip'>Fillers: {ans.get('filler_count', 0)} ({ans.get('filler_density', 0.0):.1f}%)</span>
                            <span class='diagnostic-chip'>Tech Terms: {ans.get('technical_keyword_count', 0)} ({ans.get('technical_density', 0.0):.1f}%)</span>
                            <span class='diagnostic-chip'>Hedging Phrases: {ans.get('hedging_count', 0)}</span>
                            <span class='diagnostic-chip'>Lexical Diversity: {ans.get('lexical_diversity', 0.0):.2f}</span>
                            """,
                            unsafe_allow_html=True,
                        )
                        if ans.get("speech_feedback"):
                            st.info(f"💡 **Coaching Advice:** {ans['speech_feedback']}")
                        if ans.get("technical_feedback"):
                            st.markdown(ans["technical_feedback"])

                # -------------------------------------------------------------
                # SCENARIO B: DISPLAY MAIN QUESTION (TURN 1)
                # -------------------------------------------------------------
                else:
                    st.markdown(
                        f"""
                        <div class='main-q-card'>
                            <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;'>
                                <span class='diagnostic-chip' style='background:#E0E7FF; color:#3730A3; font-weight:700;'>
                                    📌 MAIN QUESTION (Turn 1 of 2) • {difficulty}
                                </span>
                                <span style='color:#64748B; font-size:0.85rem; font-weight:600;'>
                                    Question {curr_idx + 1} of {total_q}
                                </span>
                            </div>
                            <h2 style='color: #0F172A; font-weight: 700; font-size: 1.45rem; margin-top: 6px; line-height: 1.4;'>
                                {current_q.get('question_text')}
                            </h2>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                    if not is_answered:
                        st.markdown("#### Submit Your Response:")
                        ans_tab1, ans_tab2 = st.tabs(["🎤 Spoken Voice Answer (AI Speech Evaluator)", "✍️ Typed Written Answer"])

                        with ans_tab1:
                            st.write("Speak your answer naturally. The audio will be transcribed using OpenAI Whisper and analyzed for filler words, technical depth, and delivery fluency.")

                            audio_rec = None
                            if hasattr(st, "audio_input"):
                                audio_rec = st.audio_input("Record your answer with your microphone:", key=f"audio_mic_{current_q['id']}")

                            audio_file = st.file_uploader(
                                "Or upload recorded audio file (.wav, .mp3, .m4a, .ogg):",
                                type=["wav", "mp3", "m4a", "ogg"],
                                key=f"audio_upload_{current_q['id']}",
                            )

                            target_audio = audio_rec or audio_file
                            if target_audio is not None:
                                st.audio(target_audio)
                                if st.button("🎙️ Transcribe & Evaluate Spoken Answer", type="primary", key=f"btn_audio_{current_q['id']}"):
                                    with st.spinner("Transcribing audio with Whisper & running dual evaluation..."):
                                        audio_bytes = target_audio.read()
                                        fname = getattr(target_audio, "name", "recording.wav")
                                        ctype = getattr(target_audio, "type", "audio/wav")
                                        ok, res = api.submit_audio_answer(
                                            st.session_state.token,
                                            interview_id=active_id,
                                            question_id=current_q["question_id"],
                                            audio_bytes=audio_bytes,
                                            filename=fname,
                                            content_type=ctype,
                                        )
                                        if ok:
                                            # Automatically advance turn to the follow-up question!
                                            st.session_state[turn_state_key] = "follow_up"
                                            st.success("Spoken response evaluated! Moving to interviewer follow-up...")
                                            st.rerun()
                                        else:
                                            st.error(f"Evaluation failed: {res}")

                        with ans_tab2:
                            prev_text = ans.get("answer_text", "") if ans else ""
                            with st.form(key=f"text_form_{current_q['id']}"):
                                text_input = st.text_area(
                                    "Type your answer:",
                                    value=prev_text,
                                    height=150,
                                    placeholder="Explain the data structure, algorithm invariants, time/space complexity...",
                                )
                                submit_text = st.form_submit_button("💾 Evaluate Written Answer", type="primary")
                                if submit_text:
                                    if not text_input.strip():
                                        st.error("Please provide an answer before submitting.")
                                    else:
                                        with st.spinner("Analyzing answer with RAG Evaluator & Speech ML Model..."):
                                            ok, res = api.submit_answer(
                                                st.session_state.token,
                                                interview_id=active_id,
                                                question_id=current_q["question_id"],
                                                answer_text=text_input.strip(),
                                            )
                                            if ok:
                                                # Automatically advance turn to the follow-up question!
                                                st.session_state[turn_state_key] = "follow_up"
                                                st.success("Answer evaluated! Advancing to follow-up question...")
                                                st.rerun()
                                            else:
                                                st.error(f"Evaluation failed: {res}")

                    else:
                        # Main question answered
                        is_voice_ans = bool(ans.get("audio_path"))
                        ans_header = "🎙️ YOUR SPOKEN ANSWER (AI Transcribed):" if is_voice_ans else "✍️ YOUR WRITTEN ANSWER:"
                        badge_label = "Voice Recording" if is_voice_ans else "Typed Input"
                        badge_bg = "#DBEAFE" if is_voice_ans else "#F1F5F9"
                        badge_color = "#1E40AF" if is_voice_ans else "#475569"

                        st.markdown(
                            f"""
                            <div style='background:#F8FAFC; border:1px solid #E2E8F0; border-radius:8px; padding:16px; margin-bottom:15px;'>
                                <div style='display:flex; justify-content:space-between; align-items:center;'>
                                    <span style='font-size:0.85rem; color:#1E40AF; font-weight:700;'>{ans_header}</span>
                                    <span style='font-size:0.75rem; background:{badge_bg}; color:{badge_color}; padding:2px 8px; border-radius:12px; font-weight:600;'>{badge_label}</span>
                                </div>
                                <div style='font-size:1.02rem; color:#1E293B; margin-top:6px; line-height:1.5;'>{ans.get('answer_text')}</div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                        if follow_up_q:
                            st.markdown(
                                f"""
                                <div style='background: #FFFBEB; border: 1.5px solid #FCD34D; border-radius: 8px; padding: 16px; margin-bottom: 20px;'>
                                    <div style='font-weight: 700; color: #92400E; font-size: 1.05rem;'>⚡ Interviewer Follow-Up Available</div>
                                    <div style='color: #78350F; font-size: 0.92rem; margin-top: 3px;'>The interviewer has a tailored follow-up question regarding your answer.</div>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )
                            if st.button("👉 Proceed to Follow-Up Question (Turn 2) 🎯", type="primary", use_container_width=True, key=f"btn_go_fu_{current_q['id']}"):
                                st.session_state[turn_state_key] = "follow_up"
                                st.rerun()

                        # Detailed Dual Assessment Report
                        st.write("---")
                        st.markdown("### 📋 Unified Assessment Report")
                        col_ev1, col_ev2 = st.columns(2)
                        with col_ev1:
                            tech_score = ans.get("technical_score")
                            tech_str = f"{tech_score:.1f} / 10.0" if tech_score is not None else "N/A"
                            verdict = ans.get("technical_verdict", "Evaluated")
                            st.markdown(
                                f"""
                                <div class='metric-card' style='text-align: left; border-left: 5px solid #2563EB;'>
                                    <div style='font-size: 0.9rem; color: #64748B; font-weight: 600;'>TECHNICAL SUBSTANCE</div>
                                    <div style='font-size: 1.6rem; font-weight: 800; color: #1E3A8A;'>{tech_str}</div>
                                    <div><span class='badge-completed'>{verdict}</span></div>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )
                        with col_ev2:
                            sp_verdict = ans.get("speech_verdict", "GOOD")
                            sp_conf = ans.get("speech_confidence", 85.0)
                            sp_class = "badge-good" if sp_verdict == "GOOD" else "badge-improve"
                            st.markdown(
                                f"""
                                <div class='metric-card' style='text-align: left; border-left: 5px solid #10B981;'>
                                    <div style='font-size: 0.9rem; color: #64748B; font-weight: 600;'>SPEECH DELIVERY FLUENCY</div>
                                    <div style='font-size: 1.6rem; font-weight: 800; color: #047857;'>{sp_conf:.1f}%</div>
                                    <div><span class='{sp_class}'>{sp_verdict}</span></div>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )

                        words_cnt_main = len(ans.get("answer_text", "").split()) if ans.get("answer_text") else 0
                        st.markdown("#### 🗣️ Speech Delivery Diagnostics:")
                        st.markdown(
                            f"""
                            <span class='diagnostic-chip'>Words: {words_cnt_main}</span>
                            <span class='diagnostic-chip'>Fillers: {ans.get('filler_count', 0)} ({ans.get('filler_density', 0.0):.1f}%)</span>
                            <span class='diagnostic-chip'>Tech Terms: {ans.get('technical_keyword_count', 0)} ({ans.get('technical_density', 0.0):.1f}%)</span>
                            <span class='diagnostic-chip'>Hedging Phrases: {ans.get('hedging_count', 0)}</span>
                            <span class='diagnostic-chip'>Lexical Diversity: {ans.get('lexical_diversity', 0.0):.2f}</span>
                            """,
                            unsafe_allow_html=True,
                        )

                        if ans.get("speech_feedback"):
                            st.info(f"💡 **Coaching Advice:** {ans['speech_feedback']}")

                        if ans.get("technical_feedback"):
                            with st.expander("📖 View Full Technical Rubric Breakdown & Ideal Answer", expanded=True):
                                st.markdown(ans["technical_feedback"])

                # Navigation Buttons
                st.write("")
                col_p, col_j, col_n = st.columns([1, 2, 1])
                with col_p:
                    if curr_idx > 0:
                        if st.button("⬅️ Previous Question", use_container_width=True):
                            st.session_state.current_question_index -= 1
                            prev_q_id = questions[curr_idx - 1]["id"]
                            st.session_state[f"turn_mode_{active_id}_{prev_q_id}"] = "main"
                            st.rerun()
                with col_j:
                    q_labels = []
                    for i, q in enumerate(questions):
                        label = f"Q{i+1}"
                        q_ans = q.get("answer")
                        if q.get("is_answered"):
                            if q_ans and q_ans.get("follow_up_question"):
                                if q_ans.get("follow_up_answer"):
                                    label += " (Main ✅ + Follow-Up ✅)"
                                else:
                                    label += " (Main ✅ + Follow-Up 🎯)"
                            else:
                                label += " (Main ✅)"
                        else:
                            label += " (Unanswered)"
                        q_labels.append(label)

                    selected_q_label = st.selectbox(
                        "Jump to question:",
                        q_labels,
                        index=curr_idx,
                        key="jump_q_select",
                    )
                    target_idx = q_labels.index(selected_q_label)
                    if target_idx != curr_idx:
                        st.session_state.current_question_index = target_idx
                        tgt_q_id = questions[target_idx]["id"]
                        tgt_ans = questions[target_idx].get("answer")
                        if tgt_ans and tgt_ans.get("follow_up_question") and not tgt_ans.get("follow_up_answer"):
                            st.session_state[f"turn_mode_{active_id}_{tgt_q_id}"] = "follow_up"
                        else:
                            st.session_state[f"turn_mode_{active_id}_{tgt_q_id}"] = "main"
                        st.rerun()

                with col_n:
                    if curr_idx < total_q - 1:
                        if st.button("Next Question ➡️", use_container_width=True):
                            st.session_state.current_question_index += 1
                            nxt_q_id = questions[curr_idx + 1]["id"]
                            nxt_ans = questions[curr_idx + 1].get("answer")
                            if nxt_ans and nxt_ans.get("follow_up_question") and not nxt_ans.get("follow_up_answer"):
                                st.session_state[f"turn_mode_{active_id}_{nxt_q_id}"] = "follow_up"
                            else:
                                st.session_state[f"turn_mode_{active_id}_{nxt_q_id}"] = "main"
                            st.rerun()

                st.write("---")
                if st.button("🏁 Complete Interview Session", type="primary", use_container_width=True):
                    with st.spinner("Finalizing session and scoring..."):
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
    st.markdown("<div class='main-header'>Interview History & Performance Logs</div>", unsafe_allow_html=True)
    st.markdown("<div class='sub-header'>Detailed review of technical scores, speech metrics, and follow-ups</div>", unsafe_allow_html=True)

    success, interviews = api.get_interviews(st.session_state.token)
    if not success:
        st.error(f"Could not load interview history: {interviews}")
    elif not interviews:
        st.info("No interview history found yet. Head over to **Take Interview** to start your first session!")
    else:
        for item in interviews:
            is_done = item["status"] == "COMPLETED"
            status_badge = "✅ COMPLETED" if is_done else "⏳ IN PROGRESS"
            display_title = item.get("custom_topic") or item.get("topic_name") or item.get("subject_name", "General")
            score_text = f" | Score: {item['overall_score']:.1f}/10" if item.get("overall_score") is not None else ""

            with st.expander(f"Interview #{item['id']}: {display_title} ({status_badge}{score_text})"):
                c_a, c_b, c_c = st.columns(3)
                c_a.write(f"**Started:** {format_dt(item.get('started_at'))}")
                c_b.write(f"**Completed:** {format_dt(item.get('completed_at'))}")
                c_c.write(f"**Mode:** `{item.get('generation_mode', 'CURATED')}`")

                detail_ok, detail = api.get_interview_detail(st.session_state.token, item["id"])
                if detail_ok and detail.get("questions"):
                    st.write("#### Questions & Evaluated Responses:")
                    for q in detail["questions"]:
                        ans_obj = q.get("answer")
                        st.markdown(f"**Q{q['order']}: {q['question_text']}**")
                        if ans_obj:
                            st.markdown(f"> 💬 **Submitted Answer:** {ans_obj.get('answer_text')}")
                            c_sc1, c_sc2 = st.columns(2)
                            with c_sc1:
                                t_sc = ans_obj.get("technical_score")
                                st.write(f"🎯 **Technical Score:** `{t_sc if t_sc is not None else 'N/A'}/10` ({ans_obj.get('technical_verdict', '-')})")
                            with c_sc2:
                                st.write(f"🗣️ **Speech Delivery:** `{ans_obj.get('speech_verdict', '-')}` (Fillers: `{ans_obj.get('filler_density', 0.0):.1f}%`)")

                            if ans_obj.get("speech_feedback"):
                                st.caption(f"Speech feedback: {ans_obj.get('speech_feedback')}")
                            if ans_obj.get("follow_up_question"):
                                st.markdown(f"**Follow-up Question:** *{ans_obj.get('follow_up_question')}*")
                                if ans_obj.get("follow_up_answer"):
                                    st.markdown(f"> **Follow-up Answer:** {ans_obj.get('follow_up_answer')}")
                                    st.caption(f"Follow-up feedback: {ans_obj.get('follow_up_feedback', '')}")
                        else:
                            st.caption("*No answer submitted*")
                        st.divider()


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
                value=int(profile.get("graduation_year") or 2026),
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
