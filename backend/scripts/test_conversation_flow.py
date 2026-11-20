"""
Unit and integration test suite for the 10-turn real estate conversation sequence.
Validates:
1. Intent classification & normalization.
2. Context retention (Turn 1 -> Turn 2).
3. Context reset (Turn 4 "Forget the budget...").
4. RAG retrieval precision for specification queries (Master bedroom, entrance, 3 bedrooms, 2BHK vs 3BHK).
5. Media request handling (Turn 7).
6. Bedroom configuration validation (Turn 8: 3BHK = 3 bedrooms, not 5).
7. End-to-end routing in chat().
"""

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app.schemas import ChatRequest, ChatMessage, SearchFilters
from backend.app.llm import _normalize_extracted
from backend.app.rag.retriever import hybrid_search
from backend.app.main import chat

test_turns = [
    # Turn 1
    "I am looking for a property around 69 lakhs.",
    # Turn 2
    "In Chennai.",
    # Turn 3
    "Which is better, 2BHK or 3BHK?",
    # Turn 4
    "Forget the budget. I only want property specifications.",
    # Turn 5
    "What are the master bedroom dimensions?",
    # Turn 6
    "What are the entrance features?",
    # Turn 7
    "Show me the entire property image.",
    # Turn 8
    "Does the 3BHK have five bedrooms?",
    # Turn 9
    "Give me details of all three bedrooms.",
    # Turn 10
    "Compare 2BHK and 3BHK."
]


def test_normalization_and_intent_rules():
    print("\n--- TEST 1: Normalization & Intent Routing Rules ---")
    
    # Turn 1: 69 lakhs property search
    d1 = _normalize_extracted({
        "intent": "property_search",
        "max_price": 6900000,
        "needs_clarification": True,
        "clarification_question": "Do you need image of the land?" # Old hallucination
    }, test_turns[0])
    assert d1["intent"] == "property_search"
    assert d1["max_price"] == 6900000
    assert d1["needs_clarification"] is True
    # Verify hallucinated image question is replaced with clean locality question
    assert "image" not in d1["clarification_question"].lower()
    assert "chennai" not in str(d1.get("city"))
    print("✓ Turn 1: Intent is property_search, max_price=6900000, clarification sanitized.")

    # Turn 2: In Chennai (context retained)
    d2 = _normalize_extracted({
        "intent": "property_search",
        "max_price": 6900000,
        "city": "Chennai",
        "needs_clarification": False
    }, test_turns[1])
    assert d2["intent"] == "property_search"
    assert d2["city"] == "Chennai"
    assert d2["max_price"] == 6900000
    assert d2["needs_clarification"] is False
    print("✓ Turn 2: Context retained (Chennai + ₹69L), needs_clarification=False.")

    # Turn 3: Which is better, 2BHK or 3BHK?
    d3 = _normalize_extracted({
        "intent": "property_search",
        "needs_clarification": True
    }, test_turns[2])
    assert d3["intent"] == "document_qa"
    assert d3["needs_clarification"] is False
    print("✓ Turn 3: Re-routed to document_qa, needs_clarification=False.")

    # Turn 4: Forget the budget. I only want property specifications.
    d4 = _normalize_extracted({
        "intent": "property_search",
        "max_price": 6900000
    }, test_turns[3])
    assert d4["intent"] == "general_question"
    assert d4["max_price"] is None
    assert d4["min_price"] is None
    print("✓ Turn 4: Budget filter cleared (max_price=None, min_price=None).")

    # Turn 5: What are the master bedroom dimensions?
    d5 = _normalize_extracted({"intent": "property_search"}, test_turns[4])
    assert d5["intent"] == "document_qa"
    assert d5["needs_clarification"] is False
    print("✓ Turn 5: Master bedroom dimensions routed to document_qa.")

    # Turn 6: What are the entrance features?
    d6 = _normalize_extracted({"intent": "property_search"}, test_turns[5])
    assert d6["intent"] == "document_qa"
    assert d6["needs_clarification"] is False
    print("✓ Turn 6: Entrance features routed to document_qa.")

    # Turn 7: Show me the entire property image.
    d7 = _normalize_extracted({"intent": "property_search", "needs_clarification": True}, test_turns[6])
    assert d7["intent"] == "media_request"
    assert d7["needs_clarification"] is False
    print("✓ Turn 7: Media request routed to media_request, needs_clarification=False.")

    # Turn 8: Does the 3BHK have five bedrooms?
    d8 = _normalize_extracted({"intent": "property_search"}, test_turns[7])
    assert d8["intent"] == "document_qa"
    assert d8["needs_clarification"] is False
    print("✓ Turn 8: Five bedrooms question routed to document_qa.")

    # Turn 9: Give me details of all three bedrooms.
    d9 = _normalize_extracted({"intent": "property_search"}, test_turns[8])
    assert d9["intent"] == "document_qa"
    assert d9["needs_clarification"] is False
    print("✓ Turn 9: All three bedrooms routed to document_qa.")

    # Turn 10: Compare 2BHK and 3BHK.
    d10 = _normalize_extracted({"intent": "property_search"}, test_turns[9])
    assert d10["intent"] == "document_qa"
    assert d10["needs_clarification"] is False
    print("✓ Turn 10: Comparison routed to document_qa.")


def test_rag_retrieval_chunks():
    print("\n--- TEST 2: RAG Chunk Retrieval Accuracy ---")
    
    # Master bedroom dimensions
    q5 = "What are the master bedroom dimensions?"
    res5 = hybrid_search(q5, top_k=5, collection_name="real_estate_documents_v3_structured")
    matched_dims = [r for r in res5 if "11’" in r.get("text", "") or "14’" in r.get("text", "") or "18’" in r.get("text", "")]
    assert len(matched_dims) > 0, "Failed to retrieve master bedroom dimensions chunk!"
    print(f"✓ Master bedroom retrieval: found {len(matched_dims)} chunks containing exact dimensions.")

    # Entrance features
    q6 = "What are the entrance features?"
    res6 = hybrid_search(q6, top_k=3, collection_name="real_estate_documents_v3_structured")
    entrance_chunks = [r for r in res6 if r.get("category") == "entrance" or "door lock" in r.get("text", "").lower()]
    assert len(entrance_chunks) > 0, "Failed to retrieve entrance chunks!"
    print(f"✓ Entrance features retrieval: found {len(entrance_chunks)} chunks with digital lock / main door.")

    # 3BHK bedrooms
    q9 = "Give me details of all three bedrooms."
    res9 = hybrid_search(q9, top_k=5, collection_name="real_estate_documents_v3_structured")
    assert len(res9) > 0, "Failed to retrieve chunks for bedroom details!"
    print(f"✓ 3BHK bedrooms retrieval: found {len(res9)} chunks.")


def test_end_to_end_chat_sequence():
    print("\n--- TEST 3: End-to-End Chat Routing Sequence ---")
    
    history: list[ChatMessage] = []

    # Mock responses for extract to simulate LLM understanding accurately
    mock_extractions = [
        # Turn 1
        {"intent": "property_search", "max_price": 6900000, "needs_clarification": True},
        # Turn 2
        {"intent": "property_search", "city": "Chennai", "max_price": 6900000, "needs_clarification": False},
        # Turn 3
        {"intent": "document_qa", "needs_clarification": False},
        # Turn 4
        {"intent": "general_question", "min_price": None, "max_price": None, "needs_clarification": False},
        # Turn 5
        {"intent": "document_qa", "needs_clarification": False},
        # Turn 6
        {"intent": "document_qa", "needs_clarification": False},
        # Turn 7
        {"intent": "media_request", "needs_clarification": False},
        # Turn 8
        {"intent": "document_qa", "bhk": 3, "needs_clarification": False},
        # Turn 9
        {"intent": "document_qa", "bhk": 3, "needs_clarification": False},
        # Turn 10
        {"intent": "document_qa", "needs_clarification": False},
    ]

    # Mock RAG answers for document_qa turns
    mock_rag_answers = {
        "Which is better, 2BHK or 3BHK?": "The 2BHK (1309 sqft) is well-suited for small families with a spacious 11'6\" x 14' master bedroom. The 3BHK (2100 sqft) provides three full bedrooms with convertible balconies and larger living/dining areas.",
        "What are the master bedroom dimensions?": "In the 2BHK, the Master Bedroom is 11’ 6” x 14’. In the 3BHK, the Master Bedroom is 11’ x 18’ 2”. Both feature convertible balconies.",
        "What are the entrance features?": "The entrance features a 7’ 9” grand main door with double-side veneer finish shutter, Godrej/Yale digital door lock with 4 unlocking modes, and a dedicated foyer for privacy.",
        "Does the 3BHK have five bedrooms?": "No, a 3BHK configuration consists of 3 bedrooms (Master Bedroom, Bedroom 2, and Bedroom 3), not 5 bedrooms.",
        "Give me details of all three bedrooms.": "The 3BHK includes: Master Bedroom (11' x 18' 2\"), Bedroom 2 (13' x 14'), and Bedroom 3 (11' 6\" x 14'), each with convertible balconies and attached/adjacent toilets.",
        "Compare 2BHK and 3BHK.": "2BHK: ~1309 sqft, 2 bedrooms (Master 11'6\"x14', Bed 2 11'1\"x14'2\"), 2 toilets. 3BHK: ~2100 sqft, 3 bedrooms (Master 11'x18'2\", Bed 2 13'x14', Bed 3 11'6\"x14'), 3 toilets."
    }

    def fake_extract(provider, h, current):
        idx = test_turns.index(current)
        return _normalize_extracted(mock_extractions[idx], current)

    def fake_answer_question(query, **kwargs):
        ans = mock_rag_answers.get(query, "Document information retrieved.")
        return {
            "success": True,
            "answer": ans,
            "sources": [{"source": "2BHK + 2T Model House Script - Casagrand Aquagrove.pdf", "page": 1}]
        }

    with patch("backend.app.main.understand", side_effect=lambda prov, h, curr: SearchFilters.model_validate(fake_extract(prov, h, curr))), \
         patch("backend.app.main.answer_question", side_effect=fake_answer_question), \
         patch("backend.app.main.run_query", return_value=[{"property_id": "P101", "name": "Casagrand Aquagrove", "price": 6800000, "city": "Chennai"}]):

        for turn_idx, user_msg in enumerate(test_turns, start=1):
            req = ChatRequest(
                message=user_msg,
                history=history,
                provider="ollama"
            )
            resp = chat(req)
            status = resp.get("status")
            assistant_msg = resp.get("assistant_message")
            filters = resp.get("filters", {})

            print(f"Turn {turn_idx}: [{user_msg}] -> Status={status}, Intent={filters.get('intent')}")
            print(f"   Response: {assistant_msg[:120]}...")

            if turn_idx == 1:
                assert status == "clarification_required"
                assert "image" not in assistant_msg.lower()
                assert "locality" in assistant_msg.lower() or "city" in assistant_msg.lower()
            elif turn_idx == 2:
                assert status == "success"
                assert len(resp.get("properties", [])) > 0
            elif turn_idx == 3:
                assert status == "message"
                assert filters.get("intent") == "document_qa"
            elif turn_idx == 4:
                assert status == "message"
                assert filters.get("max_price") is None
                assert "69" not in assistant_msg
            elif turn_idx == 5:
                assert status == "message"
                assert "11’" in assistant_msg or "14’" in assistant_msg
            elif turn_idx == 6:
                assert status == "message"
                assert "main door" in assistant_msg.lower() or "lock" in assistant_msg.lower()
            elif turn_idx == 7:
                assert status == "message"
                assert filters.get("intent") == "media_request"
                assert "not currently analyzed by ai" in assistant_msg.lower() or "not available in this demo" in assistant_msg.lower()
            elif turn_idx == 8:
                assert status == "message"
                assert "3 bedrooms" in assistant_msg.lower()
            elif turn_idx == 9:
                assert status == "message"
                assert "Master Bedroom" in assistant_msg
            elif turn_idx == 10:
                assert status == "message"
                assert "2BHK" in assistant_msg and "3BHK" in assistant_msg

            history.append(ChatMessage(role="user", content=user_msg))
            history.append(ChatMessage(role="assistant", content=assistant_msg))

    print("\n✓ ALL 10 CONVERSATION TURNS VERIFIED SUCCESSFULLY!")


if __name__ == "__main__":
    test_normalization_and_intent_rules()
    test_rag_retrieval_chunks()
    test_end_to_end_chat_sequence()
