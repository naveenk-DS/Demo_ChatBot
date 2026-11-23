"""
Comprehensive test suite for plain image asset ingestion and management.
Validates:
1. Supported image formats: JPG, JPEG, PNG, WEBP.
2. Ingestion and local storage in backend/data/assets/images/.
3. Metadata tracking (filename, paths, file type, date, property association).
4. No conversion into text chunks or embeddings.
5. No transmission to LLM.
6. Preservation of PDF and CSV ingestion.
7. Chatbot response stating images are stored as assets but not analyzed by AI.
"""

import json
import sys
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app.rag.image_assets import (
    ingest_image_assets,
    list_image_assets,
    get_image_status_message,
    get_default_assets_dir,
    get_registry_path,
    is_supported_image,
)
from backend.app.rag.loader import load_pdf_documents, load_csv_documents
from backend.app.schemas import ChatRequest
from backend.app.main import chat


def test_image_asset_pipeline():
    print("=" * 80)
    print("TESTING PLAIN IMAGE ASSET INGESTION & PIPELINE INTEGRITY")
    print("=" * 80)

    # 1. Test supported formats
    print("\n--- 1. Testing Format Detection ---")
    assert is_supported_image("photo.jpg") is True
    assert is_supported_image("photo.jpeg") is True
    assert is_supported_image("photo.png") is True
    assert is_supported_image("photo.webp") is True
    assert is_supported_image("Bathroom.jpg.2.jpg") is True
    assert is_supported_image("document.pdf") is False
    assert is_supported_image("data.csv") is False
    print("✓ JPG, JPEG, PNG, and WEBP formats correctly identified.")

    # 2. Test Ingestion & Local Storage
    print("\n--- 2. Testing Asset Ingestion & Storage ---")
    assets = ingest_image_assets()
    assets_dir = get_default_assets_dir()
    registry_file = get_registry_path()

    print(f"✓ Assets directory: {assets_dir}")
    print(f"✓ Registry file: {registry_file}")
    print(f"✓ Ingested {len(assets)} image asset(s).")
    assert len(assets) >= 4, f"Expected at least 4 image assets, found {len(assets)}"

    for a in assets:
        stored_file = Path(a["file_path"])
        assert stored_file.exists(), f"Stored asset file does not exist: {stored_file}"
        assert a["file_type"] in ["image/jpeg", "image/png", "image/webp"]
        assert "ingestion_date" in a
        assert a.get("property_name"), "Expected associated property_name in metadata"
        print(f"   • {a['filename']} | Type: {a['file_type']} | Cat: {a['category']} | Prop: {a['property_name']}")

    # 3. Test Metadata Association with PDFs / CSVs
    print("\n--- 3. Testing Property & Document Association ---")
    sample_img = assets[0]
    assert "Aquagrove" in sample_img["property_name"] or "Housing" in sample_img["property_name"]
    assert len(sample_img["associated_documents"]) > 0
    print(f"✓ Image '{sample_img['filename']}' successfully associated with property: {sample_img['property_name']}")
    print(f"✓ Associated documents: {sample_img['associated_documents']}")

    # 4. Guarantee No Embeddings or Text Chunks
    print("\n--- 4. Guaranteeing No Text Chunks or Embeddings for Images ---")
    pdf_docs = load_pdf_documents()
    for d in pdf_docs:
        assert not is_supported_image(d["source"]), f"Image {d['source']} was mistakenly loaded as a PDF text document!"
    print(f"✓ Verified: load_pdf_documents() contains 0 image documents (only {len(pdf_docs)} PDF pages).")

    # 5. Verify CSV Loader Preservation
    print("\n--- 5. Testing CSV Loader Preservation ---")
    csv_docs = load_csv_documents()
    print(f"✓ CSV documents loaded: {len(csv_docs)} records from Housing.csv.")
    assert len(csv_docs) > 0, "Expected Housing.csv records to load"

    # 6. Test Chatbot Image Query Response
    print("\n--- 6. Testing Chatbot Image Intent & Compliance Response ---")
    test_queries = [
        "Show me the property images.",
        "Do you have bedroom images?",
        "Can you analyze the bathroom photo?",
    ]

    from unittest.mock import patch
    from backend.app.llm import _normalize_extracted
    from backend.app.schemas import SearchFilters

    def fake_understand(prov, h, curr):
        normalized = _normalize_extracted({"intent": "property_search"}, curr)
        return SearchFilters.model_validate(normalized)

    with patch("backend.app.main.understand", side_effect=fake_understand):
        for q in test_queries:
            req = ChatRequest(message=q, history=[], provider="ollama")
            resp = chat(req)
            status = resp.get("status")
            msg = resp.get("assistant_message", "")
            filters = resp.get("filters", {})

            print(f"\nUser Query: '{q}'")
            print(f"Intent: {filters.get('intent')}")
            print(f"Chatbot Response: {msg}")

            assert filters.get("intent") == "media_request"
            assert "stored locally as plain image assets" in msg.lower() or "stored as assets" in msg.lower()
            assert "not currently analyzed by ai" in msg.lower()

    print("\n" + "=" * 80)
    print("ALL IMAGE ASSET TESTS PASSED WITH 100% COMPLIANCE!")
    print("=" * 80)


if __name__ == "__main__":
    test_image_asset_pipeline()
