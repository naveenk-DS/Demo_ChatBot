"""
Step 13: Hybrid Retrieval Verification Script.
Evaluates Dense Vector Search, BM25 Lexical Search, and Hybrid RRF Fusion
against collection 'real_estate_documents_v3_structured'.
"""

import logging
from pathlib import Path
import sys

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

# Configure logging with DEBUG level to verify debug logs
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
# Reduce noisy logs from urllib3 / chromadb
logging.getLogger("chromadb").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

from app.rag.retriever import (
    hybrid_search,
    dense_search,
    bm25_search,
    retrieve_relevant_chunks,
    DEFAULT_STRUCTURED_COLLECTION,
)
from app.rag.store import get_vector_store, check_ollama_status


def print_comparison(title: str, query: str, filters: dict, dense_res: list, bm25_res: list, hybrid_res: list):
    print("\n" + "=" * 90)
    print(f"TEST CASE: {title}")
    print(f"QUERY: \"{query}\"")
    if filters:
        print(f"FILTERS: {filters}")
    print("=" * 90)

    print("\n--- [1] DENSE SEARCH (Semantic / Neural Embeddings) ---")
    for r in dense_res[:3]:
        text_preview = r["text"].replace("\n", " ").strip()[:100]
        print(f"  Rank #{r['rank']} | Dist: {r['dense_distance']} | Chunk: {r['chunk_id']} | Cat: {r.get('category')} | Config: {r.get('configuration')}")
        print(f"    Preview: \"{text_preview}...\"")

    print("\n--- [2] BM25 SEARCH (Lexical / Exact Keyword Matching) ---")
    if not bm25_res:
        print("  (No lexical matches found)")
    for r in bm25_res[:3]:
        text_preview = r["text"].replace("\n", " ").strip()[:100]
        print(f"  Rank #{r['rank']} | BM25 Score: {r['bm25_score']} | Chunk: {r['chunk_id']} | Cat: {r.get('category')} | Config: {r.get('configuration')}")
        print(f"    Preview: \"{text_preview}...\"")

    print("\n--- [3] HYBRID RRF FUSED (Dense + BM25 + Reciprocal Rank Fusion k=60) ---")
    for r in hybrid_res[:3]:
        text_preview = r["text"].replace("\n", " ").strip()[:100]
        d_dist = r['dense_distance'] if r['dense_distance'] is not None else "N/A"
        b_sc = r['bm25_score'] if r['bm25_score'] is not None else "N/A"
        print(f"  Rank #{r['rank']} | RRF Score: {r['rrf_score']:.6f} | Dense Dist: {d_dist} | BM25 Score: {b_sc}")
        print(f"    Chunk ID: {r['chunk_id']} | Cat: {r.get('category')} | Config: {r.get('configuration')} | Page: {r.get('page')}")
        print(f"    Preview: \"{text_preview}...\"")


def main():
    print("================================================================================")
    print("STEP 13: HYBRID RETRIEVAL (DENSE + BM25 + RECIPROCAL RANK FUSION)")
    print("================================================================================")

    # 1. Verify Ollama & Vector Database
    print("\n[CHECK] Verifying Environment...")
    ollama_info = check_ollama_status()
    print(f"  Ollama Reachable: {ollama_info['reachable']}")
    if not ollama_info["reachable"]:
        print("  ERROR: Ollama is not accessible. Please ensure Ollama is running.")
        sys.exit(1)

    client = get_vector_store()
    coll = client.get_collection(DEFAULT_STRUCTURED_COLLECTION)
    count = coll.count()
    print(f"  Target Collection: '{DEFAULT_STRUCTURED_COLLECTION}' (Record Count: {count})")
    assert count > 0, "Target collection must not be empty"

    # Define test suite
    test_cases = [
        {
            "title": "Query 1: General Semantic Dimension Query",
            "query": "What is the living room size?",
            "filters": {},
            "config": None,
            "category": None,
        },
        {
            "title": "Query 2: Keyword & Specification Query",
            "query": "Kitchen specifications",
            "filters": {},
            "config": None,
            "category": None,
        },
        {
            "title": "Query 3: Master Bedroom Query",
            "query": "What is the master bedroom size?",
            "filters": {},
            "config": None,
            "category": None,
        },
        {
            "title": "Query 4: Filtered Metadata Query (2BHK, Entrance)",
            "query": "2BHK entrance features",
            "filters": {"configuration": "2BHK", "category": "entrance"},
            "config": "2BHK",
            "category": "entrance",
        },
        {
            "title": "Query 5: Filtered Metadata Query (3BHK, Bedroom)",
            "query": "3BHK bedroom features",
            "filters": {"configuration": "3BHK", "category": "bedroom"},
            "config": "3BHK",
            "category": "bedroom",
        },
        {
            "title": "Query 6: Exact Dimension & Keyword Query",
            "query": "7' 9\" grand main door with double side veneer finish",
            "filters": {},
            "config": None,
            "category": None,
        },
        {
            "title": "Query 7: Exact Numerical Dimension Query",
            "query": "12' x 24' 3\" living and dining",
            "filters": {},
            "config": None,
            "category": None,
        },
    ]

    all_passed = True
    required_keys = {
        "chunk_id", "text", "source", "page", "property_name",
        "configuration", "category", "dense_distance", "bm25_score",
        "rrf_score", "rank"
    }

    for tc in test_cases:
        q = tc["query"]
        cfg = tc["config"]
        cat = tc["category"]

        # Run Dense
        dense_res = dense_search(
            query=q,
            top_k=3,
            configuration=cfg,
            category=cat,
            collection=coll,
            collection_name=DEFAULT_STRUCTURED_COLLECTION,
        )

        # Run BM25
        bm25_res = bm25_search(
            query=q,
            top_k=3,
            configuration=cfg,
            category=cat,
            collection=coll,
            collection_name=DEFAULT_STRUCTURED_COLLECTION,
        )

        # Run Hybrid
        hybrid_res = hybrid_search(
            query=q,
            top_k=3,
            configuration=cfg,
            category=cat,
            collection=coll,
            collection_name=DEFAULT_STRUCTURED_COLLECTION,
        )

        print_comparison(tc["title"], q, tc["filters"], dense_res, bm25_res, hybrid_res)

        # Verification checks
        if not hybrid_res:
            print(f"FAILED: No results returned for query: '{q}'")
            all_passed = False
            continue

        # Check required fields
        for r in hybrid_res:
            missing = required_keys - set(r.keys())
            if missing:
                print(f"FAILED: Missing keys in hybrid result: {missing}")
                all_passed = False

            # Check metadata filtering accuracy
            if cfg and r.get("configuration") != cfg:
                print(f"FAILED: Configuration filter mismatch. Expected {cfg}, got {r.get('configuration')}")
                all_passed = False
            if cat and r.get("category") != cat:
                print(f"FAILED: Category filter mismatch. Expected {cat}, got {r.get('category')}")
                all_passed = False

    # Test backward compatibility
    print("\n" + "=" * 90)
    print("TESTING BACKWARD COMPATIBILITY: retrieve_relevant_chunks()")
    print("=" * 90)
    compat_res = retrieve_relevant_chunks(
        query="living room features",
        top_k=2,
        collection=coll,
        collection_name=DEFAULT_STRUCTURED_COLLECTION,
    )
    print(f"  retrieve_relevant_chunks() returned {len(compat_res)} items successfully.")
    assert len(compat_res) > 0
    assert "chunk_id" in compat_res[0]
    assert "distance" in compat_res[0]
    assert "score" in compat_res[0]
    print("  Backward compatibility PASSED!")

    print("\n" + "=" * 90)
    if all_passed:
        print("ALL STEP 13 HYBRID RETRIEVAL TESTS PASSED SUCCESSFULLY!")
    else:
        print("SOME TESTS FAILED — CHECK LOGS ABOVE")
    print("=" * 90)


if __name__ == "__main__":
    main()
