# Capillary Docs Chatbot (RAG)

End-to-end chatbot powered by Retrieval-Augmented Generation:
- Crawler: Firecrawl
- Embeddings: OpenAI
- Vector DB: Qdrant
- Keyword Search: LangChain BM25
- Reranker: Cohere rerank-3
- Backend: FastAPI
- Frontend: React (Vite)

## Quickstart

1) Create and fill environment variables

Copy `.env.example` to `.env` and set keys:

- OPENAI_API_KEY
- COHERE_API_KEY
- FIRECRAWL_API_KEY
- QDRANT_URL (e.g. http://localhost:6333)
- QDRANT_API_KEY (optional for local dev)

2) Crawl Capillary docs

```bash
python -m venv .venv && .\\.venv\\Scripts\\activate
pip install -r backend/requirements.txt
python crawler/firecrawl_crawl.py
```

3) Build index (Qdrant + BM25)

```bash
python indexer/build_index.py
```

4) Run backend

```bash
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

5) Run frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

## Notes
- Ensure Qdrant is running locally (Docker) or provide cloud URL.
- Re-run crawl and index when docs change.

## Source
Capillary Documentation Hub: [`https://docs.capillarytech.com/`](https://docs.capillarytech.com/)
