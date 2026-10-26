# 🎙️ AI Technical & Speech Interview Platform (v2.0)

An enterprise-grade, full-stack AI interview preparation web application integrating a **Tier-2 Dual-Source RAG Pipeline** with an **Adaptive Follow-Up Question Engine** and an **AI Communication & Speech Fluency Evaluation System**.

> 📘 **Complete Architecture & Viva Study Guide:** For an exhaustive, step-by-step technical breakdown of the RAG pipeline, FAISS vector indexing, Gemini Multimodal STT, and the Top 15 Viva Q&A, see [`COMPLETE_PROJECT_LEARNING_GUIDE.md`](COMPLETE_PROJECT_LEARNING_GUIDE.md).

---

## 🏗️ Architecture & Project Structure

The project has been restructured into a clean, modular layout separating the **Backend**, **Frontend**, **Upload Storage**, and **Research & Documentation**:

```text
interview web app/
├── backend/                               # FastAPI Application Core & Services
│   ├── app/
│   │   ├── core/                          # Environment config, JWT security, auth dependencies
│   │   ├── database/                      # SQLAlchemy database engine, base models, initial seed
│   │   ├── ml_models/                     # Trained ML model (interview_classifier.pkl)
│   │   ├── models/                        # ORM models (User, InterviewSession, Question, Answer)
│   │   ├── rag/                           # Dual-Source RAG Engine
│   │   │   ├── interviewer/               # Gemini AI prompt engine, evaluator, follow-up engine
│   │   │   ├── offline_db/                # Offline FAISS vector knowledge store (DSA, System Design)
│   │   │   ├── repo_cache/                # Cached repositories for GitHub retrieval
│   │   │   └── sources/                   # OfflineStore, GitHubRetriever, GFGRetriever, CacheManager
│   │   ├── routers/                       # REST API endpoints (interviews, auth, dashboard, etc.)
│   │   ├── schemas/                       # Pydantic v2 data validation schemas
│   │   ├── services/                      # Business logic layer
│   │   │   ├── rag_service.py             # RAG retrieval and question synthesis
│   │   │   ├── speech_service.py          # Multimodal Gemini STT, linguistic features, ML classifier
│   │   │   └── evaluation_service.py      # Unified dual evaluation orchestrator
│   │   └── main.py                        # FastAPI entry point & lifespan manager
│   ├── alembic/                           # Database migration versions
│   ├── alembic.ini                        # Alembic configuration
│   └── tests/                             # Unit & integration tests
│
├── frontend/                              # Streamlit Frontend Web Application
│   ├── app.py                             # Interactive Streamlit Web UI
│   └── api_client.py                      # REST API client library communicating with backend
│
├── uploads/                               # Centralized file storage
│   ├── audio/                             # Spoken voice recordings from candidate answers
│   └── resumes/                           # Uploaded candidate resumes
│
├── docs_and_research/                     # Archived research materials & notebooks
│   └── rag_demo_and_experiments/          # Technical architecture PDFs, SMOTE, Logistic Regression
│
├── .env                                   # Unified environment variables
├── .env.example                           # Example environment template
├── requirements.txt                       # Unified Python dependencies
├── run_platform.py                        # Python all-in-one background runner
├── start_platform.bat                     # 1-Click launcher for both backend & frontend
├── run_backend.bat                        # 1-Click launcher for FastAPI backend
├── run_frontend.bat                       # 1-Click launcher for Streamlit frontend
├── test_integrated_flow.py                # Automated end-to-end integration test suite
└── README.md                              # Complete platform documentation
```

---

## 🎯 Key Pipelines & Features

### 1. RAG Interview Pipeline & Flow
- **Tier-1 Offline Vector Knowledge Base**: Instant cosine similarity matching using FAISS and `all-MiniLM-L6-v2` embeddings over local curated topic databases.
- **Tier-2 Online Discovery Fallback**: Automatically discovers and cross-synthesizes candidate questions from GitHub technical interview repositories and GeeksforGeeks articles using Google Gemini.
- **Dynamic Topic Generation**: Candidates can type any technical topic (e.g. *"Breadth First Search and Graph Traversal"*, *"Distributed Cache Invalidation"*), generating grounded questions in real time.

### 2. Adaptive Follow-Up Question Flow (Interview-Grade Sequence)
- **Natural Conversation Flow**: When a candidate answers a question, the platform does not merely display a scorecard; it transitions seamlessly to the **Follow-Up Question as the next interview turn**.
- **Context-Bound Probe**: The follow-up question is derived directly from the candidate's answer and detected technical misconceptions (e.g., confusing a Queue with a Stack in BFS) or poses advanced architectural deep dives if answered correctly.
- **Dual Input Format for Follow-Ups**:
  - 🎤 **Spoken Voice Answer**: Candidates can answer follow-up questions directly with their microphone or audio upload, automatically transcribed using Google Gemini Multimodal Audio STT (with local Whisper fallback).
  - ✍️ **Typed Written Answer**: Candidates can also provide typed technical explanations.
- **Instant Stepper & Review**: Clear navigation pills indicate `Step 1: Main Question` vs `Step 2: Adaptive Follow-Up`, with convenient collapsible references to previous responses.

### 3. Speech & Communication Analysis Pipeline
- **Linguistic Diagnostics**: Extracts filler word density (`um`, `uh`, `like`), hedging phrases (`I think`, `maybe`), technical keyword density, and lexical diversity (type-token ratio).
- **ML Delivery Classifier**: Uses a pre-trained scikit-learn classifier (`interview_classifier.pkl`) to evaluate confidence and verbal delivery fluency (`GOOD` vs `NEEDS_IMPROVEMENT`).
- **Constructive Coaching**: Delivers targeted verbal coaching tips alongside technical rubric scores.

---

## 🚀 How to Run the Project

### Prerequisites
- Python 3.11 or Python 3.13 installed on your system.
- An internet connection for Gemini AI calls and online RAG synthesis.
- Ensure your Gemini API Key is set in `.env` (`GEMINI_API_KEY=...`).

---

### Method 1: 1-Click Unified Platform Launcher (Recommended)

Simply double-click:
```cmd
start_platform.bat
```
*Or run via command line from the project root:*
```cmd
python run_platform.py
```
This launcher automatically:
1. Cleans up ports `8000` and `8501` if already in use.
2. Starts the **FastAPI Backend** on `http://127.0.0.1:8000`.
3. Starts the **Streamlit Web App** on `http://localhost:8501`.
4. Opens both in unified real-time output.

---

### Method 2: Running Backend & Frontend in Separate Terminals

#### Terminal 1 — Backend API:
```cmd
run_backend.bat
```
*Or manually:*
```cmd
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
- API Base: `http://127.0.0.1:8000`
- Interactive Swagger Documentation: `http://127.0.0.1:8000/docs`

#### Terminal 2 — Streamlit Frontend:
```cmd
run_frontend.bat
```
*Or manually:*
```cmd
python -m streamlit run frontend/app.py --server.port 8501
```
- Web Application: `http://localhost:8501`

---

### Method 3: Automated End-to-End Integration Test

To verify that Authentication, Dynamic RAG question generation, Candidate Answer evaluation, Adaptive Follow-up question generation, and Follow-up feedback are all operating properly, run:
```cmd
python test_integrated_flow.py
```

---

## 🔑 Default Credentials

- **Test Email**: `test@example.com`
- **Password**: `Test@12345`
*(Or click **Register** in the sidebar to create a personal candidate profile).*
