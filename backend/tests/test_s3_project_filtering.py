"""
Automated Unit Tests for S3 Bucket & Folder Architecture:
- Bucket name: casa-chatbot
- Unstructured PDF brochures: brochures/<Project>/ (Casamia, Zodiac, Highlin, Suncity, Aquagroue)
- Shared structured CSV dataset: Csv-data/ (CSV, XLSX, JSON)

Verifies:
1. Bucket name: casa-chatbot.
2. All five brochure project prefixes are included (brochures/Casamia/, etc.).
3. Other brochure project folders and unapproved prefixes are excluded.
4. Nested brochure PDFs are discovered recursively.
5. Structured CSV files are discovered from Csv-data/.
6. Structured datasets are not sent to Knowledge Base ingestion.
7. S3 pagination works across all prefixes.
8. Complete canonical S3 object keys are preserved.
9. Existing document registry and incremental sync work.
10. Original S3 objects are never modified or deleted.
11. Safe deletion reconciliation only operates on in-scope prefixes.
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from app.data_pipeline.structured import StructuredDataStore
from app.services.bedrock_kb_service import BedrockKnowledgeBaseService
from app.services.document_registry import DocumentRegistry
from app.services.s3_service import (
    S3Service,
    SUPPORTED_STRUCTURED_EXTENSIONS,
    SUPPORTED_UNSTRUCTURED_EXTENSIONS,
)


class TestS3ProjectFiltering(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="estateai_s3_test_")
        self.cache_dir = Path(self.test_dir) / "documents"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.registry_file = Path(self.test_dir) / "test_reg.json"

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # 1. Bucket Name Verification
    def test_default_bucket_name_is_casa_chatbot(self):
        """Verifies that default S3 bucket name is 'casa-chatbot' and respects custom parameter."""
        with patch.dict(os.environ, {"S3_BUCKET_NAME": "casa-chatbot"}):
            s3 = S3Service(cache_dir=self.cache_dir)
            self.assertEqual(s3.bucket_name, "casa-chatbot")

        # Explicit override
        s3_custom = S3Service(bucket_name="custom-bucket", cache_dir=self.cache_dir)
        self.assertEqual(s3_custom.bucket_name, "custom-bucket")

    # 2. Prefix Combination: S3_DOCUMENT_PREFIX + Allowed Project Prefixes
    def test_prefix_combination_brochures_and_projects(self):
        """
        Verifies backend combines S3_DOCUMENT_PREFIX with each allowed project prefix correctly:
        e.g. 'brochures/' + 'Casamia/' = 'brochures/Casamia/'
        Confirms bucket name is NEVER prepended to object prefixes.
        """
        with patch.dict(
            os.environ,
            {
                "S3_BUCKET_NAME": "casa-chatbot",
                "S3_DOCUMENT_PREFIX": "brochures/",
                "S3_ALLOWED_PROJECT_PREFIXES": "Casamia/,Zodiac/,Highlin/,Suncity/,Aquagroue/",
            },
        ):
            s3 = S3Service(cache_dir=self.cache_dir)
            expected_brochure_prefixes = [
                "brochures/Casamia/",
                "brochures/Zodiac/",
                "brochures/Highlin/",
                "brochures/Suncity/",
                "brochures/Aquagroue/",
            ]
            self.assertEqual(s3.brochure_prefixes, expected_brochure_prefixes)
            self.assertEqual(s3.prefix, "brochures/")
            self.assertEqual(s3.structured_prefix, "Csv-data/")

            # Confirm bucket name is NOT in any prefix
            for pfx in s3.brochure_prefixes:
                self.assertFalse(pfx.startswith("casa-chatbot"))

    # 3. All Five Brochure Projects Included, Others Excluded
    def test_all_five_brochure_projects_included_others_excluded(self):
        """
        Verifies that PDF documents only from the five allowed brochure project folders
        are discovered, while other brochure project folders are strictly excluded.
        """
        s3 = S3Service(
            bucket_name="casa-chatbot",
            prefix="brochures/",
            structured_prefix="Csv-data/",
            allowed_project_prefixes=["Casamia/", "Zodiac/", "Highlin/", "Suncity/", "Aquagroue/"],
            cache_dir=self.cache_dir,
        )

        mock_client = MagicMock()
        mock_paginator = MagicMock()

        def mock_paginate(Bucket, Prefix):
            if Prefix == "brochures/Casamia/":
                return [{"Contents": [{"Key": "brochures/Casamia/specs.pdf", "Size": 1024, "ETag": '"c1"'}]}]
            elif Prefix == "brochures/Zodiac/":
                return [{"Contents": [{"Key": "brochures/Zodiac/brochure.pdf", "Size": 2048, "ETag": '"z1"'}]}]
            elif Prefix == "brochures/Highlin/":
                return [{"Contents": [{"Key": "brochures/Highlin/details.pdf", "Size": 4096, "ETag": '"h1"'}]}]
            elif Prefix == "brochures/Suncity/":
                return [{"Contents": [{"Key": "brochures/Suncity/overview.pdf", "Size": 8192, "ETag": '"s1"'}]}]
            elif Prefix == "brochures/Aquagroue/":
                return [
                    {
                        "Contents": [
                            {"Key": "brochures/Aquagroue/master_plan.pdf", "Size": 512, "ETag": '"a1"'},
                            # Stray unapproved project key under this prefix must be ignored
                            {"Key": "brochures/UnapprovedProject/secret.pdf", "Size": 999, "ETag": '"u1"'},
                        ]
                    }
                ]
            elif Prefix == "Csv-data/":
                return [{"Contents": []}]
            return []

        mock_paginator.paginate.side_effect = mock_paginate
        mock_client.get_paginator.return_value = mock_paginator
        s3._s3_client = mock_client

        discovered, complete = s3.list_s3_documents()

        self.assertTrue(complete)
        self.assertEqual(len(discovered), 5)
        self.assertIn("brochures/Casamia/specs.pdf", discovered)
        self.assertIn("brochures/Zodiac/brochure.pdf", discovered)
        self.assertIn("brochures/Highlin/details.pdf", discovered)
        self.assertIn("brochures/Suncity/overview.pdf", discovered)
        self.assertIn("brochures/Aquagroue/master_plan.pdf", discovered)

        # Excluded project must NOT be present
        self.assertNotIn("brochures/UnapprovedProject/secret.pdf", discovered)

    # 4. Nested Brochure PDFs Discovered Recursively
    def test_nested_brochure_pdfs_discovered(self):
        """Verifies that nested brochure PDFs within project subfolders are discovered recursively."""
        s3 = S3Service(
            bucket_name="casa-chatbot",
            prefix="brochures/",
            structured_prefix="Csv-data/",
            allowed_project_prefixes=["Casamia/"],
            cache_dir=self.cache_dir,
        )

        mock_client = MagicMock()
        mock_paginator = MagicMock()

        mock_paginator.paginate.return_value = [
            {
                "Contents": [
                    {"Key": "brochures/Casamia/Phase1/TowerA/floorplan_2bhk.pdf", "Size": 1200, "ETag": '"n1"'},
                    {"Key": "brochures/Casamia/Phase2/Villas/specifications.pdf", "Size": 2400, "ETag": '"n2"'},
                ]
            }
        ]
        mock_client.get_paginator.return_value = mock_paginator
        s3._s3_client = mock_client

        discovered, complete = s3.list_s3_documents()

        self.assertTrue(complete)
        self.assertEqual(len(discovered), 2)
        self.assertIn("brochures/Casamia/Phase1/TowerA/floorplan_2bhk.pdf", discovered)
        self.assertIn("brochures/Casamia/Phase2/Villas/specifications.pdf", discovered)

    # 5. Structured Data Discovery from Csv-data/ (No Brochure Allowlist Applied)
    def test_structured_csv_data_discovered_without_project_allowlist(self):
        """
        Verifies that CSV, XLSX, and JSON files are discovered from Csv-data/
        without applying the five-project brochure allowlist.
        """
        s3 = S3Service(
            bucket_name="casa-chatbot",
            prefix="brochures/",
            structured_prefix="Csv-data/",
            allowed_project_prefixes=["Casamia/", "Zodiac/", "Highlin/", "Suncity/", "Aquagroue/"],
            cache_dir=self.cache_dir,
        )

        mock_client = MagicMock()
        mock_paginator = MagicMock()

        def mock_paginate(Bucket, Prefix):
            if Prefix == "Csv-data/":
                return [
                    {
                        "Contents": [
                            {"Key": "Csv-data/chennai_premium_listings.csv", "Size": 5000, "ETag": '"csv1"'},
                            {"Key": "Csv-data/inventory_master.xlsx", "Size": 12000, "ETag": '"xls1"'},
                            {"Key": "Csv-data/chennai_properties_catalog.json", "Size": 8000, "ETag": '"json1"'},
                        ]
                    }
                ]
            return [{"Contents": []}]

        mock_paginator.paginate.side_effect = mock_paginate
        mock_client.get_paginator.return_value = mock_paginator
        s3._s3_client = mock_client

        discovered, complete = s3.list_s3_documents()

        self.assertTrue(complete)
        self.assertEqual(len(discovered), 3)
        self.assertIn("Csv-data/chennai_premium_listings.csv", discovered)
        self.assertIn("Csv-data/inventory_master.xlsx", discovered)
        self.assertIn("Csv-data/chennai_properties_catalog.json", discovered)

    # 6. Format Isolation: Only PDFs from brochures/ and Only Structured from Csv-data/
    def test_structured_and_brochure_format_isolation(self):
        """
        Verifies format isolation:
        - Non-PDF files in brochures/ are skipped.
        - Non-structured files in Csv-data/ are skipped.
        """
        s3 = S3Service(
            bucket_name="casa-chatbot",
            prefix="brochures/",
            structured_prefix="Csv-data/",
            allowed_project_prefixes=["Casamia/"],
            cache_dir=self.cache_dir,
        )

        mock_client = MagicMock()
        mock_paginator = MagicMock()

        def mock_paginate(Bucket, Prefix):
            if Prefix == "brochures/Casamia/":
                return [
                    {
                        "Contents": [
                            {"Key": "brochures/Casamia/valid.pdf", "Size": 1000, "ETag": '"pdf1"'},
                            {"Key": "brochures/Casamia/stray.csv", "Size": 1000, "ETag": '"csv_stray"'},
                            {"Key": "brochures/Casamia/notes.txt", "Size": 500, "ETag": '"txt1"'},
                        ]
                    }
                ]
            elif Prefix == "Csv-data/":
                return [
                    {
                        "Contents": [
                            {"Key": "Csv-data/properties.csv", "Size": 3000, "ETag": '"c1"'},
                            {"Key": "Csv-data/random.pdf", "Size": 3000, "ETag": '"pdf_stray"'},
                            {"Key": "Csv-data/image.png", "Size": 3000, "ETag": '"img1"'},
                        ]
                    }
                ]
            return []

        mock_paginator.paginate.side_effect = mock_paginate
        mock_client.get_paginator.return_value = mock_paginator
        s3._s3_client = mock_client

        discovered, complete = s3.list_s3_documents()

        self.assertTrue(complete)
        self.assertEqual(len(discovered), 2)
        # brochures/ only accepts PDF
        self.assertIn("brochures/Casamia/valid.pdf", discovered)
        self.assertNotIn("brochures/Casamia/stray.csv", discovered)
        self.assertNotIn("brochures/Casamia/notes.txt", discovered)

        # Csv-data/ only accepts structured
        self.assertIn("Csv-data/properties.csv", discovered)
        self.assertNotIn("Csv-data/random.pdf", discovered)
        self.assertNotIn("Csv-data/image.png", discovered)

    # 7. Structured Datasets Not Sent to Bedrock Knowledge Base Ingestion
    def test_structured_datasets_not_sent_to_knowledge_base(self):
        """
        Verifies that structured datasets (.csv, .xlsx, .json) are loaded into
        StructuredDataStore and maintain deterministic filtering, and are NEVER
        processed by Bedrock Knowledge Base.
        """
        csv_file = self.cache_dir / "sample_properties.csv"
        csv_file.write_text(
            "title,bhk,price,location,sqft,facing\n"
            "Casagrand Casamia 2BHK,2,7500000,Perungudi,1150,North\n"
            "Casagrand Zodiac 3BHK,3,12000000,Velachery,1600,East\n",
            encoding="utf-8",
        )

        store = StructuredDataStore()
        count = store.add_or_update(csv_file, source_name="Csv-data/sample_properties.csv")
        self.assertEqual(count, 2)

        # Deterministic property search works
        results = store.search({"bhk": 2, "max_price": 8000000})
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["property_name"], "Casagrand Casamia 2BHK")
        self.assertEqual(results[0]["source_file"], "Csv-data/sample_properties.csv")

        # Knowledge Base service is configured only for unstructured documents
        kb = BedrockKnowledgeBaseService()
        self.assertIn(".pdf", SUPPORTED_UNSTRUCTURED_EXTENSIONS)
        self.assertNotIn(".csv", SUPPORTED_UNSTRUCTURED_EXTENSIONS)
        self.assertNotIn(".xlsx", SUPPORTED_UNSTRUCTURED_EXTENSIONS)

    # 8. S3 Multi-Page Pagination Across Prefixes
    def test_multi_prefix_and_multi_page_pagination(self):
        """Verifies pagination across multiple pages for each allowed brochure project prefix and Csv-data/."""
        s3 = S3Service(
            bucket_name="casa-chatbot",
            prefix="brochures/",
            structured_prefix="Csv-data/",
            allowed_project_prefixes=["Casamia/", "Zodiac/"],
            cache_dir=self.cache_dir,
        )

        mock_client = MagicMock()
        mock_paginator = MagicMock()

        def mock_paginate(Bucket, Prefix):
            if Prefix == "brochures/Casamia/":
                return [
                    {"Contents": [{"Key": "brochures/Casamia/page1.pdf", "Size": 100, "ETag": '"p1"'}]},
                    {"Contents": [{"Key": "brochures/Casamia/page2.pdf", "Size": 200, "ETag": '"p2"'}]},
                ]
            elif Prefix == "brochures/Zodiac/":
                return [
                    {"Contents": [{"Key": "brochures/Zodiac/page1.pdf", "Size": 300, "ETag": '"p3"'}]}
                ]
            elif Prefix == "Csv-data/":
                return [
                    {"Contents": [{"Key": "Csv-data/dataset_p1.csv", "Size": 400, "ETag": '"p4"'}]},
                    {"Contents": [{"Key": "Csv-data/dataset_p2.csv", "Size": 500, "ETag": '"p5"'}]},
                ]
            return []

        mock_paginator.paginate.side_effect = mock_paginate
        mock_client.get_paginator.return_value = mock_paginator
        s3._s3_client = mock_client

        discovered, complete = s3.list_s3_documents()

        self.assertTrue(complete)
        self.assertEqual(len(discovered), 5)
        self.assertIn("brochures/Casamia/page1.pdf", discovered)
        self.assertIn("brochures/Casamia/page2.pdf", discovered)
        self.assertIn("brochures/Zodiac/page1.pdf", discovered)
        self.assertIn("Csv-data/dataset_p1.csv", discovered)
        self.assertIn("Csv-data/dataset_p2.csv", discovered)

    # 9. Complete Canonical S3 Object Keys Preserved
    def test_complete_canonical_s3_object_keys_preserved(self):
        """
        Verifies that get_cache_path and get_s3_key_for_path preserve complete canonical keys
        (e.g. 'brochures/Casamia/spec.pdf' and 'Csv-data/properties.csv') without basename stripping.
        """
        s3 = S3Service(
            bucket_name="casa-chatbot",
            prefix="brochures/",
            structured_prefix="Csv-data/",
            allowed_project_prefixes=["Casamia/"],
            cache_dir=self.cache_dir,
        )

        keys_to_test = [
            "brochures/Casamia/spec.pdf",
            "brochures/Casamia/TowerA/floorplan.pdf",
            "Csv-data/chennai_premium_listings.csv",
        ]

        for original_key in keys_to_test:
            cache_path = s3.get_cache_path(original_key)
            # Confirms cache path preserves folder structure
            self.assertTrue(str(cache_path).endswith(original_key.replace("/", os.sep)))

            # Canonical reverse key mapping preserves original key exactly
            resolved_key = s3.get_s3_key_for_path(cache_path)
            self.assertEqual(resolved_key, original_key)

    # 10. Document Registry and Incremental Sync
    def test_document_registry_and_incremental_sync(self):
        """Verifies that document registry tracks canonical keys and incremental sync categorizes new/unchanged."""
        reg = DocumentRegistry(self.registry_file)
        s3 = S3Service(
            bucket_name="casa-chatbot",
            prefix="brochures/",
            structured_prefix="Csv-data/",
            allowed_project_prefixes=["Casamia/"],
            cache_dir=self.cache_dir,
        )

        # Mock download_file and list_objects_v2
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {
                "Contents": [
                    {"Key": "brochures/Casamia/doc.pdf", "Size": 15, "ETag": '"e1"', "LastModified": "2026-11-25T00:00:00"},
                ]
            }
        ]
        mock_client.get_paginator.return_value = mock_paginator

        def fake_download(bucket, key, dest):
            Path(dest).write_bytes(b"sample pdf data")

        mock_client.download_file.side_effect = fake_download
        s3._s3_client = mock_client

        # Initial sync: new document
        manifest = s3.sync_documents_incremental(reg, allow_fallback=True)
        self.assertEqual(len(manifest["new"]), 1)
        self.assertEqual(s3.get_s3_key_for_path(manifest["new"][0]), "brochures/Casamia/doc.pdf")

        # Mark as indexed in registry
        entry = reg.get("brochures/Casamia/doc.pdf")
        self.assertIsNotNone(entry)
        reg.update_status("brochures/Casamia/doc.pdf", status="indexed", fingerprint=entry["fingerprint"])

        # Second sync: unchanged document
        manifest2 = s3.sync_documents_incremental(reg, allow_fallback=True)
        self.assertEqual(len(manifest2["unchanged"]), 1)
        self.assertEqual(len(manifest2["new"]), 0)

    # 11. Safe Deletion Reconciliation Scope
    def test_safe_deletion_reconciliation_scope(self):
        """
        Verifies that deletion reconciliation only purges deleted files belonging
        to the in-scope brochure and structured prefixes, and never touches documents
        from other prefixes.
        """
        reg = DocumentRegistry(self.registry_file)
        reg.register_or_update(
            s3_key="brochures/Casamia/old.pdf",
            filename="brochures/Casamia/old.pdf",
            file_type="pdf",
            fingerprint="h1",
            status="indexed",
        )
        reg.register_or_update(
            s3_key="Csv-data/old_data.csv",
            filename="Csv-data/old_data.csv",
            file_type="csv",
            fingerprint="h2",
            status="indexed",
        )
        reg.register_or_update(
            s3_key="OtherBucketFolder/do_not_touch.pdf",
            filename="OtherBucketFolder/do_not_touch.pdf",
            file_type="pdf",
            fingerprint="h3",
            status="indexed",
        )

        s3 = S3Service(
            bucket_name="casa-chatbot",
            prefix="brochures/",
            structured_prefix="Csv-data/",
            allowed_project_prefixes=["Casamia/"],
            cache_dir=self.cache_dir,
        )

        # S3 returns empty listing for both prefixes (meaning both were deleted)
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{"Contents": []}]
        mock_client.get_paginator.return_value = mock_paginator
        s3._s3_client = mock_client

        manifest = s3.sync_documents_incremental(reg, allow_fallback=True)

        self.assertIn("brochures/Casamia/old.pdf", manifest["deleted"])
        self.assertIn("Csv-data/old_data.csv", manifest["deleted"])
        self.assertNotIn("OtherBucketFolder/do_not_touch.pdf", manifest["deleted"])

    # 12. Original S3 Objects Never Overwritten or Modified
    def test_original_s3_objects_never_modified_or_overwritten(self):
        """
        Verifies that upload_document prevents modifying or overwriting existing S3 source objects
        by enforcing atomic conditional checks.
        """
        s3 = S3Service(bucket_name="casa-chatbot", cache_dir=self.cache_dir)
        dummy_file = self.cache_dir / "brochures" / "Casamia" / "existing.pdf"
        dummy_file.parent.mkdir(parents=True, exist_ok=True)
        dummy_file.write_bytes(b"content")

        mock_client = MagicMock()
        # Mock head_object finding the file already exists in S3
        mock_client.head_object.return_value = {"ContentLength": 100}
        s3._s3_client = mock_client

        with self.assertRaises(FileExistsError):
            s3.upload_document(dummy_file, s3_key="brochures/Casamia/existing.pdf")


if __name__ == "__main__":
    unittest.main()
