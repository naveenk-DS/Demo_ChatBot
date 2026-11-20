"""
Comprehensive test script for SearchFilters validation and ChatRequest processing.
Tests empty strings, nulls, omissions, valid numeric parsing, strict invalid rejection,
and ChatRequest execution with Ollama.
"""

from pathlib import Path
import sys

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from pydantic import ValidationError
from app.schemas import SearchFilters, ChatRequest
from app.main import chat


def test_search_filters():
    print("=" * 80)
    print("SEARCH FILTERS VALIDATION TEST SUITE")
    print("=" * 80)

    # 1. Test: No BHK selected (empty string, None, omitted)
    print("\n[TEST 1] No BHK selected...")
    f1_empty = SearchFilters.model_validate({"bhk": "", "city": "Bangalore"})
    f1_null = SearchFilters.model_validate({"bhk": None, "city": "Bangalore"})
    f1_omitted = SearchFilters.model_validate({"city": "Bangalore"})
    assert f1_empty.bhk is None, f"Expected None, got {f1_empty.bhk}"
    assert f1_null.bhk is None, f"Expected None, got {f1_null.bhk}"
    assert f1_omitted.bhk is None, f"Expected None, got {f1_omitted.bhk}"
    print(f"  Empty string bhk -> {f1_empty.bhk}")
    print(f"  Null bhk -> {f1_null.bhk}")
    print(f"  Omitted bhk -> {f1_omitted.bhk}")
    print("  [PASS] No BHK selected handled correctly.")

    # 2. Test: No minimum price (empty string, None, omitted)
    print("\n[TEST 2] No minimum price...")
    f2_empty = SearchFilters.model_validate({"min_price": "", "bhk": 2})
    f2_null = SearchFilters.model_validate({"min_price": None, "bhk": 2})
    f2_omitted = SearchFilters.model_validate({"bhk": 2})
    assert f2_empty.min_price is None, f"Expected None, got {f2_empty.min_price}"
    assert f2_null.min_price is None, f"Expected None, got {f2_null.min_price}"
    assert f2_omitted.min_price is None, f"Expected None, got {f2_omitted.min_price}"
    print(f"  Empty string min_price -> {f2_empty.min_price}")
    print(f"  Null min_price -> {f2_null.min_price}")
    print(f"  Omitted min_price -> {f2_omitted.min_price}")
    print("  [PASS] No minimum price handled correctly.")

    # 3. Test: No maximum price (empty string, None, omitted)
    print("\n[TEST 3] No maximum price...")
    f3_empty = SearchFilters.model_validate({"max_price": "", "bhk": 2})
    f3_null = SearchFilters.model_validate({"max_price": None, "bhk": 2})
    f3_omitted = SearchFilters.model_validate({"bhk": 2})
    assert f3_empty.max_price is None, f"Expected None, got {f3_empty.max_price}"
    assert f3_null.max_price is None, f"Expected None, got {f3_null.max_price}"
    assert f3_omitted.max_price is None, f"Expected None, got {f3_omitted.max_price}"
    print(f"  Empty string max_price -> {f3_empty.max_price}")
    print(f"  Null max_price -> {f3_null.max_price}")
    print(f"  Omitted max_price -> {f3_omitted.max_price}")
    print("  [PASS] No maximum price handled correctly.")

    # 4. Test: All filters empty / unspecified sentinels
    print("\n[TEST 4] All filters empty or unspecified...")
    f4 = SearchFilters.model_validate({
        "intent": "property_search",
        "location": "",
        "city": "",
        "bhk": "",
        "min_price": "",
        "max_price": "",
        "property_type": "",
    })
    assert f4.bhk is None
    assert f4.min_price is None
    assert f4.max_price is None
    assert f4.location is None
    assert f4.city is None
    assert f4.property_type is None
    print(f"  All filters empty -> {f4.model_dump()}")

    f4_sentinels = SearchFilters.model_validate({
        "bhk": "not specified",
        "min_price": "not specified",
        "max_price": "not specified",
        "location": "n/a",
        "city": "none",
    })
    assert f4_sentinels.bhk is None
    assert f4_sentinels.min_price is None
    assert f4_sentinels.max_price is None
    assert f4_sentinels.location is None
    assert f4_sentinels.city is None
    print(f"  All filters 'not specified' / 'n/a' -> {f4_sentinels.model_dump()}")
    print("  [PASS] All empty & 'not specified' filters cleanly converted to None.")

    # 5. Test: Valid BHK and price filters (integers and string integers)
    print("\n[TEST 5] Valid BHK and price filters...")
    f5_ints = SearchFilters.model_validate({
        "bhk": 3,
        "min_price": 5000000,
        "max_price": 10000000,
        "city": "Bangalore"
    })
    f5_strs = SearchFilters.model_validate({
        "bhk": "3",
        "min_price": "5000000",
        "max_price": "10000000",
        "city": "Bangalore"
    })
    assert f5_ints.bhk == 3 and isinstance(f5_ints.bhk, int)
    assert f5_ints.min_price == 5000000 and isinstance(f5_ints.min_price, int)
    assert f5_ints.max_price == 10000000 and isinstance(f5_ints.max_price, int)
    assert f5_strs.bhk == 3 and isinstance(f5_strs.bhk, int)
    assert f5_strs.min_price == 5000000 and isinstance(f5_strs.min_price, int)
    assert f5_strs.max_price == 10000000 and isinstance(f5_strs.max_price, int)
    print(f"  Parsed integer inputs: bhk={f5_ints.bhk}, min={f5_ints.min_price}, max={f5_ints.max_price}")
    print(f"  Parsed string inputs:  bhk={f5_strs.bhk}, min={f5_strs.min_price}, max={f5_strs.max_price}")
    print("  [PASS] Valid numeric inputs parsed correctly.")

    # 6. Test: Strict rejection of genuinely invalid inputs
    print("\n[TEST 6] Strict validation for genuinely invalid inputs...")
    invalid_cases = [
        ({"bhk": "invalid"}, "bhk invalid string"),
        ({"bhk": 0}, "bhk = 0 (below ge=1)"),
        ({"bhk": 15}, "bhk = 15 (above le=10)"),
        ({"min_price": -500}, "min_price negative"),
        ({"min_price": "not_a_number"}, "min_price string non-numeric"),
        ({"max_price": -100}, "max_price negative"),
        ({"min_price": 10000000, "max_price": 5000000}, "min_price > max_price"),
    ]
    for payload, desc in invalid_cases:
        try:
            SearchFilters.model_validate(payload)
            print(f"  FAILED: {desc} should have raised ValidationError!")
            sys.exit(1)
        except (ValidationError, ValueError) as err:
            print(f"  Strict validation caught {desc}: {type(err).__name__}")
    print("  [PASS] Strict validation preserved for invalid inputs.")

    # 7. Test: Chat request with Ollama selected and no search filters
    print("\n[TEST 7] Chat request with Ollama selected and no search filters...")
    req_no_filters = ChatRequest(
        message="Show me 2 BHK apartments in Bangalore below 80 lakhs",
        history=[],
        provider="ollama"
    )
    assert req_no_filters.filters is None
    print(f"  ChatRequest created: provider={req_no_filters.provider}, filters={req_no_filters.filters}")

    # Also test ChatRequest with empty filters dictionary
    req_empty_filters = ChatRequest(
        message="What is the living room size in 2BHK?",
        history=[],
        provider="ollama",
        filters={"bhk": "", "min_price": "", "max_price": ""}
    )
    assert req_empty_filters.filters.bhk is None
    assert req_empty_filters.filters.min_price is None
    assert req_empty_filters.filters.max_price is None
    print(f"  ChatRequest with empty filter dict parsed cleanly: bhk={req_empty_filters.filters.bhk}")

    # Execute chat request using Ollama
    from fastapi import HTTPException
    try:
        resp = chat(req_empty_filters)
        print(f"  Chat response status: {resp.get('status')}")
        print(f"  Chat response message: \"{resp.get('assistant_message')}\"")
        assert resp.get("status") == "message"
        assert resp.get("assistant_message") != ""
        print("  [PASS] Chat request with Ollama executed successfully without filter validation errors.")
    except HTTPException as he:
        # Check that it did NOT fail with SearchFilters validation error
        assert "SearchFilters" not in str(he.detail)
        assert "unable to parse string as an integer" not in str(he.detail)
        print(f"  Chat endpoint correctly handled request (server response: {he.detail}). Zero SearchFilters validation errors!")
        print("  [PASS] Chat request with Ollama passed SearchFilters validation cleanly.")

    print("\n" + "=" * 80)
    print("ALL SEARCH FILTERS VALIDATION TESTS PASSED!")
    print("================================================================================")


if __name__ == "__main__":
    test_search_filters()
