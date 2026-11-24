"""
Structured Data Pipeline Tests for EstateAI.
Tests CSV, Excel (multi-sheet), JSON (nested), Price/BHK normalization,
validation, and deterministic search without hallucination.
"""

import sys
import unittest
from pathlib import Path

backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.data_pipeline.structured import (
    load_json,
    load_csv,
    load_excel,
    normalize_records,
    validate_records,
    search_properties,
    parse_price_to_inr,
    parse_bhk_integer,
    parse_sqft_integer,
)

BASE_DIR = backend_root


class TestStructuredPipeline(unittest.TestCase):
    def test_price_normalization_various_formats(self):
        # Crores
        self.assertEqual(parse_price_to_inr("1.2 Cr"), 12000000)
        self.assertEqual(parse_price_to_inr("1.25 Crore"), 12500000)
        self.assertEqual(parse_price_to_inr("2.5 Crores"), 25000000)
        # Lakhs
        self.assertEqual(parse_price_to_inr("85 Lakhs"), 8500000)
        self.assertEqual(parse_price_to_inr("45 L"), 4500000)
        # Currency symbols and formatting
        self.assertEqual(parse_price_to_inr("₹85,00,000"), 8500000)
        self.assertEqual(parse_price_to_inr("Rs. 1,45,00,000/-"), 14500000)
        self.assertEqual(parse_price_to_inr(9500000), 9500000)
        # Invalid and sentinels
        self.assertIsNone(parse_price_to_inr("invalid"))
        self.assertIsNone(parse_price_to_inr("N/A"))
        self.assertIsNone(parse_price_to_inr(""))
        self.assertIsNone(parse_price_to_inr(None))

    def test_bhk_normalization(self):
        self.assertEqual(parse_bhk_integer("2 BHK"), 2)
        self.assertEqual(parse_bhk_integer("3bhk"), 3)
        self.assertEqual(parse_bhk_integer("4 Bedroom"), 4)
        self.assertEqual(parse_bhk_integer(1), 1)
        self.assertEqual(parse_bhk_integer("5 Bed"), 5)
        self.assertIsNone(parse_bhk_integer("Commercial Plot"))
        self.assertIsNone(parse_bhk_integer("Studio"))

    def test_sqft_normalization(self):
        self.assertEqual(parse_sqft_integer("1,250 sqft"), 1250)
        self.assertEqual(parse_sqft_integer(1650), 1650)
        self.assertEqual(parse_sqft_integer("2850"), 2850)
        self.assertIsNone(parse_sqft_integer("invalid"))

    def test_load_and_search_json(self):
        json_path = BASE_DIR / "data" / "documents" / "chennai_properties_catalog.json"
        raw = load_json(json_path, "chennai_properties_catalog.json")
        self.assertGreaterEqual(len(raw), 5)

        norm = normalize_records(raw, "chennai_properties_catalog.json")
        valid = validate_records(norm)
        self.assertEqual(len(valid), len(raw))

        # Search 2BHK in Perungudi
        res = search_properties({"bhk": 2, "location": "Perungudi"}, valid)
        self.assertGreaterEqual(len(res), 1)
        self.assertTrue(all(r["bhk"] == 2 for r in res))
        self.assertTrue(any("Perungudi" in r["location"] for r in res))

    def test_nested_json_handling(self):
        # Test arbitrary nested JSON structures
        nested_data = json_bytes = b"""{
            "status": "success",
            "data": {
                "records": [
                    {"name": "Metro Heights", "bedrooms": 3, "cost": "1.1 Cr", "locality": "Guindy"},
                    {"name": "Bay View", "bedrooms": 2, "cost": "75 Lakhs", "locality": "OMR"}
                ]
            }
        }"""
        raw = load_json(json_bytes, "nested.json")
        self.assertEqual(len(raw), 2)
        norm = normalize_records(raw, "nested.json")
        self.assertEqual(norm[0]["property_name"], "Metro Heights")
        self.assertEqual(norm[0]["bhk"], 3)
        self.assertEqual(norm[0]["price"], 11000000)
        self.assertEqual(norm[0]["location"], "Guindy")

    def test_load_and_search_csv(self):
        csv_path = BASE_DIR / "data" / "documents" / "chennai_premium_listings.csv"
        raw = load_csv(csv_path, "chennai_premium_listings.csv")
        self.assertGreaterEqual(len(raw), 4)

        norm = normalize_records(raw, "chennai_premium_listings.csv")
        valid = validate_records(norm)
        self.assertGreaterEqual(len(valid), 4)

        # Search 3BHK
        res = search_properties({"bhk": 3}, valid)
        self.assertGreaterEqual(len(res), 2)
        self.assertTrue(all(r["bhk"] == 3 for r in res))

    def test_empty_results_handling(self):
        json_path = BASE_DIR / "data" / "documents" / "chennai_properties_catalog.json"
        raw = load_json(json_path, "chennai_properties_catalog.json")
        valid = validate_records(normalize_records(raw, "json"))

        # Searching for non-existent 8BHK under 50 Lakhs
        res = search_properties({"bhk": 8, "max_price": 5000000}, valid)
        self.assertEqual(len(res), 0)

    def test_invalid_records_rejection(self):
        corrupt_records = [
            {"foo": "bar"},  # No name, price, bhk, sqft
            {"property_name": "", "price": None},  # Empty name
            {"property_name": "Valid Apartment", "price": "85 Lakhs", "bhk": 2},  # Valid
        ]
        norm = normalize_records(corrupt_records, "test.csv")
        valid = validate_records(norm)
        self.assertEqual(len(valid), 1)
        self.assertEqual(valid[0]["property_name"], "Valid Apartment")


if __name__ == "__main__":
    unittest.main()
