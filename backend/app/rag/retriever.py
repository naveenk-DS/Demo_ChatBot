"""
Hybrid Retriever for EstateAI RAG.
Combines BM25 keyword search with Amazon Bedrock Titan v2 vector search
from the FaissVectorStore.
Uses Reciprocal Rank Fusion (RRF) for optimal precision across engineering specifications
and conversational property inquiries.
"""

import logging
import math
import re
from collections import Counter
from typing import Any, Optional

from app.rag.store import get_vector_store

logger = logging.getLogger("estateai.retriever")

DEFAULT_TOP_K = 5
RRF_K = 60  # Standard smoothing constant for Reciprocal Rank Fusion


class DynamicBM25:
    """Lightweight in-memory BM25 index over chunk text."""

    def __init__(self, chunks: list[dict[str, Any]], k1: float = 1.5, b: float = 0.75):
        self.chunks = chunks
        self.k1 = k1
        self.b = b
        self.corpus_size = len(chunks)
        self.doc_lens = []
        self.doc_freqs: dict[str, int] = Counter()
        self.doc_term_freqs: list[dict[str, int]] = []

        total_tokens = 0
        for c in chunks:
            text = c.get("text", "")
            tokens = self._tokenize(text)
            self.doc_lens.append(len(tokens))
            total_tokens += len(tokens)
            
            tf = Counter(tokens)
            self.doc_term_freqs.append(tf)
            for t in tf.keys():
                self.doc_freqs[t] += 1

        self.avg_dl = (total_tokens / self.corpus_size) if self.corpus_size > 0 else 1.0

    def _tokenize(self, text: str) -> list[str]:
        cleaned = re.sub(r"[^\w\s\.-]", " ", text.lower())
        return [w for w in cleaned.split() if len(w) > 1]

    def score(self, query: str, top_k: int = 10) -> list[tuple[int, float]]:
        """Scores documents against query using BM25 formula."""
        if not self.chunks:
            return []

        q_tokens = self._tokenize(query)
        if not q_tokens:
            return []

        scores = [0.0] * self.corpus_size

        for token in q_tokens:
            df = self.doc_freqs.get(token, 0)
            if df == 0:
                continue

            idf = math.log((self.corpus_size - df + 0.5) / (df + 0.5) + 1.0)
            idf = max(idf, 0.0)

            for doc_idx in range(self.corpus_size):
                tf = self.doc_term_freqs[doc_idx].get(token, 0)
                if tf > 0:
                    dl = self.doc_lens[doc_idx]
                    denom = tf + self.k1 * (1.0 - self.b + self.b * (dl / self.avg_dl))
                    scores[doc_idx] += idf * (tf * (self.k1 + 1.0) / denom)

        ranked = [(idx, scores[idx]) for idx in range(self.corpus_size) if scores[idx] > 0]
        ranked.sort(key=lambda x: x[1], reverse=True)
        return ranked[:top_k]


def hybrid_search(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    bhk: Optional[int] = None,
    category: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    Executes hybrid search combining Bedrock Titan v2 vector search and BM25 text search.
    Merges ranks using Reciprocal Rank Fusion (RRF).
    """
    store = get_vector_store()
    all_chunks = store.chunks_metadata
    if not all_chunks:
        return []

    # 1. Vector Search via Bedrock Titan v2
    vector_results = store.search(query, top_k=top_k * 2)

    # 2. BM25 Keyword Search
    bm25 = DynamicBM25(all_chunks)
    bm25_results = bm25.score(query, top_k=top_k * 2)

    # 3. Reciprocal Rank Fusion (RRF)
    rrf_scores: dict[int, float] = Counter()

    for rank, (chunk, _) in enumerate(vector_results, start=1):
        # Find index in all_chunks
        try:
            doc_idx = all_chunks.index(chunk)
            rrf_scores[doc_idx] += 1.0 / (RRF_K + rank)
        except ValueError:
            pass

    for rank, (doc_idx, _) in enumerate(bm25_results, start=1):
        rrf_scores[doc_idx] += 1.0 / (RRF_K + rank)

    # Sort candidates by combined RRF score
    sorted_candidates = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

    final_chunks: list[dict[str, Any]] = []
    for doc_idx, score in sorted_candidates:
        c = all_chunks[doc_idx]
        
        # Apply metadata filtering if specified
        if bhk is not None:
            c_config = str(c.get("configuration", "")).lower()
            if f"{bhk}bhk" not in c_config and c_config not in ("general", "specifications"):
                continue

        if category:
            c_cat = str(c.get("category", "")).lower()
            if category.lower() not in c_cat and c_cat != "general":
                continue

        c_copy = dict(c)
        c_copy["relevance_score"] = round(score, 4)
        final_chunks.append(c_copy)
        if len(final_chunks) >= top_k:
            break

    # If metadata filtering was too restrictive, return top unfiltered
    if not final_chunks and sorted_candidates:
        for doc_idx, score in sorted_candidates[:top_k]:
            c_copy = dict(all_chunks[doc_idx])
            c_copy["relevance_score"] = round(score, 4)
            final_chunks.append(c_copy)

    return final_chunks


def retrieve_relevant_chunks(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    bhk: Optional[int] = None,
    category: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Primary retrieval entrypoint for chat orchestration."""
    return hybrid_search(query=query, top_k=top_k, bhk=bhk, category=category)
