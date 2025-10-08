import os
import json
from typing import List, Dict, Any
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.http import models as qm
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer, CrossEncoder

load_dotenv()

# ---------------- Environment ----------------
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "capillary_docs")
INDEX_DIR = os.path.join("data", "index")

# ---------------- Clients ----------------
openai_client = OpenAI()
qdrant = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
embed_model = SentenceTransformer("all-MiniLM-L6-v2")
reranker_model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

# ---------------- BM25 ----------------
with open(os.path.join(INDEX_DIR, "bm25_corpus.jsonl"), "r", encoding="utf-8") as f:
    docs = [json.loads(line) for line in f]
corpus = [d["text"] for d in docs]
tokenized = [c.split() for c in corpus]
bm25 = BM25Okapi(tokenized)

# ---------------- FastAPI ----------------
app = FastAPI()


class ChatRequest(BaseModel):
    query: str
    k: int = 8


# ---------------- Embedding Functions ----------------
def embed_query(query: str) -> List[float]:
    return embed_model.encode(query).tolist()


# ---------------- Search Functions ----------------
def vector_search(query: str, k: int) -> List[Dict[str, Any]]:
    qv = embed_query(query)
    hits = qdrant.search(
        collection_name=QDRANT_COLLECTION,
        query_vector=qv,
        limit=k,
        with_payload=True,
        score_threshold=0.15
    )
    results = []
    for h in hits:
        payload = h.payload or {}
        results.append({
            "text": payload.get("text", ""),
            "url": payload.get("url"),
            "title": payload.get("title"),
            "score": float(h.score),
            "source": "vector",
        })
    return results


def bm25_search(query: str, k: int) -> List[Dict[str, Any]]:
    scores = bm25.get_scores(query.split())
    top_idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
    results = []
    for i in top_idx:
        d = docs[i]
        results.append({
            "text": d["text"],
            "url": d["metadata"].get("url") or d["metadata"].get("source_path"),
            "title": d["metadata"].get("title"),
            "score": float(scores[i]),
            "source": "bm25",
        })
    return results


def hybrid_retrieve(query: str, k: int = 8) -> List[Dict[str, Any]]:
    vec_results = vector_search(query, k)
    bm25_results = bm25_search(query, k)
    combined = vec_results + bm25_results

    # deduplicate by text + url
    seen = set()
    unique = []
    for r in combined:
        key = (r["text"][:64], r.get("url"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(r)
    return unique[:max(k * 2, 10)]


# ---------------- Local Reranker ----------------
def rerank_locally(query: str, docs_in: List[Dict[str, Any]], top_n: int = 6) -> List[Dict[str, Any]]:
    if not docs_in:
        return []
    inputs = [[query, d["text"]] for d in docs_in]
    scores = reranker_model.predict(inputs)
    ranked = sorted(zip(docs_in, scores), key=lambda x: x[1], reverse=True)
    result = []
    for d, s in ranked[:top_n]:
        d["rerank_score"] = float(s)
        result.append(d)
    return result


# ---------------- Prompt + Answer ----------------
def build_prompt(contexts: List[Dict[str, Any]], query: str) -> str:
    ctx = []
    for c in contexts:
        url = c.get("url") or ""
        title = c.get("title") or ""
        snippet = c.get("text") or ""
        ctx.append(f"Title: {title}\nURL: {url}\nSnippet: {snippet}")
    joined = "\n\n".join(ctx)
    instructions = (
        "Answer the user based ONLY on the context. "
        "Cite 1-3 sources using markdown links to their URLs. "
        "If not found, say you cannot find it in the docs and suggest closest relevant links. "
        "Keep the answer concise with bullet points and bold key terms."
    )
    return f"{instructions}\n\nContext:\n{joined}\n\nQuestion: {query}\nAnswer:"


def generate_answer(query: str, contexts: List[Dict[str, Any]]) -> str:
    prompt = build_prompt(contexts, query)
    resp = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    return resp.choices[0].message.content


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For dev: allow all origins. In prod, put your React URL
    allow_credentials=True,
    allow_methods=["*"],  # Allow POST, GET, etc.
    allow_headers=["*"],
)


# ---------------- API Endpoint ----------------
@app.post("/chat")
def chat(req: ChatRequest):
    candidates = hybrid_retrieve(req.query, k=req.k)
    reranked = rerank_locally(req.query, candidates, top_n=6)
    top_ctx = reranked[:6]
    answer = generate_answer(req.query, top_ctx)

    # Collect sources
    sources = list(dict.fromkeys([c.get("url") for c in top_ctx if c.get("url")]))
    return {"answer": answer, "sources": sources}
