# AI-Powered Interview RAG Platform

> **Minor Project Proof-of-Concept**  
> An autonomous RAG (Retrieval-Augmented Generation) interview platform that dynamically discovers public GitHub interview repositories for any technical topic, indexes their content using FAISS vector search, formulates context-grounded interview questions, and evaluates candidate answers using Gemini 2.5 / 3.6 Flash.

---

## 🎯 Architecture Overview

Unlike static RAG systems that rely on hardcoded datasets, Kaggle downloads, or fixed web scrapers, this platform performs **Dynamic Source Discovery**:

```
                  USER ENTERED TOPIC (e.g., "binary search")
                                     │
                                     ▼
                  DYNAMIC GITHUB REPOSITORY DISCOVERY
             (Searches GitHub API with Query Variations)
                                     │
                                     ▼
                  REPOSITORY RANKING & SELECTION
         (Scores candidates by stars, forks, & keyword match)
                                     │
                                     ▼
                LOCAL CACHING & ZIP CONTENT EXTRACTION
           (Extracts .md, .txt, .json, .csv; filters out build files)
                                     │
                                     ▼
                      DOCUMENT CHUNKING (Overlap=200)
                                     │
                                     ▼
             EMBEDDING GENERATION (all-MiniLM-L6-v2)
                                     │
                                     ▼
                 FAISS VECTOR INDEX (faiss.IndexFlatIP)
                                     │
                                     ▼
                  TOP-K SEMANTIC CONTEXT RETRIEVAL
                                     │
                                     ▼
                GEMINI INTERVIEW QUESTION GENERATION
         (Formulates question strictly from retrieved context)
                                     │
                                     ▼
                        CANDIDATE SUBMITS ANSWER
                                     │
                                     ▼
                     GEMINI CANDIDATE ANSWER EVALUATION
       (Returns Score /10, Verdict, Good, Missing, Ideal Answer)
```

---

## 🛠️ Tech Stack & Dependencies

- **Language**: Python 3.10+
- **Embedding Model**: `sentence-transformers` (`all-MiniLM-L6-v2`)
- **Vector Database**: `faiss-cpu` (`faiss.IndexFlatIP` with L2-normalized cosine similarity)
- **LLM / Evaluation Engine**: Google Gemini API (`google-genai` SDK)
- **HTTP / GitHub Search API**: `requests`
- **Environment Config**: `python-dotenv`

---

## 📁 Project Structure

```
c:/aryan codes/RAG-DEMO#2/
│
├── rag_pipeline.py    # Main RAG execution entry point
├── .env               # Environment configuration & API keys
├── .gitignore         # Git ignore rules
├── requirements.txt   # Required Python dependencies
├── README.md          # Complete project documentation
└── repo_cache/        # Cached GitHub repositories (auto-created)
```

---

## 🚀 Setup & Installation Instructions

### 1. Environment Setup
Install required dependencies into your Python environment:

```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Edit your `.env` file in the project root:

```env
GEMINI_API_KEY=your_gemini_api_key_here
GITHUB_TOKEN=optional_github_personal_access_token_here
GEMINI_MODEL=gemini-3.6-flash
```

*(Note: `GITHUB_TOKEN` is optional, but providing one increases your GitHub Search API rate limit from 10 req/min to 30 req/min).*

---

## 💻 Execution & Verification

Run the main pipeline:

```bash
python rag_pipeline.py
```

### Demonstration Flow:
1. Enter any interview query (e.g. `binary search`, `SQL joins`, `deadlock in operating systems`, `polymorphism in OOP`, `system design`).
2. Watch the terminal display top candidate GitHub repositories with star counts and relevance scores.
3. Observe automatic selection and extraction into `repo_cache/`.
4. Inspect the top-K retrieved vector search chunks with cosine similarity scores.
5. Answer the generated interview question.
6. View the detailed Gemini evaluation output (Score, Verdict, Good points, Missing points, Improvement suggestions, and Ideal Answer).

---

## 🛡️ Key Features for Mentor Evaluation

1. **No Fixed / Hardcoded Datasets**: Pure dynamic web/GitHub repository discovery.
2. **Real Vector RAG**: Sentence Transformers + FAISS cosine similarity vector search.
3. **Context Grounding**: Gemini is strictly instructed to answer using the retrieved source blocks, preventing hallucinations.
4. **Complete Traceability**: Displays exact source files and repository links used for every interview question and answer evaluation.
