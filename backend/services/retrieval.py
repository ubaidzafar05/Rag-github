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
_RANKER = None # Lazy loaded CrossEncoder


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
            if path.suffix.lower() == ".pdf":
                text = _read_pdf(path)
            else:
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
    model = _get_model()
    # Contextual Embedding: Prepend file path to content for better retrieval
    embed_texts = [f"File: {chunk.path}\nContent:\n{chunk.text}" for chunk in chunks]
    embeddings = model.encode(embed_texts, normalize_embeddings=True)
    embeddings = np.asarray(embeddings, dtype="float32")
    return RetrievalIndex(chunks=chunks, embeddings=embeddings)


def _read_pdf(path: Path) -> str:
    try:
        import pdfplumber
        text = ""
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        return text
    except Exception:
        return ""




try:
    import tiktoken
except ImportError:
    tiktoken = None

def _count_tokens(text: str) -> int:
    if tiktoken:
        try:
            encoding = tiktoken.get_encoding("cl100k_base")
            return len(encoding.encode(text))
        except Exception:
            return len(text) // 4
    return len(text) // 4


def retrieve(
    query: str,
    index: RetrievalIndex,
    top_k: int = DEFAULT_TOP_K,
    max_tokens: int = 100000,
    repo_path: str | None = None,
) -> list[Chunk]:

    if not index.chunks or index.embeddings.size == 0:
        return []
    model = _get_model()
    query_embedding = model.encode([query], normalize_embeddings=True).astype("float32")
    collection = _get_collection(index)
    
    
    # 1. Broad Retrieval (Top K * 5)
    broad_k = top_k * 5
    if collection is not None:
        results = collection.query(query_embeddings=query_embedding.tolist(), n_results=broad_k)
        top_indices = [int(item) for item in results["ids"][0]]
    else:
        scores = np.dot(index.embeddings, query_embedding[0])
        top_indices = np.argsort(scores)[::-1][:broad_k]
    
    broad_chunks = [index.chunks[i] for i in top_indices]
    
    # 2. Re-Ranking (Cross Encoder)
    # Lazy load ranker to save startup time
    global _RANKER
    if _RANKER is None:
        try:
           from sentence_transformers import CrossEncoder
           _RANKER = CrossEncoder('cross-encoder/ms-marco-TinyBERT-L-2-v2') 
        except Exception as e:
            print(f"Re-ranker load failed: {e}")
            _RANKER = None

    if _RANKER:
        # Create pairs: (query, text)
        pairs = [[query, chunk.text] for chunk in broad_chunks]
        scores = _RANKER.predict(pairs)
        
        # Sort chunks by cross-encoder score
        # zip together, sort, unzip
        scored_chunks = sorted(zip(broad_chunks, scores), key=lambda x: x[1], reverse=True)
        ranked_chunks = [chunk for chunk, score in scored_chunks]
    else:
        ranked_chunks = broad_chunks # Fallback to vector order

    # 3. GraphRAG Expansion
    # Find dependencies of the top 3 files and add them to context
    try:
        from services.graph import get_related_files
        # Extract unique paths from top 3 chunks
        top_paths = list(set([c.path for c in ranked_chunks[:3]]))
        
        related_paths = set()
        for path in top_paths:
             # We need repo_path. Chunk doesn't store absolute repo path, only relative.
             # We need to guess or pass it. 
             # 'retrieve' doesn't receive repo_path.
             # Ideally index should store it or we pass it.
             # Limitation: We can't easily call get_related_files without absolute repo_path.
             # WORKAROUND: Skip for now OR modify signature. 
             # Actually, retrieval is usually called with an index loaded from disk. 
             # The index object doesn't know the absolute path on disk necessarily if loaded from cache.
             pass
             
        # WAIT: retrieval.py's load_index logic uses cache_dir.
        # But we need the ACTUAL source repo path to parse imports for the graph service.
        # If the user hasn't ingested/cloned, we can't parse imports.
        # Assuming ingestion happened, the files are there.
        # I will rely on the fact that if we have an index, we *likely* know the repo path or can request it.
        # Let's change 'retrieve' signature to accept 'repo_path' optional.
    except ImportError:
        pass

    graph_chunks = []
    if repo_path:
        try:
            from services.graph import get_related_files
            # Extract unique paths from top 3 chunks
            top_paths = list(set([c.path for c in ranked_chunks[:3]]))
            
            related_paths = set()
            for path in top_paths:
                 neighbors = get_related_files(repo_path, path)
                 related_paths.update(neighbors)
            
            # Find chunks matching related paths (that aren't already in ranked)
            rank_paths = set(c.path for c in ranked_chunks)
            for chunk in index.chunks:
                if chunk.path in related_paths and chunk.path not in rank_paths:
                    graph_chunks.append(chunk)
                    
            # Prioritize Graph chunks? Or append them?
            # Strategy: Append them after the top 10 re-ranked, but before the tail.
            # For simplicity: Append them at the end of the priority queue
            # But duplicate check is essential.
        except Exception as e:
            print(f"GraphRAG Error: {e}")
            
    # Combine lists: Re-Ranked + Graph Neighbors
    # Deduplicate by object identity or path+start_line
    seen = set()
    final_unique_chunks = []
    
    for c in ranked_chunks + graph_chunks:
        uid = f"{c.path}:{c.start_line}"
        if uid not in seen:
            seen.add(uid)
            final_unique_chunks.append(c)

    # 4. Token Budget Packing
    packed_chunks = []
    current_tokens = 0
    
    for chunk in final_unique_chunks:
        chunk_cost = _count_tokens(chunk.text) + 20 # Buffer for XML tags
        if current_tokens + chunk_cost <= max_tokens:
            packed_chunks.append(chunk)
            current_tokens += chunk_cost
        else:
            break
            
    return packed_chunks


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
