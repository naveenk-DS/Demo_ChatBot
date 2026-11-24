"""
PDF Processing, Chunking & RAG Retrieval Tests for EstateAI.
Tests PyMuPDF text extraction, metadata preservation, chunking boundaries,
FAISS / Vector indexing, BM25 scoring, and document fingerprinting.
"""

import sys
import unittest
from pathlib import Path

backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.rag.loader import load_pdf_documents, extract_document_metadata
from app.rag.chunker import chunk_documents
from app.rag.retriever import DynamicBM25, hybrid_search
from app.rag.store import FaissVectorStore

PDF_DIR = Path(__file__).resolve().parent.parent.parent / "pdf"


class TestPdfRagPipeline(unittest.TestCase):
    def test_pdf_extraction_and_metadata(self):
        self.assertTrue(PDF_DIR.exists(), f"PDF directory not found at {PDF_DIR}")
        
        # Load sample PDFs from pdf/ directory
        docs = load_pdf_documents(PDF_DIR)
        self.assertGreater(len(docs), 0, "Expected at least 1 extracted page from PDF repository")

        sample = docs[0]
        self.assertIn("source", sample)
        self.assertIn("page", sample)
        self.assertIn("text", sample)
        self.assertGreater(len(sample["text"]), 10)
        self.assertIsInstance(sample["page"], int)

    def test_chunking_boundaries_and_categories(self):
        mock_doc = [{
            "source": "Casagrand_Aquagrove_Specifications.pdf",
            "page": 1,
            "text": (
                "LIVING AND DINING ROOM:\n"
                "Flooring: 800 x 800 mm vitrified tiles of premium brand.\n"
                "Main Door: Teak wood frame with double-side veneered flush door shutter.\n"
                "Windows: UPVC sliding windows with mosquito mesh provision.\n\n"
                "MASTER BEDROOM:\n"
                "Flooring: Laminated wooden flooring.\n"
                "Ceiling Height: 3000 mm floor-to-ceiling clear height.\n"
                "Electrical: Concealed copper wiring with Schneider modular switches."
            ),
            "property_name": "Casagrand Aquagrove",
            "configuration": "2BHK",
        }]

        chunks = chunk_documents(mock_doc)
        self.assertGreaterEqual(len(chunks), 1)

        first_chunk = chunks[0]
        self.assertIn("source", first_chunk)
        self.assertIn("text", first_chunk)
        self.assertIn("category", first_chunk)
        self.assertEqual(first_chunk["property_name"], "Casagrand Aquagrove")

    def test_bm25_retrieval_scoring(self):
        chunks = [
            {
                "chunk_id": "c1",
                "text": "Living room has 800x800 mm premium vitrified tiles and UPVC sliding windows.",
                "source": "doc1.pdf",
                "page": 1,
            },
            {
                "chunk_id": "c2",
                "text": "Master bedroom has wooden finish flooring with attached bathroom and Kohler fittings.",
                "source": "doc1.pdf",
                "page": 2,
            },
            {
                "chunk_id": "c3",
                "text": "Clubhouse features an indoor badminton court, Olympic sized swimming pool and gym.",
                "source": "amenities.pdf",
                "page": 1,
            },
        ]

        bm25 = DynamicBM25(chunks)

        # Query for swimming pool should score chunk 3 highest
        scores_pool = bm25.score("swimming pool clubhouse")
        self.assertGreater(len(scores_pool), 0)
        top_doc_idx = scores_pool[0][0]
        self.assertEqual(top_doc_idx, 2)

        # Query for bedroom should score chunk 2 highest
        scores_bed = bm25.score("master bedroom wooden flooring")
        self.assertGreater(len(scores_bed), 0)
        self.assertEqual(scores_bed[0][0], 1)

    def test_document_fingerprinting_duplicate_prevention(self):
        store = FaissVectorStore(index_dir=backend_root / "data" / "test_faiss_temp")
        
        # Add test doc
        mock_chunks = [{
            "source": "test_script.pdf",
            "page": 1,
            "text": "Sample architectural specification text for testing duplicate fingerprints.",
            "property_name": "Test Property",
            "configuration": "3BHK",
        }]

        # Fake fingerprint
        hash1 = "d41d8cd98f00b204e9800998ecf8427e"
        store.fingerprints["test_script.pdf"] = hash1
        store.chunks_metadata = [{"text": "existing"}]

        # Calling is_document_indexed should return True
        self.assertTrue(store.is_document_indexed("test_script.pdf", hash1))
        # Different hash should return False
        self.assertFalse(store.is_document_indexed("test_script.pdf", "different_hash_12345"))


if __name__ == "__main__":
    unittest.main()

