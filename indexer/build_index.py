import os
import json
from pathlib import Path
from typing import List, Dict, Any

from dotenv import load_dotenv
from langchain.text_splitter import RecursiveCharacterTextSplitter
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer
import numpy as np

# -----------------------------
# Load environment variables
# -----------------------------
load_dotenv()

DATA_DIR = Path("data/raw")
INDEX_DIR = Path("data/index")
INDEX_DIR.mkdir(parents=True, exist_ok=True)

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "capillary_docs")

CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1200"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "180"))

# -----------------------------
# Load Sentence-Transformer model
# -----------------------------
embed_model = SentenceTransformer("all-MiniLM-L6-v2")


# -----------------------------
# Load Markdown Documents
# -----------------------------
def load_markdown_docs() -> List[Dict[str, Any]]:
    docs: List[Dict[str, Any]] = []
    for md_path in DATA_DIR.glob("*.md"):
        text = md_path.read_text(encoding="utf-8")
        meta = {}
        if text.startswith("---\n"):
            try:
                end = text.find("\n---\n", 4)
                header = text[4:end]
                meta = json.loads(header)
                text = text[end + 5:]
            except Exception:
                pass
        docs.append({"content": text, "metadata": meta, "path": str(md_path)})
    return docs


# -----------------------------
# Chunk Text into Overlapping Parts
# -----------------------------
def chunk_documents(docs: List[Dict[str, Any]]):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    all_chunks = []
    for d in docs:
        parts = splitter.split_text(d["content"])
        for i, part in enumerate(parts):
            all_chunks.append({
                "text": part,
                "metadata": {**d.get("metadata", {}), "source_path": d["path"], "chunk_id": i},
            })
    return all_chunks


# -----------------------------
# Generate Embeddings using Sentence-Transformers
# -----------------------------
def embed_texts(texts: List[str]) -> List[List[float]]:
    embeddings = embed_model.encode(texts, convert_to_numpy=True)
    return embeddings.tolist()


# -----------------------------
# Create / Ensure Qdrant Collection
# -----------------------------
def ensure_qdrant_collection(qc: QdrantClient, dim: int):
    try:
        qc.get_collection(QDRANT_COLLECTION)
    except Exception:
        qc.recreate_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE)
        )


# -----------------------------
# Build BM25 Corpus
# -----------------------------
def build_bm25(chunks: List[Dict[str, Any]]):
    corpus = [c["text"] for c in chunks]
    tokenized = [doc.split() for doc in corpus]
    bm25 = BM25Okapi(tokenized)
    with (INDEX_DIR / "bm25_corpus.jsonl").open("w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c) + "\n")
    with (INDEX_DIR / "bm25_tokens.json").open("w", encoding="utf-8") as f:
        json.dump(tokenized, f)


# -----------------------------
# Main Indexing Flow
# -----------------------------
def main():
    docs = load_markdown_docs()
    if not docs:
        raise RuntimeError("No documents found. Run crawler first.")

    chunks = chunk_documents(docs)
    texts = [c["text"] for c in chunks]

    # Determine embedding dimension from first embedding
    probe = embed_model.encode(["probe"], convert_to_numpy=True)
    dim = probe.shape[1]

    vectors = []
    batch_size = 64  # small batches for memory safety
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        vectors.extend(embed_texts(batch))

    qc = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    ensure_qdrant_collection(qc, dim)

    payloads = []
    ids = []
    for idx, c in enumerate(chunks):
        meta = c["metadata"].copy()
        meta_url = meta.get("url") or meta.get("source") or meta.get("source_path")
        payloads.append({
            "text": c["text"],
            "url": meta_url,
            "title": meta.get("title")
        })
        ids.append(idx)

    qc.upload_collection(
        collection_name=QDRANT_COLLECTION,
        vectors=vectors,
        payload=payloads,
        ids=ids
    )

    build_bm25(chunks)
    print(f"✅ Indexed {len(chunks)} chunks to Qdrant and built BM25 corpus using local embeddings.")


if __name__ == "__main__":
    main()
