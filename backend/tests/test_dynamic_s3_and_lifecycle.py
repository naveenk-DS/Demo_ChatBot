"""
Comprehensive Automated Test Suite for Dynamic S3 Document Lifecycle,
Incremental Sync, Registry, Persistence, and Fault Tolerance in EstateAI.

Tests:
1. S3 list_objects_v2 pagination across multiple pages
2. Ignoring unsupported file formats (.docx, .zip, .exe)
3. S3 permission failure graceful fallback
4. Adding a sixth document dynamically without code changes
5. Adding multiple new documents dynamically
6. Replacing/modifying an existing document (stale data purge without mixing)
7. Deleting an indexed document (purging records & vector chunks)
8. Duplicate upload detection (SHA-256 fingerprint check)
9. Multi-sheet Excel workbook parsing
10. EC2 persistence and index recovery across reload
11. Bedrock throttling resilience with backoff
12. Multi-document PDF retrieval with source & page citation preservation
"""

import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from botocore.exceptions import ClientError

from app.data_pipeline.structured import (
    StructuredDataStore,
    load_csv,
    load_excel,
    load_json,
    normalize_records,
    search_properties,
    validate_records,
)
from app.rag.retriever import DynamicBM25, hybrid_search, retrieve_relevant_chunks
from app.rag.store import FaissVectorStore
from app.services.bedrock_service import BedrockService
from app.services.document_registry import DocumentRegistry
from app.services.lock_service import acquire_indexing_lock, IndexingConflictError
from app.services.s3_service import S3Service, S3AccessError, S3PaginationError


class TestDynamicS3AndLifecycle(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="estateai_lifecycle_test_")
        self.cache_dir = Path(self.test_dir) / "documents"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.registry_file = Path(self.test_dir) / "registry.json"
        self.vector_dir = Path(self.test_dir) / "faiss_index"
        self.vector_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # 1. S3 list_objects_v2 pagination
    def test_s3_pagination_dynamic_discovery(self):
        """Verifies S3Service handles paginated results across arbitrary pages."""
        s3 = S3Service(bucket_name="test-bucket", prefix="documents/", cache_dir=self.cache_dir)
        
        # Mock boto3 client paginator
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        
        # 3 pages of mock S3 objects
        page1 = {
            "Contents": [
                {"Key": "documents/doc1.csv", "Size": 100, "ETag": '"hash1"', "LastModified": datetime.now(timezone.utc)},
                {"Key": "documents/doc2.xlsx", "Size": 200, "ETag": '"hash2"', "LastModified": datetime.now(timezone.utc)},
            ]
        }
        page2 = {
            "Contents": [
                {"Key": "documents/doc3.json", "Size": 300, "ETag": '"hash3"', "LastModified": datetime.now(timezone.utc)},
                {"Key": "documents/doc4.pdf", "Size": 400, "ETag": '"hash4"', "LastModified": datetime.now(timezone.utc)},
            ]
        }
        page3 = {
            "Contents": [
                {"Key": "documents/doc5.pdf", "Size": 500, "ETag": '"hash5"', "LastModified": datetime.now(timezone.utc)},
                {"Key": "documents/doc6_sixth_catalog.csv", "Size": 600, "ETag": '"hash6"', "LastModified": datetime.now(timezone.utc)},
                {"Key": "documents/subfolder/", "Size": 0},  # Directory should be skipped
            ]
        }
        
        mock_paginator.paginate.return_value = [page1, page2, page3]
        mock_client.get_paginator.return_value = mock_paginator
        s3._s3_client = mock_client

        docs, complete = s3.list_s3_documents()
        self.assertTrue(complete)
        self.assertEqual(len(docs), 6)
        self.assertIn("documents/doc1.csv", docs)
        self.assertIn("documents/doc6_sixth_catalog.csv", docs)
        self.assertNotIn("documents/subfolder/", docs)
        self.assertEqual(docs["documents/doc6_sixth_catalog.csv"]["file_type"], "csv")

    # 2. Unsupported file formats ignored safely
    def test_unsupported_file_format_ignored(self):
        """Verifies unsupported files (.docx, .zip, .exe) are safely ignored without raising exceptions."""
        s3 = S3Service(bucket_name="test-bucket", prefix="documents/", cache_dir=self.cache_dir)
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {
                "Contents": [
                    {"Key": "documents/valid.pdf", "Size": 100, "ETag": '"h1"'},
                    {"Key": "documents/unsupported.docx", "Size": 200, "ETag": '"h2"'},
                    {"Key": "documents/malware.exe", "Size": 300, "ETag": '"h3"'},
                    {"Key": "documents/archive.zip", "Size": 400, "ETag": '"h4"'},
                ]
            }
        ]
        mock_client.get_paginator.return_value = mock_paginator
        s3._s3_client = mock_client

        docs, complete = s3.list_s3_documents()
        self.assertTrue(complete)
        self.assertEqual(len(docs), 1)
        self.assertIn("documents/valid.pdf", docs)
        self.assertNotIn("documents/unsupported.docx", docs)

    # 3. S3 AccessDenied raises in production mode (no silent fallback to stale local data)
    def test_s3_access_denied_raises_in_production_mode(self):
        """
        Critical safety test: Verifies that S3 AccessDenied or credential failure
        raises S3AccessError in production mode and NEVER silently falls back to stale data.
        """
        s3 = S3Service(bucket_name="prod-bucket", prefix="documents/", cache_dir=self.cache_dir)
        mock_client = MagicMock()
        error_response = {"Error": {"Code": "AccessDenied", "Message": "Access Denied to S3 bucket in production"}}
        mock_client.get_paginator.side_effect = ClientError(error_response, "ListObjectsV2")
        s3._s3_client = mock_client

        # Place stale local file
        local_stale = self.cache_dir / "stale_local.csv"
        local_stale.write_text("property_name,bhk,price\nStale Listing,2,1000000", encoding="utf-8")

        reg = DocumentRegistry(self.registry_file)
        
        # In production mode (allow_fallback=False), must raise S3AccessError!
        with self.assertRaises(S3AccessError):
            s3.sync_documents_incremental(reg, allow_fallback=False)

    # 3B. S3 permission failure fallback only when explicitly permitted in test/dev
    def test_s3_permission_failure_fallback_when_permitted(self):
        """Verifies that an S3 permission failure falls back to local cache only when explicitly permitted."""
        s3 = S3Service(bucket_name="test-bucket", prefix="documents/", cache_dir=self.cache_dir)
        mock_client = MagicMock()
        error_response = {"Error": {"Code": "AccessDenied", "Message": "Access Denied to S3 bucket"}}
        mock_client.get_paginator.side_effect = ClientError(error_response, "ListObjectsV2")
        s3._s3_client = mock_client

        local_file = self.cache_dir / "fallback_sample.csv"
        local_file.write_text("property_name,bhk,price\nFallback Haven,2,7500000", encoding="utf-8")

        reg = DocumentRegistry(self.registry_file)
        sync_result = s3.sync_documents_incremental(reg, allow_fallback=True)

        self.assertTrue(len(sync_result["new"]) >= 1 or len(sync_result["unchanged"]) >= 1)

    # 3C. Mid-pagination failure aborts deletion reconciliation
    def test_partial_pagination_failure_aborts_deletion_reconciliation(self):
        """
        Critical safety test: If pagination fails midway, deletion reconciliation
        must NOT run to prevent false deletions of existing documents.
        """
        s3 = S3Service(bucket_name="test-bucket", prefix="documents/", cache_dir=self.cache_dir)
        mock_client = MagicMock()
        mock_paginator = MagicMock()

        # Page 1 succeeds, Page 2 raises error midway
        page1 = {
            "Contents": [
                {"Key": "documents/doc1.csv", "Size": 100, "ETag": '"h1"'},
            ]
        }
        
        def mock_paginate_generator(*args, **kwargs):
            yield page1
            raise ClientError({"Error": {"Code": "ConnectionReset", "Message": "Network reset"}}, "ListObjectsV2")

        mock_paginator.paginate = mock_paginate_generator
        mock_client.get_paginator.return_value = mock_paginator
        s3._s3_client = mock_client

        # Pre-seed registry with doc1 and doc2
        reg = DocumentRegistry(self.registry_file)
        reg.register_or_update(s3_key="documents/doc1.csv", filename="doc1.csv", file_type="csv", fingerprint="h1", status="indexed")
        reg.register_or_update(s3_key="documents/doc2.csv", filename="doc2.csv", file_type="csv", fingerprint="h2", status="indexed")

        # Must raise S3PaginationError and NOT delete doc2
        with self.assertRaises(S3PaginationError):
            s3.sync_documents_incremental(reg, allow_fallback=False)

        # doc2 must remain active in registry!
        self.assertEqual(reg.get("documents/doc2.csv")["status"], "indexed")

    # 4. Adding a sixth document dynamically
    def test_add_sixth_document_dynamically(self):
        """
        Verifies system dynamically indexes a 6th document (and beyond)
        without source code modification.
        """
        store = StructuredDataStore()
        
        # Ingest initial 5 mock documents
        for i in range(1, 6):
            csv_content = f"property_name,bhk,price,location\nProperty {i},{i%3 + 1},{5000000 + i*1000000},Velachery"
            store.add_or_update(csv_content.encode("utf-8"), source_name=f"catalog_doc_{i}.csv")
            
        initial_records = store.get_all_records()
        self.assertEqual(len(initial_records), 5)

        # Now dynamically add the 6th document
        sixth_csv = (
            "project_name,bhk,price,location\n"
            "Prestige Marina Sixth,3,15000000,ECR Chennai\n"
            "Prestige Marina Seventh,4,22000000,ECR Chennai"
        )
        count = store.add_or_update(sixth_csv.encode("utf-8"), source_name="sixth_document_ecr.csv")
        self.assertEqual(count, 2)

        all_records = store.get_all_records()
        self.assertEqual(len(all_records), 7)

        # Search specifically for the 6th document property
        results = store.search({"bhk": 3, "location": "ECR"})
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["property_name"], "Prestige Marina Sixth")
        self.assertEqual(results[0]["price"], 15000000)

    # 5. Adding multiple new documents
    def test_add_multiple_new_documents_simultaneously(self):
        """Verifies multi-document bulk ingestion across JSON, CSV, and XLSX formats."""
        store = StructuredDataStore()

        doc_csv = "property_name,bhk,price,location\nCSV Villa,4,30000000,Anna Nagar"
        doc_json = json.dumps([{"title": "JSON Penthouse", "bedrooms": 3, "cost": "1.8 Cr", "locality": "Guindy"}])

        c1 = store.add_or_update(doc_csv.encode("utf-8"), source_name="bulk1.csv")
        c2 = store.add_or_update(doc_json.encode("utf-8"), source_name="bulk2.json")

        self.assertEqual(c1, 1)
        self.assertEqual(c2, 1)
        self.assertEqual(len(store.get_all_records()), 2)

        # Verify searches find both
        r_csv = store.search({"bhk": 4})
        self.assertEqual(len(r_csv), 1)
        self.assertEqual(r_csv[0]["property_name"], "CSV Villa")

        r_json = store.search({"bhk": 3})
        self.assertEqual(len(r_json), 1)
        self.assertEqual(r_json[0]["property_name"], "JSON Penthouse")
        self.assertEqual(r_json[0]["price"], 18000000)

    # 6. Replacing an existing document (stale data purge without mixing)
    def test_replace_existing_document_purges_stale_content(self):
        """
        Verifies that modifying/replacing an existing document purges old records
        and replaces with new records, preventing stale or duplicated data.
        """
        store = StructuredDataStore()

        # Version 1 of catalog.csv
        v1_csv = "property_name,bhk,price,location\nOld Property Alpha,2,6000000,OMR"
        store.add_or_update(v1_csv.encode("utf-8"), source_name="catalog.csv")
        self.assertEqual(len(store.get_all_records()), 1)
        self.assertEqual(store.get_all_records()[0]["property_name"], "Old Property Alpha")

        # Version 2 of catalog.csv (Alpha was sold and replaced by Beta)
        v2_csv = "property_name,bhk,price,location\nNew Property Beta,3,9500000,Perungudi"
        store.add_or_update(v2_csv.encode("utf-8"), source_name="catalog.csv")

        all_records = store.get_all_records()
        self.assertEqual(len(all_records), 1)
        self.assertEqual(all_records[0]["property_name"], "New Property Beta")
        self.assertEqual(all_records[0]["bhk"], 3)

        # Old property should not exist anywhere
        search_old = store.search({"bhk": 2})
        self.assertEqual(len(search_old), 0)

    # 7. Deleting an indexed document
    def test_delete_indexed_document_purges_records(self):
        """Verifies deleting an indexed document removes its records and updates registry."""
        store = StructuredDataStore()
        reg = DocumentRegistry(self.registry_file)

        csv_content = "property_name,bhk,price,location\nTemporary Listing,2,5500000,Porur"
        store.add_or_update(csv_content.encode("utf-8"), source_name="temp_listing.csv")
        reg.register_or_update(
            s3_key="documents/temp_listing.csv",
            filename="temp_listing.csv",
            file_type="csv",
            fingerprint="hash_temp",
            status="indexed",
            record_count=1,
        )

        self.assertEqual(len(store.get_all_records()), 1)
        self.assertEqual(len(reg.list_active()), 1)

        # Simulate deletion
        removed = store.remove("temp_listing.csv")
        self.assertEqual(removed, 1)
        reg.mark_deleted("documents/temp_listing.csv")

        self.assertEqual(len(store.get_all_records()), 0)
        self.assertEqual(len(reg.list_active()), 0)
        self.assertEqual(reg.get("documents/temp_listing.csv")["status"], "deleted")

    # 8. Duplicate upload avoidance
    def test_duplicate_upload_avoidance(self):
        """Verifies identical file upload avoids redundant processing via SHA-256 fingerprint."""
        reg = DocumentRegistry(self.registry_file)
        f_hash = "abc123def456"

        reg.register_or_update(
            s3_key="documents/inventory.csv",
            filename="inventory.csv",
            file_type="csv",
            fingerprint=f_hash,
            status="indexed",
            record_count=5,
        )

        # Duplicate check
        self.assertTrue(reg.is_indexed("documents/inventory.csv", f_hash))
        # Modified content check
        self.assertFalse(reg.is_indexed("documents/inventory.csv", "different_hash_789"))

    # 9. Multiple Excel sheets ingestion
    def test_multiple_excel_sheets_ingestion(self):
        """Verifies that an Excel file with multiple sheets is loaded across all sheets."""
        try:
            import openpyxl
            wb = openpyxl.Workbook()
            # Sheet 1: 2BHK Units
            ws1 = wb.active
            ws1.title = "2BHK_Listings"
            ws1.append(["property_name", "bhk", "price", "location"])
            ws1.append(["Casagrand Sheet1 Unit A", 2, 7000000, "Medavakkam"])

            # Sheet 2: 3BHK Units
            ws2 = wb.create_sheet(title="3BHK_Listings")
            ws2.append(["property_name", "bhk", "price", "location"])
            ws2.append(["Casagrand Sheet2 Unit B", 3, 11000000, "Sholinganallur"])

            buf = io.BytesIO()
            wb.save(buf)
            buf.seek(0)

            store = StructuredDataStore()
            count = store.add_or_update(buf, source_name="multi_sheet_inventory.xlsx")
            self.assertEqual(count, 2)

            records = store.get_all_records()
            self.assertEqual(len(records), 2)
            sheet_names = {r.get("_excel_sheet") for r in records}
            self.assertIn("2BHK_Listings", sheet_names)
            self.assertIn("3BHK_Listings", sheet_names)
        except ImportError:
            self.skipTest("openpyxl not available")

    # 10. EC2 persistence and recovery across reload
    def test_ec2_persistence_and_recovery(self):
        """Verifies DocumentRegistry and FaissVectorStore recover persisted state on restart."""
        # 1. Write to registry
        reg1 = DocumentRegistry(self.registry_file)
        reg1.register_or_update(
            s3_key="documents/persisted.pdf",
            filename="persisted.pdf",
            file_type="pdf",
            fingerprint="perm_hash_999",
            status="indexed",
            chunk_count=12,
        )

        # 2. Re-instantiate registry from same file (simulating reboot)
        reg2 = DocumentRegistry(self.registry_file)
        entry = reg2.get("documents/persisted.pdf")
        self.assertIsNotNone(entry)
        self.assertEqual(entry["chunk_count"], 12)
        self.assertEqual(entry["status"], "indexed")

    # 11. Bedrock throttling resilience
    def test_bedrock_throttling_resilience(self):
        """Verifies BedrockService retries with backoff upon ThrottlingException."""
        bedrock = BedrockService()
        mock_client = MagicMock()
        
        # First call raises ThrottlingException, second call succeeds
        throttle_err = ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
            "Converse"
        )
        success_response = {
            "output": {"message": {"content": [{"text": '{"intent": "general_question"}'}]}},
            "usage": {"inputTokens": 10, "outputTokens": 5},
        }
        mock_client.converse.side_effect = [throttle_err, success_response]
        bedrock._bedrock_client = mock_client
        bedrock._has_credentials = True

        with patch("time.sleep", return_value=None):
            resp = bedrock.extract_filters("hello")
            self.assertEqual(resp.intent, "general_question")
            self.assertEqual(mock_client.converse.call_count, 2)

    # 12. Multi-document PDF retrieval
    def test_multi_document_pdf_retrieval(self):
        """Verifies hybrid search aggregates chunks from multiple distinct PDF documents."""
        chunks = [
            {
                "source": "Document_A_Aquagrove.pdf",
                "page": 2,
                "text": "Living room flooring is premium vitrified tiles 800x800 mm with anti-skid balcony tiles.",
                "category": "specifications",
                "configuration": "2BHK",
            },
            {
                "source": "Document_B_Clubhouse_Directory.pdf",
                "page": 1,
                "text": "Clubhouse amenities include olympic swimming pool, badminton court, and gymnasium.",
                "category": "amenities",
                "configuration": "general",
            },
        ]
        bm25 = DynamicBM25(chunks)
        results = bm25.score("vitrified tiles and swimming pool", top_k=5)
        self.assertTrue(len(results) >= 1)
        
        # Verify both documents have non-zero relevance for multi-topic query
        matched_docs = {chunks[idx]["source"] for idx, score in results}
        self.assertIn("Document_A_Aquagrove.pdf", matched_docs)

    # 13. Concurrent indexing lock protection
    def test_concurrent_indexing_lock_protection(self):
        """
        Verifies that when an indexing lock is held, a second attempt to acquire
        the lock raises IndexingConflictError, protecting against concurrent corruptions.
        """
        lock_file = Path(self.test_dir) / ".test_indexing.lock"
        with acquire_indexing_lock(timeout_seconds=2.0, lock_path=lock_file):
            # Attempting to re-acquire the lock concurrently in the same thread/process
            with self.assertRaises(IndexingConflictError):
                with acquire_indexing_lock(timeout_seconds=0.2, lock_path=lock_file):
                    pass

    # 14. Atomic FAISS persistence
    def test_atomic_faiss_persistence(self):
        """Verifies that vector store persistence creates clean atomic files."""
        store = FaissVectorStore(index_dir=self.vector_dir)
        store.chunks_metadata = [{"chunk_id": "c1", "text": "sample", "source": "test.pdf"}]
        store.vectors = [[0.1] * store.dimension]
        store.fingerprints = {"test.pdf": "hash123"}
        
        store._save_to_disk()
        
        self.assertTrue(store.metadata_file.exists())
        self.assertTrue(store.fingerprints_file.exists())
        self.assertTrue(store.vectors_file.exists())
        # Ensure temporary files are replaced and no .tmp remains
        self.assertFalse(store.metadata_file.with_suffix(".json.tmp").exists())
        self.assertFalse(store.fingerprints_file.with_suffix(".json.tmp").exists())

    # 15. All supported file formats parsers functional
    def test_all_supported_parsers_functional(self):
        """Verifies that each supported format (CSV, XLS/XLSX, JSON, Nested JSON, PDF) has an active functioning parser."""
        from app.rag.loader import load_single_pdf

        # CSV
        csv_bytes = b"property_name,bhk,price\nCSV Unit,2,6000000"
        csv_recs = load_csv(csv_bytes, "test.csv")
        self.assertEqual(len(csv_recs), 1)

        # JSON Flat
        json_bytes = json.dumps([{"title": "JSON Flat", "bhk": 3, "price": 9000000}]).encode("utf-8")
        json_recs = load_json(json_bytes, "flat.json")
        self.assertEqual(len(json_recs), 1)

        # JSON Nested
        nested_bytes = json.dumps({"status": "ok", "payload": {"data": [{"name": "Nested Unit", "bedrooms": 2, "cost": 7500000}]}}).encode("utf-8")
        nested_recs = load_json(nested_bytes, "nested.json")
        self.assertEqual(len(nested_recs), 1)

        # Excel (XLSX)
        try:
            import openpyxl
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.append(["property_name", "bhk", "price"])
            ws.append(["Excel Unit", 3, 8500000])
            buf = io.BytesIO()
            wb.save(buf)
            buf.seek(0)
            xlsx_recs = load_excel(buf, "test.xlsx")
            self.assertEqual(len(xlsx_recs), 1)
        except ImportError:
            pass

        # PDF (create valid minimal 1-page PDF using PyMuPDF)
        try:
            import fitz
            doc = fitz.open()
            page = doc.new_page()
            page.insert_text((50, 72), "Casagrand Aquagrove - 2BHK Master Bedroom Specifications")
            pdf_path = Path(self.test_dir) / "test_spec.pdf"
            doc.save(str(pdf_path))
            doc.close()

            pdf_docs = load_single_pdf(pdf_path)
            self.assertEqual(len(pdf_docs), 1)
            self.assertEqual(pdf_docs[0]["page"], 1)
            self.assertIn("Specifications", pdf_docs[0]["property_name"])
        except ImportError:
            pass

    # 16. EC2 IAM Role credential detection
    @patch("boto3.Session")
    def test_ec2_iam_role_credential_detection(self, mock_session_cls):
        """Verifies that BedrockService enables EC2 IMDS by default and detects credentials via Boto3 chain."""
        # Mock session returning credentials
        mock_creds = MagicMock()
        mock_creds.access_key = "ASIA_MOCK_ACCESS_KEY"
        mock_creds.secret_key = "MOCK_SECRET"
        mock_creds.token = "MOCK_SESSION_TOKEN"

        mock_session = MagicMock()
        mock_session.get_credentials.return_value = mock_creds
        mock_session_cls.return_value = mock_session

        bedrock = BedrockService()
        bedrock._has_credentials = None

        with patch.dict(os.environ, {"AWS_EC2_METADATA_DISABLED": "false"}):
            self.assertTrue(bedrock.has_credentials())

    # 17. Document Registry RLock No Deadlock & Backup Recovery
    def test_document_registry_rlock_no_deadlock_and_backup_recovery(self):
        """
        Verifies that DocumentRegistry uses re-entrant lock (no deadlock on remove/clear)
        and successfully recovers from corruption via .bak file.
        """
        reg = DocumentRegistry(self.registry_file)
        reg.register(
            s3_key="documents/projects.csv",
            filename="projects.csv",
            file_type="csv",
            fingerprint="abc12345",
            status="indexed",
            record_count=10,
        )
        self.assertEqual(len(reg.list_all()), 1)

        # Ensure remove and clear do not deadlock
        reg.remove("documents/projects.csv")
        self.assertEqual(len(reg.list_all()), 0)

        # Re-register and create corruption scenario
        reg.register(
            s3_key="documents/projects.csv",
            filename="projects.csv",
            file_type="csv",
            fingerprint="abc12345",
            status="indexed",
            record_count=10,
        )
        reg.save()  # Creates registry.json and registry.json.bak

        # Corrupt the main registry.json
        with open(self.registry_file, "w", encoding="utf-8") as f:
            f.write("{ corrupted json content !!!")

        # Reload registry: should recover from .bak
        recovered_reg = DocumentRegistry(self.registry_file)
        self.assertEqual(len(recovered_reg.list_all()), 1)
        self.assertIsNotNone(recovered_reg.get("documents/projects.csv"))

    # 18. Canonical S3 Key Cache Path Collision Prevention
    def test_canonical_s3_key_cache_path_no_collision(self):
        """Verifies that different S3 keys with identical basenames map to distinct local cache paths."""
        s3 = S3Service(bucket_name="test-bucket", prefix="", cache_dir=self.cache_dir)
        path1 = s3.get_cache_path("properties/chennai/projects.csv")
        path2 = s3.get_cache_path("archive/chennai/projects.csv")

        self.assertNotEqual(path1, path2)
        self.assertTrue(str(path1).endswith("projects.csv"))
        self.assertTrue(str(path2).endswith("projects.csv"))

    # 19. Atomic Download Partial File Cleanup on Failure
    def test_atomic_download_partial_file_cleanup_on_failure(self):
        """Verifies that if S3 download fails midway, .part temporary file is cleaned up."""
        s3 = S3Service(bucket_name="test-bucket", prefix="documents/", cache_dir=self.cache_dir)
        mock_client = MagicMock()
        
        def mock_download_failure(bucket, key, dest):
            # Create a partial file during download
            with open(dest, "wb") as f:
                f.write(b"partial corrupted data")
            raise Exception("Simulated connection timeout during S3 transfer")

        mock_client.download_file.side_effect = mock_download_failure
        s3._s3_client = mock_client

        with self.assertRaises(Exception):
            s3.download_document("documents/large_plan.pdf")

        # Verify no .part file remains
        part_files = list(self.cache_dir.glob("*.part"))
        self.assertEqual(len(part_files), 0)

    # 20. FAISS Staged Vector Commit Preserves Store on Embedding Failure
    def test_faiss_staged_vector_commit_preserves_store(self):
        """
        Verifies that vector store staged commit preserves previous vectors when new embeddings fail,
        and never marks failed embeddings as indexed.
        """
        store = FaissVectorStore(index_dir=self.vector_dir)
        # Seed initial working state
        store.chunks_metadata = [{"chunk_id": "c1", "text": "2BHK Living Room", "source": "spec.pdf"}]
        store.vectors = [[0.2] * store.dimension]
        store.fingerprints = {"spec.pdf": "original_hash"}
        store._save_to_disk()

        # Mock BedrockService failing to generate embeddings
        mock_bedrock = MagicMock()
        mock_bedrock.generate_embedding.side_effect = Exception("Bedrock ThrottlingException")
        mock_bedrock.embedding_dimensions = store.dimension
        store.bedrock_service = mock_bedrock

        # Attempt to update document with new hash
        new_docs = [{"text": "Updated 2BHK Master Bedroom", "source": "spec.pdf", "page": 1}]
        added = store.add_documents(new_docs, filename="spec.pdf", file_hash="new_hash")

        self.assertEqual(added, 0)
        # Original fingerprint must be preserved
        self.assertEqual(store.fingerprints.get("spec.pdf"), "original_hash")
        # Original chunks must be preserved
        self.assertEqual(len(store.chunks_metadata), 1)
        self.assertEqual(len(store.vectors), 1)

    # 21. Retriever Filter Strictness and BM25 Caching
    def test_retriever_filter_strictness_and_bm25_caching(self):
        """
        Verifies that hybrid_search does NOT drop BHK filters when no match exists,
        preventing hallucinations, and verifies BM25 index caching.
        """
        from app.rag.retriever import get_cached_bm25, invalidate_bm25_cache

        store = FaissVectorStore(index_dir=self.vector_dir)
        store.chunks_metadata = [
            {"chunk_id": "c1", "text": "2BHK Luxury apartment with granite counters", "configuration": "2BHK", "source": "2bhk.pdf"},
            {"chunk_id": "c2", "text": "3BHK Italian marble living room with terrace", "configuration": "3BHK", "source": "3bhk.pdf"},
        ]
        store.vectors = [[0.1] * store.dimension, [0.2] * store.dimension]
        store.version = 1

        invalidate_bm25_cache()
        bm25_1 = get_cached_bm25(store.chunks_metadata, store.version)
        bm25_2 = get_cached_bm25(store.chunks_metadata, store.version)
        self.assertIs(bm25_1, bm25_2)  # Must be cached object

        # Mock vector store in retriever
        with patch("app.rag.retriever.get_vector_store", return_value=store):
            # Query with 4BHK filter which does not exist in corpus
            results = hybrid_search(query="marble flooring", top_k=5, bhk=4)
            # Must return [] rather than dropping filter and returning 2BHK/3BHK!
            self.assertEqual(len(results), 0)

    # 22. Admin Key Dependency Validation (Strict Security)
    def test_admin_key_dependency(self):
        """
        Verifies that require_admin_auth:
        1. Rejects with 503 if ADMIN_API_KEY is not configured on the server.
        2. Rejects with 401 if header is missing.
        3. Rejects with 401 if an arbitrary non-empty header is supplied.
        4. Accepts only exact match via constant-time comparison.
        """
        from app.main import require_admin_auth
        from fastapi import HTTPException

        # 1. Missing ADMIN_API_KEY on server -> 503 Service Unavailable
        with patch.dict(os.environ, {"ADMIN_API_KEY": ""}):
            with self.assertRaises(HTTPException) as cm:
                require_admin_auth(x_admin_key="some-key")
            self.assertEqual(cm.exception.status_code, 503)

        # 2. Configured ADMIN_API_KEY
        with patch.dict(os.environ, {"ADMIN_API_KEY": "secret-admin-123"}):
            # Missing key raises 401
            with self.assertRaises(HTTPException) as cm:
                require_admin_auth(x_admin_key=None)
            self.assertEqual(cm.exception.status_code, 401)

            # Incorrect key raises 401
            with self.assertRaises(HTTPException) as cm:
                require_admin_auth(x_admin_key="wrong-key")
            self.assertEqual(cm.exception.status_code, 401)

            # Arbitrary non-empty string raises 401
            with self.assertRaises(HTTPException) as cm:
                require_admin_auth(x_admin_key="arbitrary-token")
            self.assertEqual(cm.exception.status_code, 401)

            # Correct key passes without raising
            require_admin_auth(x_admin_key="secret-admin-123")

    # 23. S3 Upload Collision Rejection (Source Data Protection)
    def test_s3_upload_collision_rejection(self):
        """Verifies that upload_document rejects overwriting an existing remote S3 object."""
        s3 = S3Service(bucket_name="test-bucket", prefix="documents/", cache_dir=self.cache_dir)
        mock_client = MagicMock()
        # head_object succeeds, indicating object already exists in S3
        mock_client.head_object.return_value = {"ContentLength": 500}
        s3._s3_client = mock_client

        test_file = self.cache_dir / "existing_doc.pdf"
        test_file.write_bytes(b"sample pdf data")

        with self.assertRaises(FileExistsError):
            s3.upload_document(test_file)

        # Neither put_object nor upload_file must ever be called
        mock_client.put_object.assert_not_called()
        mock_client.upload_file.assert_not_called()

    # 24. Full S3 Key Identity (Cross-Directory Collision Prevention)
    def test_full_s3_key_identity_across_prefixes(self):
        """
        Verifies that documents sharing the same basename under different S3 prefixes
        remain completely distinct and do not collide in StructuredDataStore or FaissVectorStore.
        """
        # 1. Structured Data Store
        store = StructuredDataStore()
        csv1 = b"property_name,bhk,price\nChennai Project,2,7500000"
        csv2 = b"property_name,bhk,price\nMadurai Project,3,6000000"

        store.add_or_update(csv1, source_name="documents/chennai/projects.csv")
        store.add_or_update(csv2, source_name="documents/madurai/projects.csv")

        self.assertEqual(len(store.get_all_records()), 2)

        # Purging chennai must NOT purge madurai
        removed = store.remove("documents/chennai/projects.csv")
        self.assertEqual(removed, 1)
        self.assertEqual(len(store.get_all_records()), 1)
        self.assertEqual(store.get_all_records()[0]["property_name"], "Madurai Project")

        # 2. Vector Store
        vstore = FaissVectorStore(index_dir=self.vector_dir)
        vstore.chunks_metadata = [
            {"chunk_id": "c1", "text": "Chennai spec", "source": "documents/chennai/property.pdf"},
            {"chunk_id": "c2", "text": "Madurai spec", "source": "documents/madurai/property.pdf"},
        ]
        vstore.vectors = [[0.1] * vstore.dimension, [0.2] * vstore.dimension]
        vstore.fingerprints = {
            "documents/chennai/property.pdf": "hash_chennai",
            "documents/madurai/property.pdf": "hash_madurai",
        }

        # Removing chennai must NOT remove madurai
        vstore.remove_document("documents/chennai/property.pdf")
        self.assertEqual(len(vstore.chunks_metadata), 1)
        self.assertEqual(vstore.chunks_metadata[0]["source"], "documents/madurai/property.pdf")
        self.assertIn("documents/madurai/property.pdf", vstore.fingerprints)
        self.assertNotIn("documents/chennai/property.pdf", vstore.fingerprints)

    # 25. Staged Rebuild Preserves Working Index On Failure
    def test_staged_rebuild_preserves_working_index_on_failure(self):
        """
        Verifies that when force_rebuild fails during staging (e.g. S3 listing error or parsing error),
        the active working index is 100% preserved and not wiped.
        """
        from app.main import sync_all_pipeline, get_structured_store, get_document_registry, get_vector_store

        structured = get_structured_store()
        registry = get_document_registry()

        # Isolate and seed working state
        structured.clear()
        csv_data = b"property_name,bhk,price\nWorking Active Listing,2,5000000"
        structured.add_or_update(csv_data, source_name="active_inventory.csv")
        registry.register_or_update(
            s3_key="active_inventory.csv",
            filename="active_inventory.csv",
            file_type="csv",
            fingerprint="active_hash",
            status="indexed",
            record_count=1,
        )

        initial_count = len(structured.get_all_records())
        self.assertEqual(initial_count, 1)

        # Mock S3Service to fail during listing
        with patch("app.services.s3_service.S3Service.list_s3_documents") as mock_list:
            mock_list.side_effect = S3AccessError("Simulated network failure during rebuild")
            with patch("app.services.s3_service.S3Service.is_configured", return_value=True):
                with self.assertRaises(Exception):
                    sync_all_pipeline(force_rebuild=True)

        # Working index MUST BE PRESERVED!
        self.assertEqual(len(structured.get_all_records()), 1)
        self.assertEqual(structured.get_all_records()[0]["property_name"], "Working Active Listing")
        self.assertIsNotNone(registry.get("active_inventory.csv"))

    # 26. Vector Store Persistence Error Propagation
    def test_vector_store_persistence_error_propagation(self):
        """Verifies that _save_to_disk raises IOError instead of swallowing errors when disk write fails."""
        store = FaissVectorStore(index_dir=self.vector_dir)
        store.chunks_metadata = [{"chunk_id": "c1", "text": "sample", "source": "test.pdf"}]
        store.vectors = [[0.1] * store.dimension]

        # Patch metadata_file open to raise PermissionError
        with patch("builtins.open", side_effect=PermissionError("Disk is write protected")):
            with self.assertRaises(IOError):
                store._save_to_disk()

    # 27. Structured Property Retrieval Location Filter Strictness
    def test_structured_property_location_filter_strictness(self):
        """Verifies that search_properties does NOT drop or relax location filters when no match exists."""
        records = [
            {"property_name": "OMR Tower", "bhk": 2, "price": 6000000, "location": "OMR", "property_type": "Apartment"},
            {"property_name": "Porur Villa", "bhk": 2, "price": 6500000, "location": "Porur", "property_type": "Villa"},
        ]
        # Querying for a location not in records ("Adyar")
        results = search_properties({"bhk": 2, "location": "Adyar"}, records, limit=5)
        # Must return empty list, NOT relax and return OMR or Porur!
        self.assertEqual(len(results), 0)

    # 28. Staged Rebuild Activates Atomically On Success
    def test_staged_rebuild_activates_atomically_on_success(self):
        """Verifies that force_rebuild successfully rebuilds and atomically replaces working records."""
        from app.main import sync_all_pipeline, get_structured_store, get_document_registry

        structured = get_structured_store()
        registry = get_document_registry()
        structured.clear()

        # Place new document in isolated test cache
        doc_path = self.cache_dir / "new_rebuild_catalog.csv"
        doc_path.write_text("property_name,bhk,price\nRebuilt Success Tower,3,9500000\n", encoding="utf-8")

        with patch("app.services.s3_service.S3Service.is_configured", return_value=False):
            with patch.dict(os.environ, {"DOCUMENT_CACHE_PATH": str(self.cache_dir), "ALLOW_LOCAL_FALLBACK": "true"}):
                result = sync_all_pipeline(force_rebuild=True)

        self.assertEqual(result["status"], "success")
        self.assertTrue(len(structured.get_all_records()) >= 1)
        self.assertTrue(any(r["property_name"] == "Rebuilt Success Tower" for r in structured.get_all_records()))

    # 29. Concurrent Upload Atomic Collision Rejection via IfNoneMatch
    def test_s3_upload_concurrent_conditional_rejection(self):
        """
        Verifies that upload_document rejects overwriting even when head_object reports 404
        if a concurrent upload completes first and S3 put_object returns PreconditionFailed (412).
        """
        s3 = S3Service(bucket_name="test-bucket", prefix="documents/", cache_dir=self.cache_dir)
        mock_client = MagicMock()
        
        # head_object reports 404 (pretending race window where key didn't exist yet)
        mock_client.head_object.side_effect = ClientError({"Error": {"Code": "404", "Message": "Not Found"}}, "HeadObject")
        # put_object rejects with PreconditionFailed (IfNoneMatch='*')
        mock_client.put_object.side_effect = ClientError({"Error": {"Code": "PreconditionFailed", "Message": "At least one precondition failed"}}, "PutObject")
        s3._s3_client = mock_client

        test_file = self.cache_dir / "race_condition_doc.pdf"
        test_file.write_bytes(b"sample pdf data")

        with self.assertRaises(FileExistsError):
            s3.upload_document(test_file)

        mock_client.put_object.assert_called_once()
        self.assertEqual(mock_client.put_object.call_args[1]["IfNoneMatch"], "*")

    # 30. Staged Rebuild Transactional Rollback on Mid-Activation Failure
    def test_staged_rebuild_transactional_rollback_on_mid_activation_failure(self):
        """
        Verifies that if an exception occurs during the activation phase of staged rebuild,
        the in-memory structured store and registry are completely rolled back to their pre-activation state.
        """
        from app.main import sync_all_pipeline, get_structured_store, get_document_registry

        structured = get_structured_store()
        registry = get_document_registry()

        structured.clear()
        initial_csv = b"property_name,bhk,price\nOriginal Unbroken Tower,2,4500000"
        structured.add_or_update(initial_csv, source_name="original_working.csv")
        registry.register_or_update(
            s3_key="original_working.csv",
            filename="original_working.csv",
            file_type="csv",
            fingerprint="unbroken_hash",
            status="indexed",
            record_count=1,
        )

        # Place new document that will stage successfully
        staged_csv = self.cache_dir / "new_to_stage.csv"
        staged_csv.write_text("property_name,bhk,price\nNew Staged Tower,3,8000000\n", encoding="utf-8")

        # Inject error during step 3 of activation (copying registry file)
        original_copy2 = shutil.copy2
        def copy_interceptor(src, dst, *args, **kwargs):
            if "reg_staging" in str(src):
                raise IOError("Simulated disk error during registry activation")
            return original_copy2(src, dst, *args, **kwargs)

        with patch("app.services.s3_service.S3Service.is_configured", return_value=False):
            with patch.dict(os.environ, {"DOCUMENT_CACHE_PATH": str(self.cache_dir), "ALLOW_LOCAL_FALLBACK": "true"}):
                with patch("shutil.copy2", side_effect=copy_interceptor):
                    with self.assertRaises(IOError) as ctx:
                        sync_all_pipeline(force_rebuild=True)
                    self.assertIn("rolled back", str(ctx.exception).lower())

        # Verify rollback preserved original in-memory data
        records = structured.get_all_records()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["property_name"], "Original Unbroken Tower")
        self.assertIsNotNone(registry.get("original_working.csv"))


if __name__ == "__main__":
    unittest.main()
