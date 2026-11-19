"""
Dynamic, Scalable Document Retrieval Module for the Real Estate AI Chatbot RAG system.
Supports Dense Vector Retrieval, Dynamic BM25 Lexical Retrieval, and Hybrid Search (RRF)
across any document collection and arbitrary metadata filters.
"""

from collections import Counter
import logging
import math
from pathlib import Path
import re
from typing import Any, Optional, Union

import chromadb
from .store import (
    DEFAULT_COLLECTION_NAME,
    DEFAULT_STRUCTURED_COLLECTION,
    get_embedding,
    get_or_create_collection,
    get_vector_store,
)

logger = logging.getLogger(__name__)

DEFAULT_TOP_K: int = 3
RRF_K: float = 60.0  # Standard Reciprocal Rank Fusion smoothing constant


def tokenize(text: str) -> list[str]:
    """Extracts lowercase alphanumeric word tokens from text."""
    return re.findall(r"\w+", text.lower())


class DynamicBM25:
    """
    In-memory BM25 Okapi index dynamically constructed from any ChromaDB collection.
    Automatically scales with newly ingested documents with zero code modifications.
    """

    def __init__(
        self,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict[str, Any]],
        k1: float = 1.5,
        b: float = 0.75,
    ):
        self.ids = ids
        self.documents = documents
        self.metadatas = metadatas
        self.k1 = k1
        self.b = b
        self.N = len(documents)

        self.tokenized_corpus = [tokenize(d) for d in documents]
        self.doc_lens = [len(d) for d in self.tokenized_corpus]
        self.avgdl = sum(self.doc_lens) / self.N if self.N > 0 else 1.0

        # Document frequencies for all unique tokens
        self.df: Counter = Counter()
        for doc in self.tokenized_corpus:
            for word in set(doc):
                self.df[word] += 1

    def score(
        self,
        query: str,
        where_filter: Optional[dict[str, Any]] = None,
    ) -> list[tuple[str, float]]:
        """
        Scores all indexed documents against a query string, applying optional metadata filters.
        Returns a sorted list of (chunk_id, bm25_score) tuples (descending).
        """
        if self.N == 0:
            return []

        q_tokens = tokenize(query)
        if not q_tokens:
            return []

        scored_results: list[tuple[str, float]] = []

        for idx, doc in enumerate(self.tokenized_corpus):
            # Apply metadata filters if provided
            if where_filter:
                meta = self.metadatas[idx] if idx < len(self.metadatas) else {}
                skip = False
                for k, v in where_filter.items():
                    doc_val = meta.get(k)
                    if isinstance(v, str) and isinstance(doc_val, str):
                        if doc_val.strip().lower() != v.strip().lower():
                            skip = True
                            break
                    elif doc_val != v:
                        skip = True
                        break
                if skip:
                    continue

            score = 0.0
            doc_len = self.doc_lens[idx]
            counts = Counter(doc)

            for q in q_tokens:
                if q not in counts:
                    continue
                n_q = self.df.get(q, 0)
                # BM25 IDF formulation with smoothing
                idf = math.log((self.N - n_q + 0.5) / (n_q + 0.5) + 1.0)
                f = counts[q]
                denom = f + self.k1 * (1.0 - self.b + self.b * (doc_len / self.avgdl))
                score += idf * (f * (self.k1 + 1.0)) / denom

            if score > 0.0:
                scored_results.append((self.ids[idx], score))

        return sorted(scored_results, key=lambda x: x[1], reverse=True)


def _build_where_filter(
    source: Optional[str] = None,
    property_name: Optional[str] = None,
    configuration: Optional[str] = None,
    category: Optional[str] = None,
    filter_metadata: Optional[dict[str, Any]] = None,
) -> tuple[dict[str, Any], Optional[dict[str, Any]]]:
    """
    Constructs normalized metadata filter dictionary and ChromaDB-compatible `where` clause.
    """
    combined_filter: dict[str, Any] = {}
    if source and source.strip():
        combined_filter["source"] = source.strip()
    if property_name and property_name.strip():
        combined_filter["property_name"] = property_name.strip()
    if configuration and configuration.strip():
        combined_filter["configuration"] = configuration.strip().upper()
    if category and category.strip():
        combined_filter["category"] = category.strip().lower()
    if filter_metadata:
        combined_filter.update(filter_metadata)

    chroma_where: Optional[dict[str, Any]] = None
    if len(combined_filter) == 1:
        chroma_where = combined_filter
    elif len(combined_filter) > 1:
        chroma_where = {"$and": [{k: v} for k, v in combined_filter.items()]}

    return combined_filter, chroma_where


def dense_search(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    configuration: Optional[str] = None,
    category: Optional[str] = None,
    source: Optional[str] = None,
    property_name: Optional[str] = None,
    filter_metadata: Optional[dict[str, Any]] = None,
    client: Optional[chromadb.PersistentClient] = None,
    collection: Optional[chromadb.Collection] = None,
    collection_name: str = DEFAULT_STRUCTURED_COLLECTION,
) -> list[dict[str, Any]]:
    """
    Dense vector search against ChromaDB using Ollama embeddings.
    """
    if not query or not query.strip():
        raise ValueError("Search query cannot be empty or whitespace.")

    coll = collection or get_or_create_collection(
        client=client, collection_name=collection_name
    )
    total_records = coll.count()
    if total_records == 0:
        logger.warning("ChromaDB collection '%s' is empty.", coll.name)
        return []

    combined_filter, chroma_where = _build_where_filter(
        source=source,
        property_name=property_name,
        configuration=configuration,
        category=category,
        filter_metadata=filter_metadata,
    )

    clean_query = query.strip()
    q_emb = get_embedding(clean_query)
    n_fetch = min(max(top_k * 4, 25), total_records)

    q_params: dict[str, Any] = {
        "query_embeddings": [q_emb],
        "n_results": n_fetch,
        "include": ["documents", "metadatas", "distances"],
    }
    if chroma_where:
        q_params["where"] = chroma_where

    res = coll.query(**q_params)
    d_ids = res.get("ids", [[]])[0]
    d_docs = res.get("documents", [[]])[0]
    d_metas = res.get("metadatas", [[]])[0]
    d_dists = res.get("distances", [[]])[0]

    results: list[dict[str, Any]] = []
    for rank, cid in enumerate(d_ids[:top_k], start=1):
        idx = rank - 1
        meta = d_metas[idx] if idx < len(d_metas) else {}
        dist = float(d_dists[idx]) if idx < len(d_dists) else 0.0
        item = {
            "rank": rank,
            "chunk_id": cid,
            "text": d_docs[idx] if idx < len(d_docs) else "",
            "source": meta.get("source", "unknown"),
            "page": int(meta.get("page", 1)),
            "property_name": meta.get("property_name", ""),
            "configuration": meta.get("configuration", ""),
            "category": meta.get("category", ""),
            "dense_distance": round(dist, 4),
            "bm25_score": None,
            "rrf_score": round(1.0 / (RRF_K + rank), 6),
            "distance": round(dist, 4),
        }
        for k, v in meta.items():
            if k not in item:
                item[k] = v
        results.append(item)

    return results


def bm25_search(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    configuration: Optional[str] = None,
    category: Optional[str] = None,
    source: Optional[str] = None,
    property_name: Optional[str] = None,
    filter_metadata: Optional[dict[str, Any]] = None,
    client: Optional[chromadb.PersistentClient] = None,
    collection: Optional[chromadb.Collection] = None,
    collection_name: str = DEFAULT_STRUCTURED_COLLECTION,
) -> list[dict[str, Any]]:
    """
    BM25 lexical search dynamically indexing documents from the specified ChromaDB collection.
    """
    if not query or not query.strip():
        raise ValueError("Search query cannot be empty or whitespace.")

    coll = collection or get_or_create_collection(
        client=client, collection_name=collection_name
    )
    total_records = coll.count()
    if total_records == 0:
        logger.warning("ChromaDB collection '%s' is empty.", coll.name)
        return []

    combined_filter, _ = _build_where_filter(
        source=source,
        property_name=property_name,
        configuration=configuration,
        category=category,
        filter_metadata=filter_metadata,
    )

    clean_query = query.strip()
    all_data = coll.get(include=["documents", "metadatas"])
    bm25_index = DynamicBM25(
        ids=all_data["ids"],
        documents=all_data["documents"],
        metadatas=all_data["metadatas"],
    )
    scored = bm25_index.score(clean_query, where_filter=combined_filter)

    results: list[dict[str, Any]] = []
    id_map = {cid: idx for idx, cid in enumerate(all_data["ids"])}

    for rank, (cid, score) in enumerate(scored[:top_k], start=1):
        idx = id_map[cid]
        meta = all_data["metadatas"][idx]
        item = {
            "rank": rank,
            "chunk_id": cid,
            "text": all_data["documents"][idx],
            "source": meta.get("source", "unknown"),
            "page": int(meta.get("page", 1)),
            "property_name": meta.get("property_name", ""),
            "configuration": meta.get("configuration", ""),
            "category": meta.get("category", ""),
            "dense_distance": None,
            "bm25_score": round(score, 4),
            "rrf_score": round(1.0 / (RRF_K + rank), 6),
            "distance": round(1.0 / (1.0 + score), 4),
        }
        for k, v in meta.items():
            if k not in item:
                item[k] = v
        results.append(item)

    return results


def hybrid_search(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    configuration: Optional[str] = None,
    category: Optional[str] = None,
    source: Optional[str] = None,
    property_name: Optional[str] = None,
    filter_metadata: Optional[dict[str, Any]] = None,
    rrf_k: float = RRF_K,
    client: Optional[chromadb.PersistentClient] = None,
    collection: Optional[chromadb.Collection] = None,
    collection_name: str = DEFAULT_STRUCTURED_COLLECTION,
) -> list[dict[str, Any]]:
    """
    Dedicated Hybrid Retrieval combining Dense Vector Search + BM25 Keyword Search
    fused with Reciprocal Rank Fusion (RRF: score = sum(1 / (k + rank))).

    Args:
        query: User search query.
        top_k: Number of ranked chunks to return (default: 3).
        configuration: Optional unit filter (e.g. '2BHK', '3BHK').
        category: Optional category filter (e.g. 'bedroom', 'entrance', 'kitchen').
        source: Optional PDF source filename filter.
        property_name: Optional property name filter.
        filter_metadata: Additional arbitrary metadata filters.
        rrf_k: Reciprocal Rank Fusion constant (default: 60.0).
        client: Optional active ChromaDB PersistentClient.
        collection: Optional ChromaDB Collection instance.
        collection_name: Target collection (default: 'real_estate_documents_v3_structured').

    Returns:
        Enriched list of ranked chunk dictionaries containing:
        - chunk_id
        - text
        - source
        - page
        - property_name
        - configuration
        - category
        - dense_distance (float or None)
        - bm25_score (float or None)
        - rrf_score (float)
        - rank (int: 1, 2, ...)
    """
    if not query or not query.strip():
        raise ValueError("Search query cannot be empty or whitespace.")

    if not isinstance(top_k, int) or top_k <= 0:
        raise ValueError(f"top_k must be a positive integer, got {top_k}")

    coll = collection or get_or_create_collection(
        client=client, collection_name=collection_name
    )

    total_records = coll.count()
    if total_records == 0:
        logger.warning("ChromaDB collection '%s' is empty.", coll.name)
        return []

    combined_filter, chroma_where = _build_where_filter(
        source=source,
        property_name=property_name,
        configuration=configuration,
        category=category,
        filter_metadata=filter_metadata,
    )

    clean_query = query.strip()
    logger.debug("=== HYBRID RETRIEVAL START: Query='%s' (top_k=%d, rrf_k=%.1f) ===", clean_query, top_k, rrf_k)
    if combined_filter:
        logger.debug("Applied metadata filters: %s", combined_filter)

    dense_ranks: dict[str, int] = {}
    dense_distances: dict[str, float] = {}
    bm25_ranks: dict[str, int] = {}
    bm25_scores: dict[str, float] = {}
    records_by_id: dict[str, dict[str, Any]] = {}

    # 1. Dense Vector Retrieval
    try:
        q_emb = get_embedding(clean_query)
        n_fetch = min(max(top_k * 4, 25), total_records)
        q_params: dict[str, Any] = {
            "query_embeddings": [q_emb],
            "n_results": n_fetch,
            "include": ["documents", "metadatas", "distances"],
        }
        if chroma_where:
            q_params["where"] = chroma_where

        res = coll.query(**q_params)
        d_ids = res.get("ids", [[]])[0]
        d_docs = res.get("documents", [[]])[0]
        d_metas = res.get("metadatas", [[]])[0]
        d_dists = res.get("distances", [[]])[0]

        logger.debug("--- DENSE SEARCH CANDIDATES (count=%d) ---", len(d_ids))
        for rank, cid in enumerate(d_ids, start=1):
            dense_ranks[cid] = rank
            dist = float(d_dists[rank - 1]) if rank - 1 < len(d_dists) else 0.0
            dense_distances[cid] = dist
            records_by_id[cid] = {
                "text": d_docs[rank - 1] if rank - 1 < len(d_docs) else "",
                "meta": d_metas[rank - 1] if rank - 1 < len(d_metas) else {},
            }
            logger.debug("  [Dense #%d] ID: %s | Distance: %.4f", rank, cid, dist)
    except Exception as dense_err:
        logger.warning("Dense vector retrieval failed (%s); proceeding with BM25 only.", dense_err)

    # 2. Dynamic BM25 Lexical Retrieval
    try:
        all_data = coll.get(include=["documents", "metadatas"])
        bm25_index = DynamicBM25(
            ids=all_data["ids"],
            documents=all_data["documents"],
            metadatas=all_data["metadatas"],
        )
        scored_bm25 = bm25_index.score(clean_query, where_filter=combined_filter)

        logger.debug("--- BM25 SEARCH CANDIDATES (count=%d) ---", len(scored_bm25))
        for rank, (cid, score) in enumerate(scored_bm25, start=1):
            bm25_ranks[cid] = rank
            bm25_scores[cid] = score
            if cid not in records_by_id:
                idx = all_data["ids"].index(cid)
                records_by_id[cid] = {
                    "text": all_data["documents"][idx],
                    "meta": all_data["metadatas"][idx],
                }
            if rank <= 15:
                logger.debug("  [BM25 #%d] ID: %s | Score: %.4f", rank, cid, score)
    except Exception as bm25_err:
        logger.warning("BM25 lexical retrieval failed (%s); proceeding with Dense only.", bm25_err)

    # 3. Reciprocal Rank Fusion (RRF)
    candidate_ids = set(dense_ranks.keys()) | set(bm25_ranks.keys())
    if not candidate_ids:
        logger.warning("No candidates found by either Dense or BM25 retrieval for '%s'", clean_query)
        return []

    fused_candidates: list[tuple[str, float, Optional[int], Optional[int]]] = []
    for cid in candidate_ids:
        d_rank = dense_ranks.get(cid)
        b_rank = bm25_ranks.get(cid)

        rrf_dense = 1.0 / (rrf_k + d_rank) if d_rank is not None else 0.0
        rrf_bm25 = 1.0 / (rrf_k + b_rank) if b_rank is not None else 0.0
        fused_score = rrf_dense + rrf_bm25

        fused_candidates.append((cid, fused_score, d_rank, b_rank))

    # Sort descending by fused RRF score
    fused_candidates.sort(key=lambda x: x[1], reverse=True)
    top_candidates = fused_candidates[:top_k]

    logger.debug("--- HYBRID RRF FUSED RANKING (top %d of %d candidates) ---", len(top_candidates), len(fused_candidates))
    for rank, (cid, rrf_score, d_rank, b_rank) in enumerate(top_candidates, start=1):
        logger.debug(
            "  [Hybrid #%d] ID: %s | RRF Score: %.6f | Dense Rank: %s | BM25 Rank: %s",
            rank, cid, rrf_score, str(d_rank), str(b_rank)
        )

    # 4. Construct enriched output dictionaries
    output: list[dict[str, Any]] = []
    for rank, (cid, rrf_score, d_rank, b_rank) in enumerate(top_candidates, start=1):
        rec = records_by_id[cid]
        meta = rec.get("meta", {})
        d_dist = round(dense_distances[cid], 4) if cid in dense_distances else None
        b_sc = round(bm25_scores[cid], 4) if cid in bm25_scores else None

        item: dict[str, Any] = {
            "rank": rank,
            "chunk_id": cid,
            "text": rec.get("text", ""),
            "source": meta.get("source", "unknown"),
            "page": int(meta.get("page", 1)),
            "property_name": meta.get("property_name", ""),
            "configuration": meta.get("configuration", ""),
            "category": meta.get("category", ""),
            "dense_distance": d_dist,
            "bm25_score": b_sc,
            "rrf_score": round(rrf_score, 6),
            # Backward-compatible convenience aliases
            "distance": d_dist if d_dist is not None else 1.0,
            "score": round(rrf_score, 6),
        }
        for k, v in meta.items():
            if k not in item:
                item[k] = v

        output.append(item)

    logger.info(
        "Hybrid search returned %d chunk(s) for query='%s' (Dense candidates: %d, BM25 candidates: %d)",
        len(output), clean_query, len(dense_ranks), len(bm25_ranks)
    )
    return output


# Dedicated hybrid retrieval alias
retrieve_hybrid = hybrid_search


def retrieve_relevant_chunks(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    mode: str = "hybrid",
    source: Optional[str] = None,
    property_name: Optional[str] = None,
    configuration: Optional[str] = None,
    category: Optional[str] = None,
    filter_metadata: Optional[dict[str, Any]] = None,
    client: Optional[chromadb.PersistentClient] = None,
    collection: Optional[chromadb.Collection] = None,
    collection_name: str = DEFAULT_COLLECTION_NAME,
) -> list[dict[str, Any]]:
    """
    Backward-compatible document retrieval function supporting Dense, BM25, and Hybrid strategies.
    Defaults to collection_name='real_estate_documents' for existing compatibility.
    """
    if mode == "dense":
        return dense_search(
            query=query,
            top_k=top_k,
            configuration=configuration,
            category=category,
            source=source,
            property_name=property_name,
            filter_metadata=filter_metadata,
            client=client,
            collection=collection,
            collection_name=collection_name,
        )
    elif mode == "bm25":
        return bm25_search(
            query=query,
            top_k=top_k,
            configuration=configuration,
            category=category,
            source=source,
            property_name=property_name,
            filter_metadata=filter_metadata,
            client=client,
            collection=collection,
            collection_name=collection_name,
        )
    else:
        # Default: hybrid search
        return hybrid_search(
            query=query,
            top_k=top_k,
            configuration=configuration,
            category=category,
            source=source,
            property_name=property_name,
            filter_metadata=filter_metadata,
            client=client,
            collection=collection,
            collection_name=collection_name,
        )


retrieve = retrieve_relevant_chunks
