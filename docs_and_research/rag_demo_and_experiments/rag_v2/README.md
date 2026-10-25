# AI Technical Interviewer 2.0 (Offline-First & Dual-Source RAG)

An advanced AI-powered technical interview preparation system built with Python, FAISS vector search, Google Gemini, and automated dual-source knowledge retrieval (GitHub Repositories + GeeksforGeeks).

---

## 🌟 Key Features

1. **Tier-1 Local Offline Knowledge Base & Vector Index**:
   - Checks local offline database (`rag_v2/offline_db/`) first using `sentence-transformers/all-MiniLM-L6-v2` and FAISS IndexFlatIP (cosine similarity).
   - If cosine similarity $\ge 0.68$, it retrieves local knowledge instantly with **zero network latency** and **no rate limits**.

2. **Tier-2 Dual-Source Online Discovery (GitHub + GeeksforGeeks)**:
   - If the topic is missing offline or below the similarity threshold:
     - **GitHub**: Discovers and extracts top-starred coding interview repositories.
     - **GeeksforGeeks (GFG)**: Searches and extracts technical articles, complexities, and explanations.
   - **Cross-Source Comparison**: Gemini compares the material from GitHub and GeeksforGeeks, synthesizing the best conceptual and practical question.
   - **Automatic Caching**: Automatically saves the newly synthesized topic into `offline_db/dynamic_cache.json` for instant future retrieval.

3. **Interactive Answer Evaluation**:
   - Grades the candidate's answer out of 10.
   - Provides Verdict (`Correct`, `Partially Correct`, `Incorrect`).
   - Highlights strengths, missing points, improvements, and ideal answers.

4. **Adaptive Misconception-Driven Follow-Up Engine**:
   - If the candidate answers incorrectly or exhibits misconceptions (e.g. confusing Stack with Queue in BFS), Gemini detects the mistake and asks a targeted follow-up question (e.g., *"Do you know what data structure is used in BFS and why a Stack changes the traversal?"*).
   - If the candidate answers correctly, Gemini poses an advanced follow-up (e.g., 0-1 BFS, bidirectional search, edge cases).
   - Multi-turn interactive conversation loop.

---

## 📂 Project Structure

```
rag_v2/
├── offline_db/                 # Curated local knowledge base (JSON + vector indexed)
│   ├── dsa_topics.json         # Pre-loaded DSA topics (BFS, DFS, Binary Search, etc.)
│   ├── system_design.json      # System design topics (LRU Cache, Sharding)
│   └── dynamic_cache.json      # Automatically populated when online topics are searched
├── sources/
│   ├── offline_store.py        # FAISS vector store & thresholding logic
│   ├── github_retriever.py     # GitHub API search, ZIP downloader, content extractor
│   └── gfg_retriever.py        # GeeksforGeeks search & HTML content parser
├── interviewer/
│   ├── gemini_client.py        # Gemini client wrapper with exponential backoff
│   ├── question_generator.py   # Cross-source comparison and question generator
│   ├── evaluator.py            # Answer evaluation & misconception extractor
│   └── follow_up_engine.py     # Targeted follow-up question generator & grader
├── main.py                     # Interactive CLI entrypoint
├── requirements.txt            # Project dependencies
└── README.md                   # Documentation
```

---

## 🚀 Getting Started

### 1. Configure Environment Variables
Ensure your `.env` file in the project root contains your Gemini API key:
```env
GEMINI_API_KEY=your_gemini_api_key_here
GITHUB_TOKEN=your_github_token_here    # (Optional, increases GitHub API rate limit)
GEMINI_MODEL=gemini-2.5-flash
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run the Interviewer
```bash
python main.py
```
