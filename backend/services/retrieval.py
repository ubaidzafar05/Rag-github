from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
from sentence_transformers import SentenceTransformer

try:
    import chromadb
except Exception:  # pragma: no cover - optional dependency
    chromadb = None

DEFAULT_EMBED_MODEL = os.getenv("RAG_EMBED_MODEL", "all-MiniLM-L6-v2")
DEFAULT_TOP_K = int(os.getenv("RAG_TOP_K", "6"))
MAX_FILE_SIZE_BYTES = int(os.getenv("RAG_MAX_FILE_SIZE_BYTES", "200000"))
CHUNK_LINE_SIZE = int(os.getenv("RAG_CHUNK_LINE_SIZE", "200"))
CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "40"))
DEFAULT_CACHE_DIR = os.getenv("RAG_CACHE_DIR", ".rag_cache")


@dataclass
class Chunk:
    path: str
    start_line: int
    end_line: int
    text: str


@dataclass
class RetrievalIndex:
    chunks: list[Chunk]
    embeddings: np.ndarray
    collection_name: str | None = None
    collection_path: str | None = None


_MODEL: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _MODEL
    if _MODEL is None:
        _MODEL = SentenceTransformer(DEFAULT_EMBED_MODEL)
    return _MODEL


def _iter_files(repo_root: Path) -> Iterable[Path]:
    for root, dirnames, filenames in os.walk(repo_root):
        dirnames[:] = [
            d
            for d in dirnames
            if d not in {".git", "node_modules", "__pycache__", ".venv", "dist", "build"}
        ]
        for filename in filenames:
            if filename in {"repomix-output.txt", "repomix-output.xml"}:
                continue
            path = Path(root) / filename
            if path.stat().st_size > MAX_FILE_SIZE_BYTES:
                continue
            yield path


def _chunk_lines(lines: list[str]) -> Iterable[tuple[int, int, str]]:
    start = 0
    total = len(lines)
    while start < total:
        end = min(start + CHUNK_LINE_SIZE, total)
        chunk_text = "".join(lines[start:end]).strip()
        if chunk_text:
            yield start + 1, end, chunk_text
        if end == total:
            break
        start = max(end - CHUNK_OVERLAP, 0)


def build_chunks(repo_path: str) -> list[Chunk]:
    repo_root = Path(repo_path)
    chunks: list[Chunk] = []
    for path in _iter_files(repo_root):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        lines = text.splitlines(keepends=True)
        for start_line, end_line, chunk_text in _chunk_lines(lines):
            chunks.append(
                Chunk(
                    path=str(path.relative_to(repo_root)),
                    start_line=start_line,
                    end_line=end_line,
                    text=chunk_text,
                )
            )
    return chunks


def build_index(repo_path: str) -> RetrievalIndex:
    chunks = build_chunks(repo_path)
    if not chunks:
        return RetrievalIndex(chunks=[], embeddings=np.zeros((0, 0)))
    model = _get_model()
    embeddings = model.encode([chunk.text for chunk in chunks], normalize_embeddings=True)
    embeddings = np.asarray(embeddings, dtype="float32")
    return RetrievalIndex(chunks=chunks, embeddings=embeddings)


def retrieve(
    query: str,
    index: RetrievalIndex,
    top_k: int = DEFAULT_TOP_K,
) -> list[Chunk]:
    if not index.chunks or index.embeddings.size == 0:
        return []
    model = _get_model()
    query_embedding = model.encode([query], normalize_embeddings=True).astype("float32")
    collection = _get_collection(index)
    if collection is not None:
        results = collection.query(query_embeddings=query_embedding.tolist(), n_results=top_k)
        top_indices = [int(item) for item in results["ids"][0]]
    else:
        scores = np.dot(index.embeddings, query_embedding[0])
        top_indices = np.argsort(scores)[::-1][:top_k]
    return [index.chunks[i] for i in top_indices]


def format_chunks(chunks: list[Chunk]) -> str:
    formatted = []
    for chunk in chunks:
        formatted.append(
            f'<FILE path="{chunk.path}" lines="{chunk.start_line}-{chunk.end_line}">\n'
            f"{chunk.text}\n"
            "</FILE>"
        )
    return "\n\n".join(formatted)


def _cache_dir(repo_path: str) -> Path:
    repo_root = Path(repo_path)
    cache_dir = repo_root / DEFAULT_CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def _cache_key(repo_path: str, repo_url: str | None = None) -> str:
    payload = f"{repo_path}:{repo_url or ''}:{DEFAULT_EMBED_MODEL}:{CHUNK_LINE_SIZE}:{CHUNK_OVERLAP}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _get_collection(index: RetrievalIndex):
    if chromadb is None or not index.collection_name or not index.collection_path:
        return None
    try:
        client = chromadb.PersistentClient(path=index.collection_path)
        return client.get_or_create_collection(index.collection_name)
    except Exception:
        return None


def load_index(repo_path: str, repo_url: str | None = None) -> RetrievalIndex | None:
    cache_dir = _cache_dir(repo_path)
    key = _cache_key(repo_path, repo_url)
    meta_path = cache_dir / f"{key}.json"
    emb_path = cache_dir / f"{key}.npy"
    if not meta_path.exists() or not emb_path.exists():
        return None
    try:
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        chunks = [
            Chunk(
                path=item["path"],
                start_line=item["start_line"],
                end_line=item["end_line"],
                text=item["text"],
            )
            for item in metadata.get("chunks", [])
        ]
        embeddings = np.load(str(emb_path))
        return RetrievalIndex(
            chunks=chunks,
            embeddings=embeddings,
            collection_name=metadata.get("collection_name"),
            collection_path=metadata.get("collection_path"),
        )
    except Exception:
        return None


def save_index(repo_path: str, index: RetrievalIndex, repo_url: str | None = None) -> None:
    cache_dir = _cache_dir(repo_path)
    key = _cache_key(repo_path, repo_url)
    meta_path = cache_dir / f"{key}.json"
    emb_path = cache_dir / f"{key}.npy"
    collection_name = f"repo_{key}"
    metadata = {
        "chunks": [
            {
                "path": chunk.path,
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
                "text": chunk.text,
            }
            for chunk in index.chunks
        ],
        "collection_name": collection_name,
        "collection_path": str(cache_dir),
    }
    meta_path.write_text(json.dumps(metadata), encoding="utf-8")
    np.save(str(emb_path), index.embeddings)
    if chromadb is not None and index.chunks:
        client = chromadb.PersistentClient(path=str(cache_dir))
        collection = client.get_or_create_collection(collection_name)
        ids = [str(i) for i in range(len(index.chunks))]
        collection.upsert(
            ids=ids,
            embeddings=index.embeddings.tolist(),
            documents=[chunk.text for chunk in index.chunks],
            metadatas=[
                {"path": chunk.path, "start_line": chunk.start_line, "end_line": chunk.end_line}
                for chunk in index.chunks
            ],
        )
        index.collection_name = collection_name
        index.collection_path = str(cache_dir)
