"""
Test property card information, location diversity across Chennai,
and query-specific extracted document specifications.
"""
import sys
from pathlib import Path

# Ensure project root is in sys.path
root_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(root_dir))

from backend.app.main import app, _rag_to_details, extract_chennai_location, _fetch_properties_for_bhk
from backend.app.schemas import ChatRequest
from fastapi.testclient import TestClient

client = TestClient(app)

def test_rag_topic_filtering():
    sample_rag_answer = """
    Here are the specifications:
    * Master Bedroom: 14' x 16' with laminated wooden flooring and walk-in wardrobe
    * Bedroom 2: 12' x 14' with vitrified tile flooring
    * Kitchen: Black granite platform with stainless steel sink and exhaust provision
    * Utility: Anti-skid ceramic tiles with washing machine point
    * Bathrooms: Kohler wall-hung EWC, Jaguar CP fittings, and 25L geyser provision
    * Clubhouse: 25,000 sq ft clubhouse with swimming pool, gym, and squash court
    * Electrical: Concealed copper wiring with Schneider modular switches
    """
    
    # 1. Test bedroom filter
    bedroom_details = _rag_to_details(sample_rag_answer, query="show bedroom specifications")
    print("\n--- Bedroom query details ---")
    for d in bedroom_details:
        print(" -", d)
    assert any("Bedroom" in d or "wardrobe" in d for d in bedroom_details), "Bedroom details should be prioritized"
    assert not any("Kitchen" in d for d in bedroom_details), "Kitchen should not be in bedroom details"
    
    # 2. Test kitchen filter
    kitchen_details = _rag_to_details(sample_rag_answer, query="what are the kitchen specifications?")
    print("\n--- Kitchen query details ---")
    for d in kitchen_details:
        print(" -", d)
    assert any("Kitchen" in d or "Utility" in d or "granite" in d for d in kitchen_details), "Kitchen details should be prioritized"
    assert not any("Bedroom" in d for d in kitchen_details), "Bedroom should not be in kitchen details"
    
    # 3. Test amenities filter
    amenity_details = _rag_to_details(sample_rag_answer, query="tell me about clubhouse and amenities")
    print("\n--- Amenity query details ---")
    for d in amenity_details:
        print(" -", d)
    assert any("Clubhouse" in d or "swimming" in d for d in amenity_details), "Clubhouse/amenities details should be prioritized"

def test_chennai_location_coverage():
    print("\n--- Chennai location coverage test ---")
    locations = ["Anna Nagar", "Velachery", "Porur", "Guindy", "Sholinganallur", "Kelambakkam"]
    for loc in locations:
        extracted = extract_chennai_location(f"Show 3 BHK in {loc}")
        assert extracted is not None, f"Should recognize {loc}"
        props = _fetch_properties_for_bhk(3, limit=1, location=extracted)
        assert len(props) > 0, f"Should return properties for {loc}"
        p = props[0]
        print(f"[{loc}] -> {p['property_name']} | Location: {p['location']}, {p['city']} | Price: ₹{p['price'] / 10000000:.2f} Cr")
        assert loc.lower() in p["location"].lower() or loc.lower() in p.get("description", "").lower(), f"Should match {loc}"

def test_api_chat_flow():
    print("\n--- API /api/chat document specifications test ---")
    # Ask about 3BHK bedroom details
    resp = client.post("/api/chat", json={
        "message": "What are the 3BHK bedroom specifications and dimensions?",
        "provider": "gemini",
        "history": []
    })
    assert resp.status_code == 200, f"Chat status {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["status"] == "success"
    assert len(data.get("properties", [])) > 0
    prop = data["properties"][0]
    print(f"API Returned Property: {prop['property_name']}")
    print(f"Price: {prop.get('price')} (actual numeric price, not invented)")
    print(f"Location: {prop.get('location')}")
    print(f"Details count: {len(prop.get('details', []))}")
    for d in prop.get("details", [])[:5]:
        print("   *", d)
    
    # Verify no 'live_price' or timestamp in response
    assert "live_price" not in prop
    assert "Live price" not in str(data)

if __name__ == "__main__":
    test_rag_topic_filtering()
    test_chennai_location_coverage()
    test_api_chat_flow()
    print("\nALL BACKEND TESTS PASSED SUCCESSFULLY!")

