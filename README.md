# AI-Powered Interview & Placement Platform (Phase 1)

A clean, full-stack interview preparation and practice platform designed for engineering candidates. Built with **FastAPI** on the backend and **Streamlit** on the frontend, using **SQLite** with **SQLAlchemy ORM** and **Alembic** migrations.

---

## 🌟 Key Features

- **JWT Authentication**: Secure user registration, login, and token-based protected endpoints.
- **Student Profile**: Manage academic details, CGPA, graduation year, phone, LinkedIn, and GitHub links.
- **Resume Management**: Upload, inspect metadata, and delete candidate resumes.
- **Curated Subjects & Topics**: Explore interview subjects (Python, DBMS, Java, DSA) and specific sub-topics.
- **Interview Simulation**:
  - Start an interview session with targeted questions.
  - Interactive multi-line answer submission per question.
  - Question navigation and answer tracking.
  - Formal interview completion with timestamp recording.
- **Interview History**: Review past sessions, questions asked, and candidate answers.
- **Candidate Dashboard**: Real-time metrics on completed interviews, active sessions, and questions answered.
- **Automated Development Seeding**: Automatically seeds a test candidate account, subjects, topics, and interview questions on startup.

---

## 🛠️ Tech Stack

- **Backend**: FastAPI, Pydantic v2, Python-JOSE (JWT), PBKDF2-HMAC-SHA256 password hashing
- **Database**: SQLite, SQLAlchemy 2.0, Alembic
- **Frontend**: Streamlit, Requests
- **Server**: Uvicorn

---

## 📁 Project Structure

```text
├── alembic/                # Database migration scripts
│   ├── versions/           # Migration revisions
│   └── env.py              # Migration environment
├── app/                    # FastAPI Backend
│   ├── core/               # Configuration, security, dependencies
│   ├── database/           # DB engine, base, seed script
│   ├── models/             # SQLAlchemy ORM models
│   ├── routers/            # API endpoints (/api/v1/)
│   ├── schemas/            # Pydantic request/response schemas
│   └── main.py             # FastAPI entrypoint & router mounts
├── frontend/               # Streamlit Frontend
│   ├── api_client.py       # Backend REST API client
│   └── app.py              # Streamlit interactive UI
├── tests/                  # Automated integration tests
│   └── test_flow.py        # 14-step end-to-end test suite
├── uploads/                # Resume storage directory
├── alembic.ini             # Alembic configuration
├── requirements.txt        # Pinned Python dependencies
└── README.md
```

---

## ⚡ Default Test Credentials

For quick local testing, the following test account is automatically seeded into the database:

- **Email**: `test@example.com`
- **Password**: `Test@12345`

*(The Streamlit frontend also provides a 1-click **"⚡ Quick Fill Test Account"** button on the sign-in screen).*

---

## 🚀 How to Run

### 1. Clone the Repository & Set Up Virtual Environment

```bash
git clone https://github.com/Avanindera/Interview_prep_platform.git
cd Interview_prep_platform

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows (PowerShell):
.\venv\Scripts\Activate.ps1

# On Linux / macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Run Database Migrations

```bash
alembic upgrade head
```

### 3. Start the Backend (Terminal 1)

```bash
uvicorn app.main:app --reload
```

- **Backend API**: http://127.0.0.1:8000
- **Interactive Swagger Docs**: http://127.0.0.1:8000/docs

### 4. Start the Frontend (Terminal 2)

```bash
streamlit run frontend/app.py
```

- **Streamlit App**: http://localhost:8501

### 5. Run Automated Verification Tests (Optional)

With the backend running, execute:

```bash
python tests/test_flow.py
```
