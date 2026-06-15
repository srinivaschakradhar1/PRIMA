# AI-Powered Maintenance Wizard for Steel Plants — Backend

FastAPI backend providing equipment health prediction, a RAG knowledge pipeline,
and a LangGraph-based diagnosis agent for steel plant maintenance.

## Prerequisites

- Python 3.10+
- An OpenAI API key (the RAG pipeline has no offline fallback — see step 3)

## Getting Started

### 1. Create and activate a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

On macOS/Linux:

```bash
python -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure the OpenAI API key

Copy the example env file and fill in your key. A valid `OPENAI_API_KEY`
(`sk-...`) is **required** — without a working key the app aborts at startup
(connectivity probe) and every ingest/search request returns HTTP 503.

```bash
cp src/.env.example src/.env
```

Then edit `src/.env` and set your key:

```ini
OPENAI_API_KEY=sk-your-key-here
OPENAI_CHAT_MODEL=gpt-4o
OPENAI_EMBEDDING_MODEL=text-embedding-3-large
```

### 4. Start the application

Run from the `src` directory:

```bash
cd src
python main.py
```

The server starts on [http://localhost:8080](http://localhost:8080) with
auto-reload enabled. On startup it loads the seed JSON data into SQLite,
initializes the FAISS index, and verifies OpenAI connectivity.

## Verifying it works

- Health check: [http://localhost:8080/health](http://localhost:8080/health) → `{"status": "ok"}`
- Interactive API docs: [http://localhost:8080/docs](http://localhost:8080/docs)
