"""
Automated Unit Tests for Amazon Bedrock Knowledge Bases Integration.
Tests:
1. Bedrock Knowledge Base Service initialization and configuration detection.
2. Retrieve API request formatting and configurable search type (HYBRID vs SEMANTIC).
3. Retrieval result mapping and S3 URI source attribution.
4. Production failure safety: NO silent fallback to local FAISS when KB is configured.
5. Development / offline fallback to local FAISS when KB is unconfigured.
6. Configurable S3 prefix supporting project folder hierarchies in cg-website-chatbot-data.
7. Data separation: structured CSV/XLSX/JSON vs unstructured PDF/TXT documents.
"""

import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from botocore.exceptions import ClientError

from app.services.bedrock_kb_service import (
    BedrockKnowledgeBaseService,
    BedrockKnowledgeBaseError,
)
from app.rag.retriever import retrieve_relevant_chunks
from app.services.s3_service import S3Service, SUPPORTED_STRUCTURED_EXTENSIONS, SUPPORTED_UNSTRUCTURED_EXTENSIONS


class TestBedrockKnowledgeBaseIntegration(unittest.TestCase):
    def setUp(self):
        self.mock_kb_id = "KB12345678"

    # 1. Unconfigured behavior
    def test_kb_unconfigured_detection(self):
        """Verifies that an unconfigured or placeholder KB ID is detected as not configured."""
        kb = BedrockKnowledgeBaseService(kb_id="")
        self.assertFalse(kb.is_configured())
        self.assertEqual(kb.retrieve("test query"), [])

        kb_placeholder = BedrockKnowledgeBaseService(kb_id="YOUR_BEDROCK_KNOWLEDGE_BASE_ID")
        self.assertFalse(kb_placeholder.is_configured())

    # 2. Configurable search type: HYBRID vs SEMANTIC
    def test_kb_search_type_configuration(self):
        """Verifies configurable HYBRID vs SEMANTIC search type based on vector store capabilities."""
        with patch.dict(os.environ, {"BEDROCK_KB_SEARCH_TYPE": "SEMANTIC"}):
            kb_semantic = BedrockKnowledgeBaseService(kb_id=self.mock_kb_id)
            self.assertEqual(kb_semantic.search_type, "SEMANTIC")

        with patch.dict(os.environ, {"BEDROCK_KB_SEARCH_TYPE": "HYBRID"}):
            kb_hybrid = BedrockKnowledgeBaseService(kb_id=self.mock_kb_id)
            self.assertEqual(kb_hybrid.search_type, "HYBRID")

        # Invalid defaults to HYBRID
        with patch.dict(os.environ, {"BEDROCK_KB_SEARCH_TYPE": "UNKNOWN_MODE"}):
            kb_invalid = BedrockKnowledgeBaseService(kb_id=self.mock_kb_id)
            self.assertEqual(kb_invalid.search_type, "HYBRID")

    # 3. Successful Retrieve API call and result normalization
    @patch("boto3.Session")
    def test_kb_retrieve_successful_mapping(self, mock_session_cls):
        """Verifies that bedrock-agent-runtime.retrieve results are normalized with S3 source attribution."""
        mock_client = MagicMock()
        mock_session = MagicMock()
        mock_session.client.return_value = mock_client
        mock_session_cls.return_value = mock_session

        mock_client.retrieve.return_value = {
            "retrievalResults": [
                {
                    "content": {"text": "Master bedroom flooring is imported vitrified tiles 800x800mm."},
                    "location": {
                        "type": "S3",
                        "s3Location": {"uri": "s3://cg-website-chatbot-data/Casagrand Aquagrove/Specifications.pdf"},
                    },
                    "score": 0.88,
                    "metadata": {"pageNumber": "4"},
                },
                {
                    "content": {"text": "Clubhouse includes Olympic-length swimming pool and badminton courts."},
                    "location": {
                        "type": "S3",
                        "s3Location": {"uri": "s3://cg-website-chatbot-data/Casagrand Aquagrove/Amenities.pdf"},
                    },
                    "score": 0.76,
                    "metadata": {"pageNumber": "1"},
                },
            ]
        }

        kb = BedrockKnowledgeBaseService(kb_id=self.mock_kb_id, search_type="HYBRID")
        kb._client = mock_client

        results = kb.retrieve("bedroom flooring specifications", top_k=2)

        self.assertEqual(len(results), 2)
        # Verify first result
        self.assertIn("vitrified tiles", results[0]["text"])
        self.assertEqual(results[0]["source"], "Casagrand Aquagrove/Specifications.pdf")
        self.assertEqual(results[0]["page"], 4)
        self.assertEqual(results[0]["score"], 0.88)
        self.assertEqual(results[0]["s3_uri"], "s3://cg-website-chatbot-data/Casagrand Aquagrove/Specifications.pdf")

        # Verify client API invocation parameters
        mock_client.retrieve.assert_called_once()
        call_kwargs = mock_client.retrieve.call_args[1]
        self.assertEqual(call_kwargs["knowledgeBaseId"], self.mock_kb_id)
        self.assertEqual(call_kwargs["retrievalQuery"]["text"], "bedroom flooring specifications")
        self.assertEqual(
            call_kwargs["retrievalConfiguration"]["vectorSearchConfiguration"]["overrideSearchType"],
            "HYBRID",
        )

    # 4. Production failure safety: NO silent fallback to FAISS
    def test_kb_production_fail_closed_no_silent_fallback(self):
        """
        CRITICAL SAFETY TEST:
        When BEDROCK_KNOWLEDGE_BASE_ID is configured in production,
        a Knowledge Base failure MUST raise an exception and NOT silently fall back to FAISS.
        """
        with patch("app.services.bedrock_kb_service.BedrockKnowledgeBaseService.is_configured", return_value=True):
            with patch("app.services.bedrock_kb_service.BedrockKnowledgeBaseService.retrieve") as mock_retrieve:
                mock_retrieve.side_effect = BedrockKnowledgeBaseError("ResourceNotFoundException: KnowledgeBase not found")
                
                with patch.dict(os.environ, {"APP_ENV": "production", "ALLOW_LOCAL_FALLBACK": "false"}):
                    with self.assertRaises(BedrockKnowledgeBaseError):
                        retrieve_relevant_chunks(query="specifications question")

    # 5. Development mode permits fallback to local FAISS when unconfigured
    def test_kb_development_fallback_when_unconfigured(self):
        """Verifies that when Knowledge Base is unconfigured, local FAISS hybrid search is engaged in development."""
        with patch("app.services.bedrock_kb_service.BedrockKnowledgeBaseService.is_configured", return_value=False):
            with patch("app.rag.retriever.hybrid_search", return_value=[{"text": "local chunk", "source": "local.pdf"}]) as mock_hybrid:
                results = retrieve_relevant_chunks(query="test query")
                mock_hybrid.assert_called_once()
                self.assertEqual(len(results), 1)
                self.assertEqual(results[0]["text"], "local chunk")

    # 6. Configurable S3 Prefix supporting project folder hierarchies
    def test_configurable_s3_prefix_project_folders(self):
        """Verifies that S3Service supports empty prefix for scanning multi-level project folders."""
        s3 = S3Service(bucket_name="casa-chatbot", prefix="")
        self.assertEqual(s3.bucket_name, "casa-chatbot")
        self.assertEqual(s3.prefix, "")

        # Verify key mapping with arbitrary nested project folders
        cache_path = s3.cache_dir / "Casagrand Aquagrove" / "Tower A" / "spec.pdf"
        s3_key = s3.get_s3_key_for_path(cache_path)
        self.assertEqual(s3_key, "Casagrand Aquagrove/Tower A/spec.pdf")

    # 7. Data Separation: Structured datasets vs Unstructured documents
    def test_s3_document_type_separation(self):
        """Verifies clear separation between structured datasets and unstructured documents."""
        self.assertIn(".csv", SUPPORTED_STRUCTURED_EXTENSIONS)
        self.assertIn(".xlsx", SUPPORTED_STRUCTURED_EXTENSIONS)
        self.assertIn(".json", SUPPORTED_STRUCTURED_EXTENSIONS)
        self.assertNotIn(".pdf", SUPPORTED_STRUCTURED_EXTENSIONS)

        self.assertIn(".pdf", SUPPORTED_UNSTRUCTURED_EXTENSIONS)
        self.assertNotIn(".csv", SUPPORTED_UNSTRUCTURED_EXTENSIONS)


if __name__ == "__main__":
    unittest.main()
