"""
Vector Store Manager for EstateAI RAG using Amazon Bedrock Titan v2 and FAISS.
Replaces ChromaDB and Ollama.
Persists vectors and chunk metadata on EC2 local storage.
Features:
- Titan Embeddings v2 (amazon.titan-embed-text-v2:0, 1024 dimensions)
- Persistent FAISS index on disk
- Seamless NumPy cosine fallback if FAISS native DLL is constrained by local OS policy
- Document SHA-256 fingerprinting to prevent redundant re-indexing
- Controlled errors without placeholder zero vectors
"""

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any, Optional, Union

import numpy as np

# Attempt FAISS import
try:
    import faiss
    _HAS_FAISS = True
except Exception as faiss_err:
    faiss = None
    _HAS_FAISS = False

from app.config import env
from app.rag.chunker import chunk_documents
from app.rag.loader import get_default_pdf_dir, load_pdf_documents
from app.services.bedrock_service import BedrockService

logger = logging.getLogger("estateai.vector_store")

INDEX_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "faiss_index"


class FaissVectorStore:
    def __init__(self, index_dir: Optional[Union[str, Path]] = None):
        self.index_dir = Path(index_dir or env("VECTOR_STORE_PATH", str(INDEX_DIR)))
        self.index_dir.mkdir(parents=True, exist_ok=True)
        
        self.index_file = self.index_dir / "index.faiss"
        self.vectors_file = self.index_dir / "vectors.npy"
        self.metadata_file = self.index_dir / "metadata.json"
        self.fingerprints_file = self.index_dir / "fingerprints.json"

        self.bedrock_service = BedrockService()
        self.dimension = self.bedrock_service.embedding_dimensions

        self.index = None
        self.vectors: list[list[float]] = []
        self.chunks_metadata: list[dict[str, Any]] = []
        self.fingerprints: dict[str, str] = {}

        self._load_from_disk()

    def _load_from_disk(self):
        """Loads FAISS index or NumPy vectors and metadata from persistent storage."""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, "r", encoding="utf-8") as f:
                    self.chunks_metadata = json.load(f)
            except Exception as e:
                logger.warning("Failed to load metadata.json: %s", e)
                self.chunks_metadata = []

        if self.fingerprints_file.exists():
            try:
                with open(self.fingerprints_file, "r", encoding="utf-8") as f:
                    self.fingerprints = json.load(f)
            except Exception as e:
                logger.warning("Failed to load fingerprints.json: %s", e)
                self.fingerprints = {}

        # Load FAISS index if available
        if _HAS_FAISS and self.index_file.exists():
            try:
                self.index = faiss.read_index(str(self.index_file))
                logger.info("Loaded persistent FAISS index with %d vectors", self.index.ntotal)
            except Exception as e:
                logger.warning("Failed to read FAISS index file: %s", e)
                self.index = None

        # Load raw vectors array for NumPy fallback
        if self.vectors_file.exists():
            try:
                arr = np.load(str(self.vectors_file))
                self.vectors = arr.tolist()
                logger.info("Loaded %d persistent vectors from disk", len(self.vectors))
            except Exception as e:
                logger.warning("Failed to read vectors.npy: %s", e)
                self.vectors = []

    def _save_to_disk(self):
        """Persists index, vectors, metadata, and fingerprints to disk."""
        try:
            with open(self.metadata_file, "w", encoding="utf-8") as f:
                json.dump(self.chunks_metadata, f, indent=2)

            with open(self.fingerprints_file, "w", encoding="utf-8") as f:
                json.dump(self.fingerprints, f, indent=2)

            if self.vectors:
                arr = np.array(self.vectors, dtype=np.float32)
                np.save(str(self.vectors_file), arr)

            if _HAS_FAISS and self.index is not None:
                faiss.write_index(self.index, str(self.index_file))

            logger.info("Saved vector index (%d items) to %s", len(self.chunks_metadata), self.index_dir)
        except Exception as e:
            logger.error("Failed to save vector store to disk: %s", e)

    def is_document_indexed(self, filename: str, file_hash: str) -> bool:
        """Checks if document has already been indexed with matching hash."""
        return self.fingerprints.get(filename) == file_hash and len(self.chunks_metadata) > 0

    def add_documents(self, documents: list[dict[str, Any]], filename: str, file_hash: str) -> int:
        """
        Chunks documents, generates Bedrock Titan v2 embeddings, and stores in vector index.
        Returns number of chunks indexed.
        """
        if self.is_document_indexed(filename, file_hash):
            logger.info("Document '%s' already indexed with fingerprint %s. Skipping duplicate embedding.", filename, file_hash[:8])
            return 0

        chunks = chunk_documents(documents)
        if not chunks:
            logger.warning("No text chunks generated for '%s'. Check document text extractability.", filename)
            return 0

        logger.info("Generating Amazon Bedrock Titan v2 embeddings for %d chunks in '%s'", len(chunks), filename)
        new_vectors = []
        new_metadata = []

        for idx, chunk in enumerate(chunks):
            text = chunk.get("text", "").strip()
            if not text:
                continue
            
            try:
                embedding = self.bedrock_service.generate_embedding(text)
                new_vectors.append(embedding)
                
                # Attach unique chunk ID and metadata
                chunk["chunk_id"] = f"{filename}_{idx:04d}"
                new_metadata.append(chunk)
            except Exception as e:
                logger.error("Failed to generate embedding for chunk %d of '%s': %s", idx, filename, e)
                # Controlled error: do NOT generate zero vector placeholder
                continue

        if not new_vectors:
            logger.error("Zero valid embeddings generated for '%s'. Index not updated.", filename)
            return 0

        # Update in-memory storage
        self.vectors.extend(new_vectors)
        self.chunks_metadata.extend(new_metadata)
        self.fingerprints[filename] = file_hash

        # Update FAISS index
        if _HAS_FAISS:
            arr = np.array(new_vectors, dtype=np.float32)
            faiss.normalize_L2(arr)
            if self.index is None:
                self.index = faiss.IndexFlatIP(self.dimension)
            self.index.add(arr)

        self._save_to_disk()
        logger.info("Successfully added %d chunks from '%s' to vector store", len(new_vectors), filename)
        return len(new_vectors)

    def search(self, query: str, top_k: int = 5) -> list[tuple[dict[str, Any], float]]:
        """
        Generates query embedding via Bedrock Titan v2 and searches vectors.
        Returns list of (chunk_metadata, similarity_score).
        """
        if not self.chunks_metadata or not self.vectors:
            logger.warning("Vector store is empty. No documents indexed.")
            return []

        try:
            query_vec = self.bedrock_service.generate_embedding(query)
        except Exception as e:
            logger.error("Failed to generate query embedding: %s", e)
            return []

        # FAISS search if available
        if _HAS_FAISS and self.index is not None and self.index.ntotal > 0:
            q_arr = np.array([query_vec], dtype=np.float32)
            faiss.normalize_L2(q_arr)
            scores, indices = self.index.search(q_arr, min(top_k, self.index.ntotal))
            
            results = []
            for score, idx in zip(scores[0], indices[0]):
                if idx >= 0 and idx < len(self.chunks_metadata):
                    results.append((self.chunks_metadata[idx], float(score)))
            return results

        # NumPy cosine similarity fallback
        q_arr = np.array(query_vec, dtype=np.float32)
        norm_q = np.linalg.norm(q_arr)
        if norm_q > 0:
            q_arr = q_arr / norm_q

        v_arr = np.array(self.vectors, dtype=np.float32)
        norms_v = np.linalg.norm(v_arr, axis=1, keepdims=True)
        norms_v[norms_v == 0] = 1.0
        v_arr_norm = v_arr / norms_v

        sims = np.dot(v_arr_norm, q_arr)
        ranked_indices = np.argsort(-sims)[:top_k]

        results = []
        for idx in ranked_indices:
            results.append((self.chunks_metadata[idx], float(sims[idx])))
        return results

    def sync_all_pdfs(self, pdf_dir: Optional[Union[str, Path]] = None) -> int:
        """
        Inspects PDF directory, computes fingerprints, and indexes newly added or changed PDFs.
        Returns total number of chunks added.
        """
        if not self.bedrock_service.has_credentials():
            logger.info("Bedrock credentials not present locally. PDF embedding synchronization deferred.")
            return 0

        target_dir = Path(pdf_dir or get_default_pdf_dir())
        if not target_dir.exists():
            logger.warning("PDF directory '%s' does not exist", target_dir)
            return 0

        pdf_files = sorted(target_dir.glob("*.pdf"))
        total_added = 0

        # Load all documents once
        all_docs = load_pdf_documents(target_dir)

        for pdf_path in pdf_files:
            try:
                hasher = hashlib.sha256()
                with open(pdf_path, "rb") as f:
                    for chunk in iter(lambda: f.read(65536), b""):
                        hasher.update(chunk)
                file_hash = hasher.hexdigest()

                if self.is_document_indexed(pdf_path.name, file_hash):
                    continue

                current_docs = [d for d in all_docs if d.get("source") == pdf_path.name]
                if current_docs:
                    added = self.add_documents(current_docs, pdf_path.name, file_hash)
                    total_added += added

            except Exception as e:
                logger.error("Failed to sync PDF '%s': %s", pdf_path.name, e)

        return total_added


_GLOBAL_VECTOR_STORE: Optional[FaissVectorStore] = None


def get_vector_store() -> FaissVectorStore:
    global _GLOBAL_VECTOR_STORE
    if _GLOBAL_VECTOR_STORE is None:
        _GLOBAL_VECTOR_STORE = FaissVectorStore()
    return _GLOBAL_VECTOR_STORE
