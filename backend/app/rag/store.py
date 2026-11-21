"""
Vector store and local embedding module for the Real Estate AI Chatbot RAG system.
Uses Ollama (nomic-embed-text) for embeddings and ChromaDB PersistentClient for storage.
"""

import json
import logging
import os
from pathlib import Path
import sys
from typing import Any, Optional, Union
import urllib.error
import urllib.request
import warnings

warnings.filterwarnings("ignore", category=RuntimeWarning, module="opentelemetry")

# Fallback for Windows Application Control blocking grpc._cython
try:
    from grpc._cython import cygrpc  # noqa: F401
except Exception:
    from unittest.mock import MagicMock
    mock_grpc = MagicMock(__version__="1.63.2")
    sys.modules.setdefault("grpc", mock_grpc)
    sys.modules.setdefault("grpc._compression", mock_grpc)
    sys.modules.setdefault("grpc._cython", mock_grpc)

import chromadb

logger = logging.getLogger(__name__)

DEFAULT_COLLECTION_NAME: str = "real_estate_documents"
DEFAULT_STRUCTURED_COLLECTION: str = "real_estate_documents_v3_structured"
COLLECTION_V3_STRUCTURED: str = "real_estate_documents_v3_structured"
DEFAULT_OLLAMA_MODEL: str = "nomic-embed-text"
DEFAULT_OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
DEFAULT_TIMEOUT: int = 10

_last_ollama_check_time: float = 0.0
_is_ollama_available: Optional[bool] = None


def is_ollama_reachable(cache_ttl_seconds: float = 30.0) -> bool:
    """Checks if local Ollama is reachable with a fast 1.0s timeout, cached for cache_ttl_seconds.
    On Render or production deployments, immediately returns False without network attempts."""
    global _last_ollama_check_time, _is_ollama_available
    import time

    # Immediately disable Ollama when deployed on Render or in production
    if os.getenv("RENDER") or os.getenv("RENDER_SERVICE_ID") or os.getenv("APP_ENV") == "production":
        _is_ollama_available = False
        return False

    now = time.time()
    if _is_ollama_available is not None and (now - _last_ollama_check_time) < cache_ttl_seconds:
        return _is_ollama_available

    url = f"{get_ollama_base_url()}/api/tags"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            _is_ollama_available = (resp.status == 200)
    except Exception:
        _is_ollama_available = False

    _last_ollama_check_time = now
    return _is_ollama_available


def get_default_chroma_dir() -> Path:
    """Resolves default ChromaDB directory: <backend>/data/chroma_db."""
    return Path(__file__).resolve().parent.parent.parent / "data" / "chroma_db"


def get_ollama_base_url() -> str:
    """Returns Ollama base URL from environment or default."""
    return os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL).rstrip("/")


def get_embedding_model() -> str:
    """Returns Ollama embedding model name from environment or default."""
    return os.getenv("OLLAMA_EMBED_MODEL", DEFAULT_OLLAMA_MODEL)


def _post_ollama(endpoint: str, payload: dict, timeout: int = DEFAULT_TIMEOUT) -> dict:
    """Internal helper to execute JSON POST requests to local Ollama API."""
    url = f"{get_ollama_base_url()}{endpoint}"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        raise ConnectionError(
            f"Ollama unavailable at {url}: {e.reason}. Ensure Ollama is running ('ollama serve')."
        ) from e


def check_ollama_status() -> dict[str, Any]:
    """Checks if Ollama service is reachable and has the embedding model."""
    status = {"reachable": False, "model_available": False, "version": None, "error": None}
    try:
        url = f"{get_ollama_base_url()}/api/tags"
        with urllib.request.urlopen(urllib.request.Request(url), timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models = [m.get("name", "") for m in data.get("models", [])]
            target = get_embedding_model()
            status["reachable"] = True
            status["model_available"] = any(m == target or m.startswith(f"{target}:") for m in models)
    except Exception as e:
        status["error"] = str(e)
    return status


def get_embedding(text: str, model: Optional[str] = None) -> list[float]:
    """Generates a dense vector embedding for a single text using Ollama."""
    if not text or not text.strip():
        raise ValueError("Cannot generate embedding for empty text.")
    if not is_ollama_reachable():
        raise ConnectionError("Ollama service is not reachable on this host.")
    data = _post_ollama("/api/embeddings", {"model": model or get_embedding_model(), "prompt": text})
    emb = data.get("embedding")
    if not emb:
        raise RuntimeError("Ollama returned empty embedding.")
    return emb


def get_embeddings(texts: list[str], model: Optional[str] = None) -> list[list[float]]:
    """Generates embeddings for multiple texts using batch or fallback sequential calls."""
    if not texts:
        return []
    target_model = model or get_embedding_model()
    try:
        data = _post_ollama("/api/embed", {"model": target_model, "input": texts})
        if "embeddings" in data and len(data["embeddings"]) == len(texts):
            return data["embeddings"]
    except Exception:
        pass
    return [get_embedding(t, target_model) for t in texts]


def get_vector_store(persist_dir: Optional[Union[str, Path]] = None) -> chromadb.PersistentClient:
    """Initializes and returns a ChromaDB PersistentClient instance."""
    path = Path(persist_dir).resolve() if persist_dir else get_default_chroma_dir()
    path.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(path))


def get_or_create_collection(
    client: Optional[chromadb.PersistentClient] = None,
    collection_name: str = DEFAULT_COLLECTION_NAME,
    persist_dir: Optional[Union[str, Path]] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> chromadb.Collection:
    """Retrieves or creates a persistent ChromaDB collection."""
    db_client = client or get_vector_store(persist_dir=persist_dir)
    return db_client.get_or_create_collection(name=collection_name, metadata=metadata)


def add_chunks(
    chunks: list[dict[str, Any]],
    client: Optional[chromadb.PersistentClient] = None,
    collection: Optional[chromadb.Collection] = None,
    collection_name: str = DEFAULT_COLLECTION_NAME,
    persist_dir: Optional[Union[str, Path]] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    Adds chunk documents and their embeddings into ChromaDB.
    Deduplicates within the input batch and skips chunks already stored in ChromaDB.
    """
    coll = collection or get_or_create_collection(
        client=client, collection_name=collection_name, persist_dir=persist_dir, metadata=metadata
    )
    if not chunks:
        return {"total_submitted": 0, "new_added": 0, "skipped_duplicates": 0, "collection_count": coll.count()}

    # 1. Deduplicate within the provided batch itself
    seen: set[str] = set()
    unique_batch: list[dict[str, Any]] = []
    for c in chunks:
        cid = c.get("chunk_id")
        if cid and cid not in seen:
            seen.add(cid)
            unique_batch.append(c)

    batch_dups = len(chunks) - len(unique_batch)

    # 2. Check which chunks already exist in ChromaDB
    existing = set(coll.get(ids=[c["chunk_id"] for c in unique_batch])["ids"])
    to_add = [c for c in unique_batch if c["chunk_id"] not in existing]
    skipped = batch_dups + (len(unique_batch) - len(to_add))

    if not to_add:
        logger.info("All %d submitted chunks are duplicates. Skipped.", len(chunks))
        return {
            "total_submitted": len(chunks),
            "new_added": 0,
            "skipped_duplicates": skipped,
            "collection_count": coll.count(),
        }

    # 3. Generate embeddings and ingest
    texts = [c["text"] for c in to_add]
    ids = [c["chunk_id"] for c in to_add]
    metadatas = []
    for c in to_add:
        m = {
            "source": c.get("source", "unknown"),
            "page": int(c.get("page", 1)),
            "chunk_id": c["chunk_id"],
            "char_count": len(c["text"]),
        }
        # Dynamically preserve any additional metadata fields (e.g. property_name, configuration, category)
        for k, v in c.items():
            if k not in ("text", "source", "page", "chunk_id", "char_count") and v is not None:
                m[k] = v if isinstance(v, (int, float, bool)) else str(v)
        metadatas.append(m)

    embeddings = get_embeddings(texts)
    coll.add(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)
    logger.info("Added %d new chunk(s) to collection '%s'.", len(to_add), coll.name)

    return {
        "total_submitted": len(chunks),
        "new_added": len(to_add),
        "skipped_duplicates": skipped,
        "collection_count": coll.count(),
    }


def get_collection_status(
    client: Optional[Union[chromadb.PersistentClient, str]] = None,
    collection_name: str = DEFAULT_COLLECTION_NAME,
    persist_dir: Optional[Union[str, Path]] = None,
) -> dict[str, Any]:
    """Returns basic diagnostics of the ChromaDB collection."""
    
    if isinstance(client, str):
        collection_name = client
        client = None

    path = Path(persist_dir).resolve() if persist_dir else get_default_chroma_dir()
    db_client = client or get_vector_store(persist_dir=path)
    coll = db_client.get_or_create_collection(name=collection_name)
    return {
        "collection_name": collection_name,
        "record_count": coll.count(),
        "persist_directory": str(path),
        "directory_exists": path.exists(),
    }
