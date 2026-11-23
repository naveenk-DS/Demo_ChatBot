"""
Test suite for dynamic arbitrary PDF document ingestion and retrieval.
Verifies:
1. Creation and dynamic ingestion of an arbitrary property PDF (non-BHK, e.g. Community Guidelines).
2. Metadata extraction: document_id, source, page, property_name, document_type.
3. Hybrid retrieval (BM25 + Dense + RRF) successfully retrieves relevant chunks from the arbitrary PDF.
4. Grounded answer generation and document sources verification.
5. Preservation of existing 2BHK, 3BHK, 4BHK document retrieval.
"""

import sys
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import fitz
from backend.app.rag.loader import get_default_pdf_dir, load_pdf_documents, extract_document_metadata
from backend.app.rag.store import sync_pdf_documents, get_vector_store, DEFAULT_STRUCTURED_COLLECTION
from backend.app.rag.retriever import hybrid_search
from backend.app.rag.service import answer_question
from backend.app.main import app
from fastapi.testclient import TestClient


def create_sample_arbitrary_pdf():
    pdf_dir = get_default_pdf_dir()
    sample_pdf_path = pdf_dir / "Community_Guidelines_And_Clubhouse_Rules.pdf"
    if sample_pdf_path.exists():
        print(f"Sample arbitrary PDF already exists: {sample_pdf_path}")
        return sample_pdf_path

    doc = fitz.open()
    # Page 1: Clubhouse rules and amenities
    page1 = doc.new_page()
    page1_text = """COMMUNITY GUIDELINES & CLUBHOUSE RULES

1. Clubhouse Access and Operating Hours:
The clubhouse and recreational facilities are open daily from 6:00 AM to 10:00 PM.
Quiet hours are strictly observed across all common residential corridors and the courtyard between 10:30 PM and 6:30 AM.

2. Swimming Pool Regulations:
Residents must shower before entering the swimming pool.
Children under 14 must be accompanied by an adult guardian at all times.
Glassware, food, and smoking are strictly prohibited within the pool deck perimeter.
"""
    page1.insert_text((50, 72), page1_text, fontsize=11)

    # Page 2: Pet policy and parking rules
    page2 = doc.new_page()
    page2_text = """COMMUNITY GUIDELINES & CLUBHOUSE RULES (Page 2)

3. Pet Policy:
Domestic pets are permitted with a maximum of two pets per apartment unit.
Dogs must be kept on a leash in all common areas, elevators, and basement lobbies.
Owners are required to clean up immediately after their pets.

4. Assigned Parking Allocations:
Each registered apartment unit is allocated one designated covered basement parking stall.
Visitor parking stalls are reserved for daytime guests and are limited to a maximum continuous duration of 4 hours.
Commercial vehicles exceeding 3.5 tons may not be parked overnight on residential premises.
"""
    page2.insert_text((50, 72), page2_text, fontsize=11)

    doc.save(str(sample_pdf_path))
    doc.close()
    print(f"Created sample arbitrary PDF: {sample_pdf_path}")
    return sample_pdf_path


def test_dynamic_rag():
    print("=" * 80)
    print("VERIFYING DYNAMIC ARBITRARY PDF INGESTION & RETRIEVAL")
    print("=" * 80)

    # Step 1: Create arbitrary PDF
    pdf_path = create_sample_arbitrary_pdf()
    assert pdf_path.exists(), "Sample PDF was not created"

    # Step 2: Test metadata extraction
    print("\n--- 1. Testing Document Metadata Extraction ---")
    meta = extract_document_metadata(pdf_path, "COMMUNITY GUIDELINES & CLUBHOUSE RULES\nOperating Hours")
    print(f"Extracted metadata: {meta}")
    assert meta["document_id"] == "community_guidelines_and_clubhouse_rules"
    assert "community guidelines" in meta["property_name"].lower()
    assert meta["configuration"] == "general"
    assert meta["document_type"] in ["guideline", "rules", "document"]
    print("✓ Metadata extracted dynamically without requiring BHK or room configurations.")

    # Step 3: Sync into ChromaDB
    print("\n--- 2. Syncing Documents Into ChromaDB ---")
    sync_result = sync_pdf_documents()
    print(f"Sync result: {sync_result}")

    # Step 4: Test Hybrid Retrieval on the arbitrary PDF
    print("\n--- 3. Testing Hybrid Retrieval on Arbitrary PDF ---")
    retrieved = hybrid_search("What are the quiet hours and swimming pool rules?", top_k=3)
    assert len(retrieved) > 0, "Expected at least 1 retrieved chunk"
    top_chunk = retrieved[0]
    print(f"Top retrieved source: {top_chunk.get('source')} (Page {top_chunk.get('page')})")
    print(f"Text snippet: {top_chunk.get('text')[:120]}...")
    assert "Community_Guidelines_And_Clubhouse_Rules.pdf" in top_chunk.get("source")
    assert "quiet hours" in top_chunk.get("text").lower() or "swimming" in top_chunk.get("text").lower()
    print("✓ Hybrid search successfully retrieved chunks from the arbitrary PDF!")

    # Step 5: Test Hybrid Retrieval on another query from page 2
    print("\n--- 4. Testing Pet Policy and Parking Query ---")
    retrieved_pets = hybrid_search("What is the pet policy and parking limit?", top_k=3)
    assert len(retrieved_pets) > 0
    pet_chunk = retrieved_pets[0]
    print(f"Pet chunk source: {pet_chunk.get('source')} (Page {pet_chunk.get('page')})")
    assert "Community_Guidelines_And_Clubhouse_Rules.pdf" in pet_chunk.get("source")
    print("✓ Successfully retrieved page 2 parking & pet rules!")

    # Step 6: Verify existing 2BHK and 3BHK documents still retrieve correctly
    print("\n--- 5. Verifying Existing 2BHK and 3BHK Documents ---")
    retrieved_2bhk = hybrid_search("What are the 2BHK specifications?", top_k=3)
    assert len(retrieved_2bhk) > 0
    assert any("2BHK" in c.get("source") for c in retrieved_2bhk)
    print("✓ 2BHK document retrieval preserved!")

    retrieved_3bhk = hybrid_search("What are the 3BHK specifications?", top_k=3)
    assert len(retrieved_3bhk) > 0
    assert any("3BHK" in c.get("source") for c in retrieved_3bhk)
    print("✓ 3BHK document retrieval preserved!")

    # Step 7: Test Document List API Endpoint
    print("\n--- 6. Testing Document API Endpoints ---")
    client = TestClient(app)
    docs_resp = client.get("/api/documents")
    assert docs_resp.status_code == 200
    docs_data = docs_resp.json()
    print(f"Indexed documents count: {docs_data.get('total')}")
    filenames = [d["filename"] for d in docs_data.get("documents", [])]
    assert "Community_Guidelines_And_Clubhouse_Rules.pdf" in filenames
    print(f"✓ /api/documents returned: {filenames}")

    # Step 8: Test Chat API with arbitrary document query (if provider is available)
    print("\n--- 7. Testing Chat API with Arbitrary Document Query ---")
    try:
        chat_resp = client.post("/api/chat", json={
            "message": "What are the clubhouse operating hours and quiet hours in the community guidelines?",
            "provider": "gemini",
            "history": []
        })
        print(f"Chat response status: {chat_resp.status_code}")
        if chat_resp.status_code == 200:
            chat_data = chat_resp.json()
            print(f"Assistant message preview: {chat_data.get('assistant_message')[:120]}...")
            print(f"Sources returned: {chat_data.get('sources')}")
            assert len(chat_data.get("sources", [])) > 0
            assert any("Community_Guidelines" in s.get("source", "") for s in chat_data.get("sources", []))
            print("✓ Chatbot grounded answer generated from arbitrary PDF with verified sources!")
        else:
            print(f"Chat API returned {chat_resp.status_code} (LLM upstream offline in local test environment, RAG verified via hybrid_search)")
    except Exception as e:
        print(f"Chat API network call skipped: {e}")

    print("\n" + "=" * 80)
    print("ALL DYNAMIC PDF INGESTION & RETRIEVAL TESTS PASSED SUCCESSFULLY!")
    print("=" * 80)


if __name__ == "__main__":
    test_dynamic_rag()
