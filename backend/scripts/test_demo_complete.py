"""
End-to-end Comprehensive Verification Test Suite for the Real Estate AI Chatbot CTO/Client Demo.
Tests:
1. 1BHK, 2BHK, 3BHK, 4BHK document specifications
2. Multi-document retrieval across unstructured PDFs
3. Property search with Athena / demo catalog
4. Search refinement handling
5. Contextual image retrieval
6. General conversational responses
"""

import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.rag.retriever import hybrid_search
from backend.app.rag.service import answer_question
from backend.app.schemas import ChatRequest, ChatMessage
from backend.app.main import chat

def run_tests():
    print("=" * 70)
    print("ESTATEAI CTO/CLIENT DEMO COMPREHENSIVE VERIFICATION SUITE")
    print("=" * 70)

    # 1. Multi-Document Knowledge Base Retrieval Tests
    test_queries = [
        ("1BHK Specs", "What are the 1BHK super built-up area and dimensions?", "Casagrand_Aquagrove_1BHK_Studio_Specifications.pdf"),
        ("2BHK Specs", "What are the 2BHK bedroom and living dimensions?", "2BHK"),
        ("3BHK Specs", "What are the 3BHK specifications and room sizes?", "3BHK"),
        ("4BHK Penthouse", "What are the 4BHK penthouse dimensions and terrace deck?", "Casagrand_Aquagrove_4BHK_Penthouse_Luxury_Specifications.pdf"),
        ("Villa Living", "What are the villa garden area and car port specs?", "Casagrand_Aquagrove_Villa_Independent_Living_Guide.pdf"),
        ("Structural", "What is the seismic zone compliance and concrete grade?", "Structural_Design_and_Civil_Specifications_Handbook.pdf"),
        ("Doors & Windows", "What type of digital lock and glass are used for doors and windows?", "Doors_Windows_and_Hardware_Schedule.pdf"),
        ("Flooring & Finishes", "What vitrified tile size and paint brands are specified?", "Flooring_Wall_Finishes_and_Painting_Schedule.pdf"),
        ("Electrical & Plumbing", "What brand of modular switches and CP fittings are installed?", "Electrical_Plumbing_and_HVAC_Schedule.pdf"),
        ("Clubhouse & Sports", "What is the swimming pool size and badminton courts in the clubhouse?", "Clubhouse_Sports_and_Recreation_Amenities_Directory.pdf"),
        ("Security & Smart Home", "What CCTV and visitor management app are used?", "Security_Access_Control_and_Smart_Home_Guidelines.pdf"),
        ("Parking & EV Rules", "What are the parking allocation and EV charging socket specs?", "Parking_Allocation_EV_Charging_and_Traffic_Rules.pdf"),
        ("Water & Environment", "What STP technology and rainwater harvesting pits are installed?", "Water_Management_STP_and_Rainwater_Harvesting_Policy.pdf"),
        ("Payment & Handover", "What is the construction linked payment schedule?", "Payment_Schedules_Possession_Timelines_and_Handover_Policy.pdf"),
        ("Renovation Guidelines", "What are the permitted interior work hours and noise rules?", "Home_Renovation_Interior_Work_and_Architectural_Guidelines.pdf"),
        ("Pet Policy", "What are the pet rules, leash requirements and agility park?", "Pet_Policy_and_Common_Area_Etiquette.pdf"),
    ]

    print("\n--- 1. Testing Multi-Document Hybrid RRF Retrieval ---")
    retrieval_passed = 0
    for label, query, expected_sub in test_queries:
        hits = hybrid_search(query, top_k=2)
        top_source = hits[0]["source"] if hits else "NONE"
        matched = expected_sub.lower() in top_source.lower()
        if not matched and len(hits) > 1:
            matched = expected_sub.lower() in hits[1]["source"].lower()
        status = "PASS" if matched else "WARN"
        if matched:
            retrieval_passed += 1
        print(f"[{status}] {label:22s} -> Source: {top_source}")

    print(f"\nRetrieval Score: {retrieval_passed}/{len(test_queries)} passed")

    # 2. Testing Chat Endpoint Intent Routing & Property Card Generation
    print("\n--- 2. Testing Chat Dispatcher & Property Card Generation ---")
    chat_tests = [
        ("What are the 2BHK specifications?", "document_qa", True),
        ("What are the 3BHK specifications?", "document_qa", True),
        ("What are the 4BHK specifications?", "document_qa", True),
        ("What are the permitted interior renovation hours?", "document_qa", False),
        ("Show me bedroom images", "media_request", False),
        ("3 BHK under 1.8 crore near OMR, east facing", "property_search", True),
        ("Can you show cheaper ones?", "search_refinement", True),
        ("Hello, who are you?", "general_question", False),
    ]

    endpoint_passed = 0
    for msg, expected_intent, expect_cards in chat_tests:
        req = ChatRequest(message=msg, history=[], provider="gemini")
        try:
            resp = chat(req)
            intent = resp.get("filters", {}).get("intent")
            has_cards = len(resp.get("properties", [])) > 0
            has_images = len(resp.get("images", [])) > 0

            intent_ok = (intent == expected_intent) or (expected_intent == "property_search" and intent in ("property_search", "search_refinement"))
            cards_ok = (has_cards == expect_cards) or (expected_intent == "media_request" and has_images)
            ok = intent_ok and cards_ok

            status = "PASS" if ok else f"FAIL (intent={intent}, cards={has_cards})"
            if ok:
                endpoint_passed += 1
            print(f"[{status:4s}] Msg: \"{msg[:35]:35s}\" -> Intent: {intent}, Cards: {len(resp.get('properties', []))}, Images: {len(resp.get('images', []))}")
        except Exception as e:
            print(f"[FAIL] Msg: \"{msg}\" -> Error: {e}")

    print(f"\nEndpoint Score: {endpoint_passed}/{len(chat_tests)} passed")

    # 3. Verify Backup Directory Exists
    backup_path = PROJECT_ROOT / "frontend" / "src_backup_dashboard"
    backup_exists = backup_path.exists() and (backup_path / "App.jsx").exists()
    print(f"\n--- 3. Backup Status ---")
    print(f"UI Backup Directory: {backup_path} -> {'EXISTS (Verified)' if backup_exists else 'MISSING'}")

    print("\n" + "=" * 70)
    print("ALL VERIFICATIONS COMPLETE")
    print("=" * 70)

if __name__ == "__main__":
    run_tests()

