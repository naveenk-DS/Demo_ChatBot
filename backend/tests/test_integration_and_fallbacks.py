"""
Integration & Fallback Resilience Tests for EstateAI.
Verifies that:
1. Athena is disabled and never triggers Athena calls or costs.
2. S3 gracefully falls back to local cache when bucket is not configured.
3. Bedrock gracefully falls back to rule-based intent/filter extraction when offline.
4. System remains 100% operational in disconnected/test environments.
"""

import os
import sys
import unittest
from pathlib import Path

backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.athena import is_athena_enabled, run_query
from app.services.s3_service import S3Service
from app.services.bedrock_service import BedrockService


class TestIntegrationAndFallbacks(unittest.TestCase):
    def setUp(self):
        self._orig_env = {
            "ALLOW_LOCAL_FALLBACK": os.environ.get("ALLOW_LOCAL_FALLBACK"),
            "APP_ENV": os.environ.get("APP_ENV"),
        }
        os.environ["ALLOW_LOCAL_FALLBACK"] = "true"
        os.environ["APP_ENV"] = "test"

    def tearDown(self):
        for k, v in self._orig_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    def test_athena_disabled_by_default(self):
        # Verification that Athena is disabled
        self.assertFalse(is_athena_enabled())
        # run_query must return empty list without connecting or throwing
        records = run_query("SELECT * FROM properties")
        self.assertEqual(records, [])

    def test_s3_graceful_fallback(self):
        # Using unconfigured or empty bucket
        s3 = S3Service(bucket_name="your-property-bucket")
        self.assertFalse(s3.is_configured())
        
        # sync_documents must fall back to local documents safely
        docs = s3.sync_documents()
        self.assertIsInstance(docs, list)
        self.assertGreater(len(docs), 0, "Expected local cached/repo documents as fallback")

    def test_bedrock_rule_based_fallback(self):
        bedrock = BedrockService()
        
        # 1. Greeting
        res_hi = bedrock._fallback_filter_extractor("Hi, good morning")
        self.assertEqual(res_hi.intent, "general_question")

        # 2. 2BHK search in Perungudi under 1 Cr
        res_search = bedrock._fallback_filter_extractor("Show me 2BHK in Perungudi under 1 Crore")
        self.assertEqual(res_search.intent, "property_search")
        self.assertEqual(res_search.bhk, 2)
        self.assertEqual(res_search.max_price, 10000000)
        self.assertEqual(res_search.location, "Perungudi")

        # 3. Document QA for civil specifications
        res_qa = bedrock._fallback_filter_extractor("What are the civil construction specifications and wiring rules?")
        self.assertEqual(res_qa.intent, "document_qa")

        # 4. Image request
        res_img = bedrock._fallback_filter_extractor("Show me photos of the bathroom")
        self.assertEqual(res_img.intent, "media_request")


if __name__ == "__main__":
    unittest.main()

