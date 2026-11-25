"""
Chat & API Endpoints Tests for EstateAI.
Verifies all FastAPI endpoint handlers:
- health()
- get_providers()
- chat() [Greetings, 2BHK search, Price bounded search, Media requests]
- enquiry()
- list_documents()
- get_images()
"""

import os
import sys
import unittest
from pathlib import Path

backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

import app.main
from app.main import (
    health,
    get_providers,
    get_images,
    list_documents,
    chat,
    enquiry,
    load_all_structured_data,
)
from app.schemas import ChatRequest, EnquiryRequest


class TestChatEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Isolate test suite from local production environment
        cls._orig_env = {
            "ALLOW_LOCAL_FALLBACK": os.environ.get("ALLOW_LOCAL_FALLBACK"),
            "APP_ENV": os.environ.get("APP_ENV"),
            "S3_BUCKET_NAME": os.environ.get("S3_BUCKET_NAME"),
        }
        os.environ["ALLOW_LOCAL_FALLBACK"] = "true"
        os.environ["APP_ENV"] = "test"
        os.environ["S3_BUCKET_NAME"] = ""
        # Initialize verified properties catalog
        app.main.VERIFIED_PROPERTIES = load_all_structured_data()

    @classmethod
    def tearDownClass(cls):
        for k, v in cls._orig_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_health_endpoint(self):
        data = health()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["service"], "estateai-concierge-backend")
        self.assertIn("aws", data)
        self.assertIn("flags", data)
        self.assertFalse(data["flags"]["enable_athena"])
        self.assertFalse(data["flags"]["enable_glue"])
        self.assertGreater(data["properties_loaded"], 0)

    def test_providers_endpoint(self):
        data = get_providers()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["active_provider"], "bedrock")
        self.assertIn("bedrock", data["providers"])

    def test_chat_greeting_workflow(self):
        req = ChatRequest(message="Hello, good morning!", history=[], provider="bedrock")
        data = chat(req)
        self.assertEqual(data["status"], "success")
        self.assertTrue(len(data["assistant_message"]) > 10)
        self.assertEqual(data["properties"], [])
        self.assertEqual(data["filters"]["intent"], "general_question")

    def test_chat_property_search_2bhk(self):
        req = ChatRequest(message="Show me 2BHK properties in Chennai", history=[], provider="bedrock")
        data = chat(req)
        self.assertEqual(data["status"], "success")
        self.assertTrue(len(data["assistant_message"]) > 10)
        
        properties = data["properties"]
        self.assertGreaterEqual(len(properties), 1)
        first = properties[0]
        self.assertIn("property_name", first)
        self.assertIn("price", first)
        self.assertIn("bhk", first)
        self.assertEqual(first["bhk"], 2)
        self.assertIn("location", first)
        self.assertIn("details", first)

    def test_chat_property_search_under_budget(self):
        req = ChatRequest(message="Show me 2BHK properties under 1 Crore in Chennai", history=[], provider="bedrock")
        data = chat(req)
        self.assertEqual(data["status"], "success")
        
        properties = data["properties"]
        self.assertGreaterEqual(len(properties), 1)
        for p in properties:
            self.assertEqual(p["bhk"], 2)
            self.assertLessEqual(p["price"], 10000000)

    def test_chat_media_request(self):
        req = ChatRequest(message="Show me photos of the bedroom", history=[], provider="bedrock")
        data = chat(req)
        self.assertEqual(data["status"], "success")
        self.assertIn("bedroom", data["assistant_message"].lower())
        self.assertIsInstance(data["images"], list)

    def test_enquiry_submission(self):
        req = EnquiryRequest(
            name="Arun Kumar",
            phone="+91 98401 23456",
            property_id="AQG-2BHK-01",
            message="I would like to schedule a weekend site visit.",
            consent=True,
        )
        data = enquiry(req)
        self.assertEqual(data["status"], "success")
        self.assertIn("enquiry_id", data)

    def test_list_documents_endpoint(self):
        data = list_documents()
        self.assertEqual(data["status"], "success")
        self.assertIn("documents", data)
        self.assertGreater(data["count"], 0)

    def test_get_images_endpoint(self):
        data = get_images(category="bedroom")
        self.assertEqual(data["status"], "success")
        self.assertIn("images", data)


if __name__ == "__main__":
    unittest.main()
