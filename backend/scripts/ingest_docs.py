"""
Ingestion & Retrieval Validation Script for Real Estate AI Chatbot RAG System.
Migrates PDF documents into ChromaDB collection 'real_estate_documents_v2'
using genuine local Ollama 'nomic-embed-text' embeddings and validates semantic retrieval.
"""

import sys
import os
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.rag.loader import load_pdf_documents
from app.rag.chunker import chunk_documents
from app.rag.store import (
    get_vector_store,
    add_chunks,
    check_ollama_status,
)
from app.rag.retriever import retrieve_relevant_chunks

COLLECTION_V3 = "real_estate_documents_v3_structured"
COLLECTION_V2 = "real_estate_documents_v2"
COLLECTION_V1 = "real_estate_documents"


def run_pipeline():
    print("=" * 80)
    print("STEP 10.1 — REAL OLLAMA EMBEDDING MIGRATION & RETRIEVAL VALIDATION")
    print("=" * 80)

    # 1. Confirm Ollama status
    print("\n[TASK 2] Verifying Ollama Engine & Model...")
    ollama_info = check_ollama_status()
    print(f"   Ollama reachable: {ollama_info['reachable']}")
    print(f"   Ollama version: {ollama_info['version']}")
    print(f"   Model 'nomic-embed-text' ready: {ollama_info['model_available']}")
    if not ollama_info["reachable"]:
        print("\nERROR: Ollama is not running. Please start Ollama with 'ollama serve'.")
        sys.exit(1)
    if not ollama_info["model_available"]:
        print("\nERROR: Model 'nomic-embed-text' not found. Run 'ollama pull nomic-embed-text'.")
        sys.exit(1)

    # 2. Load and Chunk PDFs
    print("\n[TASK 4 & 5] Loading and Chunking Source PDFs from pdf/...")
    docs = load_pdf_documents()
    chunks = chunk_documents(docs)
    print(f"   Extracted {len(docs)} document pages.")
    print(f"   Generated {len(chunks)} semantic chunks.")
    if len(chunks) != 12:
        print(f"   WARNING: Expected 12 chunks, got {len(chunks)}")

    # 3. Access ChromaDB & Ingest into real_estate_documents_v2
    print(f"\n[TASK 3 & 7] Ingesting Genuine Ollama Embeddings into '{COLLECTION_V2}'...")
    client = get_vector_store()

    # Verify existing collection is preserved
    existing_collections = [c.name for c in client.list_collections()]
    print(f"   Existing collections: {existing_collections}")
    if COLLECTION_V1 in existing_collections:
        print(f"   Preserving existing collection: '{COLLECTION_V1}'")

    coll_v2 = client.get_or_create_collection(
        name=COLLECTION_V2,
        metadata={"hnsw:space": "cosine"}
    )
    print(f"   Target collection '{COLLECTION_V2}' ready. Initial count: {coll_v2.count()}")

    ingest_result = add_chunks(
        chunks,
        client=client,
        collection=coll_v2,
        collection_name=COLLECTION_V2,
        metadata={"hnsw:space": "cosine"},
    )
    print(f"   Ingestion result: {ingest_result}")

    # 4. Verify Genuine Vectors, Dimensions & Metadata
    print("\n[TASK 8] Verifying Stored Embeddings...")
    sample = coll_v2.get(include=["embeddings", "metadatas", "documents"], limit=2)
    embs = sample["embeddings"]
    total_stored = coll_v2.count()
    print(f"   Total chunks stored in '{COLLECTION_V2}': {total_stored}")
    print(f"   Embedding dimension: {len(embs[0])}")
    assert len(embs[0]) == 768, "Embedding dimensions must be exactly 768"

    # Verify vectors are genuine floats from Ollama
    first_10 = [round(float(v), 5) for v in embs[0][:10]]
    print(f"   Sample vector preview (first 10 floats): {first_10}")
    # Verify non-mock pattern
    is_genuine = not all(abs(embs[0][i+1] - embs[0][i] - 0.02) < 0.001 for i in range(10))
    print(f"   Verified genuine neural vector: {is_genuine}")
    assert is_genuine, "Vectors must be genuine neural embeddings, not mock test values."

    # Verify cold-start persistence
    print("   Testing persistence across fresh client instance...")
    reopened_client = get_vector_store()
    reopened_coll = reopened_client.get_collection(COLLECTION_V2)
    print(f"   Reopened collection record count: {reopened_coll.count()}")
    assert reopened_coll.count() == 12, "All 12 records must persist"

    if COLLECTION_V1 in existing_collections:
        v1_count = reopened_client.get_collection(COLLECTION_V1).count()
        print(f"   Original collection '{COLLECTION_V1}' count: {v1_count} (preserved)")
        assert v1_count == 12, "Original collection must remain intact at 12 records"

    # 5. Semantic Retrieval Evaluation
    test_queries = [
        "Tell me about the 2BHK model house",
        "What features are available in the 3BHK?",
        "Describe the living room",
        "What is mentioned about bedrooms?",
    ]

    print("\n" + "=" * 80)
    print("[TASK 9 & 10] SEMANTIC RETRIEVAL TEST RESULTS (Cosine Distance: lower = more similar)")
    print("=" * 80)

    for q in test_queries:
        print(f"\n>>> QUERY: \"{q}\"")
        results = retrieve_relevant_chunks(
            query=q,
            top_k=3,
            collection=reopened_coll,
            collection_name=COLLECTION_V2,
        )
        for rank, r in enumerate(results, start=1):
            print(f"  Rank #{rank} | Cosine Dist: {r['distance']:.4f}")
            print(f"    Source: {r['source']} (Page {r['page']})")
            print(f"    Chunk ID: {r['chunk_id']}")
            preview = r['text'].replace('\n', ' ').strip()
            if len(preview) > 130:
                preview = preview[:130] + "..."
            print(f"    Text: {preview}")

    # 6. Source Filtering Validation
    print("\n" + "=" * 80)
    print("[TASK 11] VALIDATING SOURCE FILTERING")
    print("=" * 80)

    source_2bhk = "2BHK + 2T Model House Script - Casagrand Aquagrove.pdf"
    source_3bhk = "3BHK + 3T Model House Script - Casagrand Aquagrove.pdf"

    print(f"\n--- Filtered Query 1: 'living and dining specifications' -> 2BHK ONLY ---")
    res_2bhk = retrieve_relevant_chunks(
        query="living and dining specifications",
        top_k=3,
        source=source_2bhk,
        collection=reopened_coll,
        collection_name=COLLECTION_V2,
    )
    for r in res_2bhk:
        print(f"  * Dist: {r['distance']:.4f} | Source: {r['source']} | Page: {r['page']}")
    assert all(r["source"] == source_2bhk for r in res_2bhk), "All results must be from 2BHK"
    print(f"  Result: All {len(res_2bhk)} results are strictly from 2BHK PDF.")

    print(f"\n--- Filtered Query 2: 'living and dining specifications' -> 3BHK ONLY ---")
    res_3bhk = retrieve_relevant_chunks(
        query="living and dining specifications",
        top_k=3,
        source=source_3bhk,
        collection=reopened_coll,
        collection_name=COLLECTION_V2,
    )
    for r in res_3bhk:
        print(f"  * Dist: {r['distance']:.4f} | Source: {r['source']} | Page: {r['page']}")
    assert all(r["source"] == source_3bhk for r in res_3bhk), "All results must be from 3BHK"
    print(f"  Result: All {len(res_3bhk)} results are strictly from 3BHK PDF.")

    print("\n" + "=" * 80)
    print("SUCCESS: STEP 10.1 COMPLETED AND VALIDATED WITH GENUINE OLLAMA EMBEDDINGS!")
    print("=" * 80)


def run_structured_pipeline():
    print("=" * 80)
    print("STEP 12 — STRUCTURED DOCUMENT INGESTION (COLLECTION V3)")
    print("=" * 80)
    ollama_info = check_ollama_status()
    if not ollama_info["reachable"]:
        print("\nERROR: Ollama is not running. Please start Ollama with 'ollama serve'.")
        sys.exit(1)
    if not ollama_info["model_available"]:
        print("\nERROR: Model 'nomic-embed-text' not found. Run 'ollama pull nomic-embed-text'.")
        sys.exit(1)

    docs = load_pdf_documents()
    chunks = chunk_documents(docs, structured=True)
    print(f"   Loaded {len(docs)} pages, generated {len(chunks)} structured chunks.")

    client = get_vector_store()
    coll_v3 = client.get_or_create_collection(
        name=COLLECTION_V3,
        metadata={"hnsw:space": "cosine"}
    )
    result = add_chunks(chunks, client=client, collection=coll_v3, collection_name=COLLECTION_V3)
    print(f"   Ingestion into '{COLLECTION_V3}': {result}")
    print(f"   Total records in '{COLLECTION_V3}': {coll_v3.count()}")


if __name__ == "__main__":
    if "--v3" in sys.argv:
        run_structured_pipeline()
    else:
        run_pipeline()
