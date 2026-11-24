"""
S3 Service for EstateAI.
Responsible for downloading structured and unstructured documents from Amazon S3,
caching them locally on persistent EC2 storage, and managing document synchronization.
Uses standard EC2 IAM instance role credentials by default.
"""

import hashlib
import logging
import os
from pathlib import Path
from typing import Any, Optional, Union

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from app.config import env

logger = logging.getLogger("estateai.s3_service")


class S3Service:
    def __init__(
        self,
        bucket_name: Optional[str] = None,
        prefix: Optional[str] = None,
        cache_dir: Optional[Union[str, Path]] = None,
        region_name: Optional[str] = None,
    ):
        self.bucket_name = bucket_name or env("S3_BUCKET_NAME", "")
        self.prefix = prefix or env("S3_DOCUMENT_PREFIX", "documents/")
        self.region_name = region_name or env("AWS_REGION", "ap-south-1")
        
        # Local document cache directory on EC2 storage
        default_cache = Path(__file__).resolve().parent.parent.parent / "data" / "documents"
        self.cache_dir = Path(cache_dir or env("DOCUMENT_CACHE_PATH", str(default_cache)))
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self._s3_client = None

    def _get_client(self):
        """Initializes boto3 S3 client using standard credential provider chain (EC2 IAM role)."""
        if self._s3_client is not None:
            return self._s3_client

        session_kwargs = {"region_name": self.region_name}
        # Only use explicit profile if configured and not placeholder
        profile = env("AWS_PROFILE", "")
        if profile and profile not in ("your-aws-profile-name", "realestate-demo"):
            session_kwargs["profile_name"] = profile

        session = boto3.Session(**session_kwargs)
        self._s3_client = session.client("s3")
        return self._s3_client

    def is_configured(self) -> bool:
        """Returns True if bucket name is set and not placeholder."""
        b = self.bucket_name.strip()
        return bool(b and b not in ("your-property-bucket", "YOUR-ATHENA-RESULTS-BUCKET/"))

    def compute_file_hash(self, file_path: Path) -> str:
        """Computes SHA-256 fingerprint of a local file."""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def sync_documents(self) -> list[Path]:
        """
        Synchronizes documents from S3 bucket into local EC2 cache.
        Returns list of downloaded or existing cached file paths.
        Falls back to local cache or repository documents if S3 is unavailable.
        """
        downloaded_files: list[Path] = []

        if not self.is_configured():
            logger.info("S3_BUCKET_NAME not configured or placeholder. Using local document directory: %s", self.cache_dir)
            return self.get_cached_documents()

        try:
            client = self._get_client()
            logger.info("Listing objects in S3 bucket '%s' with prefix '%s'", self.bucket_name, self.prefix)
            paginator = client.get_paginator("list_objects_v2")
            pages = paginator.paginate(Bucket=self.bucket_name, Prefix=self.prefix)

            for page in pages:
                contents = page.get("Contents", [])
                for obj in contents:
                    key = obj.get("Key", "")
                    if not key or key.endswith("/"):
                        continue  # Skip folders

                    filename = Path(key).name
                    # Filter supported extensions
                    ext = Path(filename).suffix.lower()
                    if ext not in (".csv", ".xlsx", ".xls", ".json", ".pdf"):
                        continue

                    local_dest = self.cache_dir / filename
                    s3_etag = obj.get("ETag", "").strip('"')

                    # Download if file does not exist locally or size differs
                    s3_size = obj.get("Size", 0)
                    needs_download = True
                    if local_dest.exists() and local_dest.stat().st_size == s3_size:
                        needs_download = False

                    if needs_download:
                        logger.info("Downloading s3://%s/%s -> %s", self.bucket_name, key, local_dest)
                        client.download_file(self.bucket_name, key, str(local_dest))

                    downloaded_files.append(local_dest)

        except (ClientError, NoCredentialsError, Exception) as exc:
            logger.warning(
                "Unable to sync from S3 bucket '%s' (%s). Falling back to existing local documents.",
                self.bucket_name,
                exc,
            )
            return self.get_cached_documents()

        return downloaded_files if downloaded_files else self.get_cached_documents()

    def get_cached_documents(self) -> list[Path]:
        """Returns all supported document files present in the cache directory or pdf/ directory."""
        candidates = []
        # Check cache_dir
        if self.cache_dir.exists():
            for f in self.cache_dir.iterdir():
                if f.is_file() and f.suffix.lower() in (".csv", ".xlsx", ".xls", ".json", ".pdf"):
                    candidates.append(f)

        # Check repository pdf/ directory for initial fallback
        repo_pdf_dir = Path(__file__).resolve().parent.parent.parent.parent / "pdf"
        if repo_pdf_dir.exists() and repo_pdf_dir.is_dir():
            for f in repo_pdf_dir.iterdir():
                if f.is_file() and f.suffix.lower() == ".pdf" and f not in candidates:
                    candidates.append(f)

        return sorted(candidates, key=lambda p: p.name)

    def upload_document(self, local_path: Path, s3_key: Optional[str] = None) -> bool:
        """Uploads a local document to the S3 bucket if configured."""
        if not self.is_configured():
            logger.warning("Cannot upload to S3: bucket not configured.")
            return False

        target_key = s3_key or f"{self.prefix.rstrip('/')}/{local_path.name}"
        try:
            client = self._get_client()
            client.upload_file(str(local_path), self.bucket_name, target_key)
            logger.info("Successfully uploaded %s to s3://%s/%s", local_path, self.bucket_name, target_key)
            return True
        except Exception as e:
            logger.error("Failed to upload %s to S3: %s", local_path, e)
            return False

