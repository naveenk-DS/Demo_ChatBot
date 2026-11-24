"""
Dynamic S3 Service for EstateAI.
Responsible for downloading structured (CSV, XLSX, JSON) and unstructured (PDF)
documents from Amazon S3, discovering files dynamically via list_objects_v2 pagination,
caching them on persistent EC2 storage, and managing incremental synchronization.

Supports:
- Unlimited documents (no hardcoded counts or limits)
- S3 pagination via ContinuationToken
- Safe ignoring of unsupported file formats
- Fingerprint-based change detection (SHA-256)
- S3 deletion detection
- Seamless offline/local fallback
"""

import hashlib
import logging
import os
from pathlib import Path
from typing import Any, Optional, Union

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from app.config import env
from app.services.document_registry import DocumentRegistry, get_document_registry

logger = logging.getLogger("estateai.s3_service")

SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".json", ".pdf"}


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
        profile = env("AWS_PROFILE", "")
        if profile and profile not in ("your-aws-profile-name", "realestate-demo"):
            session_kwargs["profile_name"] = profile

        session = boto3.Session(**session_kwargs)
        self._s3_client = session.client("s3")
        return self._s3_client

    def is_configured(self) -> bool:
        """Returns True if bucket name is set and not a placeholder."""
        b = self.bucket_name.strip()
        return bool(b and b not in ("your-property-bucket", "YOUR-ATHENA-RESULTS-BUCKET/", "none"))

    @staticmethod
    def compute_file_hash(file_path: Union[str, Path]) -> str:
        """Computes SHA-256 fingerprint of a local file."""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def list_s3_documents(self) -> dict[str, dict[str, Any]]:
        """
        Lists all valid documents in S3 prefix using list_objects_v2 pagination.
        Filters out directories and unsupported file types safely.
        Returns a dict mapping s3_key -> metadata dict.
        """
        if not self.is_configured():
            return {}

        client = self._get_client()
        paginator = client.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=self.bucket_name, Prefix=self.prefix)

        discovered: dict[str, dict[str, Any]] = {}

        for page in pages:
            contents = page.get("Contents", [])
            for obj in contents:
                key = obj.get("Key", "")
                if not key or key.endswith("/"):
                    continue

                filename = Path(key).name
                ext = Path(filename).suffix.lower()

                # Safe format filter
                if ext not in SUPPORTED_EXTENSIONS:
                    logger.debug("Skipping unsupported S3 object: %s (ext: %s)", key, ext)
                    continue

                discovered[key] = {
                    "s3_key": key,
                    "filename": filename,
                    "file_type": ext.lstrip("."),
                    "size_bytes": obj.get("Size", 0),
                    "last_modified": obj.get("LastModified", "").isoformat() if hasattr(obj.get("LastModified", ""), "isoformat") else str(obj.get("LastModified", "")),
                    "etag": obj.get("ETag", "").strip('"'),
                }

        logger.info("Discovered %d supported document(s) in s3://%s/%s across all pages", len(discovered), self.bucket_name, self.prefix)
        return discovered

    def sync_documents_incremental(
        self,
        registry: Optional[DocumentRegistry] = None,
    ) -> dict[str, list[Any]]:
        """
        Incrementally synchronizes S3 documents with local cache and DocumentRegistry.
        Detects:
        - new documents
        - modified documents (content/fingerprint change)
        - deleted documents (removed from S3)
        - unchanged documents

        Returns:
            {
                "new": [Path],
                "modified": [Path],
                "deleted": [str (s3_key or filename)],
                "unchanged": [Path],
                "failed": [str]
            }
        """
        reg = registry or get_document_registry()
        result: dict[str, list[Any]] = {
            "new": [],
            "modified": [],
            "deleted": [],
            "unchanged": [],
            "failed": [],
        }

        # Offline / Local fallback mode
        if not self.is_configured():
            logger.info("S3 bucket not configured. Running incremental sync on local cache directory: %s", self.cache_dir)
            return self._sync_local_cache(reg)

        try:
            s3_docs = self.list_s3_documents()
            client = self._get_client()

            # 1. Detect deleted S3 files (previously active in registry, but no longer in S3)
            active_entries = reg.list_active()
            for entry in active_entries:
                key = entry.get("s3_key")
                # Only check keys that originated from S3 prefix
                if key and key.startswith(self.prefix) and key not in s3_docs:
                    logger.info("Detected deleted document from S3: %s", key)
                    result["deleted"].append(key)

            # 2. Process S3 documents (new, modified, unchanged)
            for key, meta in s3_docs.items():
                filename = meta["filename"]
                local_path = self.cache_dir / filename
                s3_size = meta["size_bytes"]
                s3_last_mod = meta["last_modified"]
                file_type = meta["file_type"]

                reg_entry = reg.get(key)
                needs_download = True

                if local_path.exists():
                    local_size = local_path.stat().st_size
                    # Check if local file exists and matches size
                    if local_size == s3_size:
                        local_hash = self.compute_file_hash(local_path)
                        if reg_entry and reg_entry.get("fingerprint") == local_hash and reg_entry.get("status") == "indexed":
                            needs_download = False
                            result["unchanged"].append(local_path)
                            continue

                if needs_download:
                    try:
                        logger.info("Downloading s3://%s/%s -> %s", self.bucket_name, key, local_path)
                        client.download_file(self.bucket_name, key, str(local_path))
                        new_hash = self.compute_file_hash(local_path)

                        if not reg_entry or reg_entry.get("status") == "deleted":
                            reg.register_or_update(
                                s3_key=key,
                                filename=filename,
                                file_type=file_type,
                                fingerprint=new_hash,
                                size_bytes=s3_size,
                                last_modified=s3_last_mod,
                                status="pending",
                            )
                            result["new"].append(local_path)
                        else:
                            # Modified document
                            reg.register_or_update(
                                s3_key=key,
                                filename=filename,
                                file_type=file_type,
                                fingerprint=new_hash,
                                size_bytes=s3_size,
                                last_modified=s3_last_mod,
                                status="pending",
                            )
                            result["modified"].append(local_path)

                    except Exception as dl_err:
                        logger.error("Failed to download %s: %s", key, dl_err)
                        reg.register_or_update(
                            s3_key=key,
                            filename=filename,
                            file_type=file_type,
                            fingerprint="",
                            size_bytes=s3_size,
                            last_modified=s3_last_mod,
                            status="failed",
                            error_message=str(dl_err),
                        )
                        result["failed"].append(key)

        except (ClientError, NoCredentialsError, Exception) as exc:
            logger.warning("Error communicating with S3 (%s). Falling back to local cache.", exc)
            return self._sync_local_cache(reg)

        return result

    def _sync_local_cache(self, reg: DocumentRegistry) -> dict[str, list[Any]]:
        """Syncs local cache when running without S3 connection."""
        result: dict[str, list[Any]] = {
            "new": [],
            "modified": [],
            "deleted": [],
            "unchanged": [],
            "failed": [],
        }

        # Gather local files from cache_dir and repo pdf/ fallback
        local_files: dict[str, Path] = {}
        if self.cache_dir.exists():
            for f in self.cache_dir.iterdir():
                if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS:
                    local_files[f.name] = f

        repo_pdf = Path(__file__).resolve().parent.parent.parent.parent / "pdf"
        if repo_pdf.exists() and repo_pdf.is_dir():
            for f in repo_pdf.iterdir():
                if f.is_file() and f.suffix.lower() == ".pdf" and f.name not in local_files:
                    local_files[f.name] = f

        # Detect deleted
        active_entries = reg.list_active()
        for entry in active_entries:
            fname = entry.get("filename", "")
            if fname and fname not in local_files:
                logger.info("Detected locally deleted document: %s", fname)
                result["deleted"].append(fname)

        # Detect new / modified / unchanged
        for fname, path in local_files.items():
            try:
                f_hash = self.compute_file_hash(path)
                reg_entry = reg.get(fname)
                f_type = path.suffix.lower().lstrip(".")
                f_size = path.stat().st_size

                if not reg_entry or reg_entry.get("status") == "deleted":
                    reg.register_or_update(
                        s3_key=f"local://{fname}",
                        filename=fname,
                        file_type=f_type,
                        fingerprint=f_hash,
                        size_bytes=f_size,
                        status="pending",
                    )
                    result["new"].append(path)
                elif reg_entry.get("fingerprint") != f_hash:
                    reg.register_or_update(
                        s3_key=reg_entry.get("s3_key", f"local://{fname}"),
                        filename=fname,
                        file_type=f_type,
                        fingerprint=f_hash,
                        size_bytes=f_size,
                        status="pending",
                    )
                    result["modified"].append(path)
                elif reg_entry.get("status") == "indexed":
                    result["unchanged"].append(path)
                else:
                    result["new"].append(path)
            except Exception as e:
                logger.error("Error inspecting local file %s: %s", fname, e)
                result["failed"].append(fname)

        return result

    def sync_documents(self) -> list[Path]:
        """Backward-compatible method returning all active supported document paths."""
        sync_res = self.sync_documents_incremental()
        all_paths = set(sync_res["unchanged"] + sync_res["new"] + sync_res["modified"])
        return sorted(list(all_paths), key=lambda p: p.name)

    def get_cached_documents(self) -> list[Path]:
        """Returns all supported document files present in cache directory or fallback."""
        candidates = []
        if self.cache_dir.exists():
            for f in self.cache_dir.iterdir():
                if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS:
                    candidates.append(f)

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
