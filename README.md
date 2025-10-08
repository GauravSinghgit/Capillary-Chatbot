# Capillary Docs Chatbot (RAG)

End-to-end chatbot powered by Retrieval-Augmented Generation with local retrieval and reranking, and OpenAI for answer generation.

- **Crawler**: Playwright/Chromium-based (`crawler/crawl4ai_crawl.py`)
- **Chunking**: LangChain `RecursiveCharacterTextSplitter`
- **Embeddings**: Sentence-Transformers `all-MiniLM-L6-v2` (local)
- **Vector DB**: Qdrant
- **Keyword Search**: `rank-bm25`
- **Reranker**: CrossEncoder `ms-marco-MiniLM-L-6-v2` (local)
- **Generator**: OpenAI (`gpt-4o-mini`)
- **Backend**: FastAPI
- **Frontend**: React (Vite)

Architecture Flow

       ┌────────────────────────┐
       │     Crawl4AI Crawler   │
       └────────────┬───────────┘
                    │
                    ▼
       ┌────────────────────────┐
       │   Text Cleaning &      │
       │   Chunking Pipeline    │
       └────────────┬───────────┘
                    │
                    ▼
       ┌────────────────────────┐
       │ Sentence Transformer    │
       │ (Embeddings)            │
       └────────────┬───────────┘
                    │
                    ▼
       ┌────────────────────────┐
       │    Qdrant (Local)      │
       │   Vector DB Storage    │
       └────────────┬───────────┘
                    │
                    ▼
       ┌────────────────────────┐
       │ Local Reranker Model   │
       └────────────┬───────────┘
                    │
                    ▼
       ┌────────────────────────┐
       │     FastAPI Backend    │
       │   + LLM Response Gen   │
       └────────────────────────┘

## Prerequisites

 - Python 3.10+
 - Node.js 18+
 - Qdrant running locally or cloud
 - Playwright browsers (Chromium) installed

Run Qdrant locally (example):

```bash
docker run -p 6333:6333 -p 6334:6334 qdrant/qdrant
```

## Environment Variables

Create a `.env` in the project root and set as needed:

- `OPENAI_API_KEY`
- `QDRANT_URL` (e.g. `http://localhost:6333`)
- `QDRANT_API_KEY` (optional for local)
- `QDRANT_COLLECTION` (default: `capillary_docs`)
- `DOCS_DOMAIN` (default: `https://docs.capillarytech.com/`)
- `CRAWL_MAX_PAGES` (default: `500`)
- `CRAWL_CONCURRENCY` (default: `5`)
- `FIRECRAWL_API_KEY` (only if using Firecrawl)

## Setup (Windows PowerShell)

```bash
python -m venv .venv && .\.venv\Scripts\activate
pip install -r backend/requirements.txt

# Crawler needs Playwright
pip install playwright
python -m playwright install chromium
```

## 1) Crawl documentation

Default: Playwright-based crawler (sitemap + rendered content):

```bash
python crawler/crawl4ai.py
```

```bash
python crawler/chunk_docs.py
```
Raw markdown pages are saved to `data/raw`.

## 2) Build index (Qdrant + BM25)

```bash
python indexer/build_index.py
```

This:
- Chunks markdown with LangChain
- Generates local embeddings (Sentence-Transformers)
- Uploads vectors + payloads to Qdrant
- Builds BM25 artifacts in `data/index`

## 3) Run backend

```bash
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

Backend serves `POST /chat` that performs hybrid retrieval (vector + BM25), local reranking, then calls OpenAI to generate the final answer and returns sources.

## 4) Run frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

## Notes
- Ensure Qdrant is reachable at `QDRANT_URL` before indexing/searching.
- Re-run crawl and index when docs change.
 - You can tune retrieval via `k` in the request body to `/chat`.

## Source
Capillary Documentation Hub: [`https://docs.capillarytech.com/`](https://docs.capillarytech.com/)
