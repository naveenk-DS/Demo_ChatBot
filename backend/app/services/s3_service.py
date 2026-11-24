"""
Dynamic S3 Service for EstateAI.
Responsible for downloading structured (CSV, XLS, XLSX, JSON) and unstructured (PDF)
documents from Amazon S3, discovering files dynamically via list_objects_v2 pagination,
caching them on persistent EC2 storage, and managing incremental synchronization.

Production Safety Rules:
1. S3 AccessDenied or credential errors must NEVER silently fall back to stale local data in production.
2. Local fallback is permitted ONLY when explicitly enabled via ALLOW_LOCAL_FALLBACK=true or in development mode.
3. Distinguishes S3 access failures from legitimate empty buckets.
4. Deletion reconciliation runs ONLY after a complete, successful S3 pagination cycle.
5. If pagination fails midway, deletion reconciliation is aborted to prevent data loss.
"""

import hashlib
import logging
import os
from pathlib import Path
from typing import Any, Optional, Union

import boto3
from botocore.exceptions import ClientError, EndpointConnectionError, NoCredentialsError

from app.config import env, bool_env
from app.services.document_registry import DocumentRegistry, get_document_registry

logger = logging.getLogger("estateai.s3_service")

SUPPORTED_STRUCTURED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".json"}
SUPPORTED_UNSTRUCTURED_EXTENSIONS = {".pdf"}
SUPPORTED_EXTENSIONS = SUPPORTED_STRUCTURED_EXTENSIONS | SUPPORTED_UNSTRUCTURED_EXTENSIONS


class S3AccessError(Exception):
    """Raised when S3 access fails due to permissions (AccessDenied), credentials, or network errors in production."""
    pass


class S3PaginationError(Exception):
    """Raised when S3 pagination cycle is interrupted midway, preventing safe deletion reconciliation."""
    pass


class S3Service:
    def __init__(
        self,
        bucket_name: Optional[str] = None,
        prefix: Optional[str] = None,
        cache_dir: Optional[Union[str, Path]] = None,
        region_name: Optional[str] = None,
    ):
        self.bucket_name = bucket_name or env("S3_BUCKET_NAME", "cg-website-chatbot-data")
        # Configurable S3 prefix: default to empty string to allow scanning all project folders in cg-website-chatbot-data
        if prefix is not None:
            self.prefix = prefix
        else:
            self.prefix = env("S3_DOCUMENT_PREFIX", "")
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

    is_s3_configured = is_configured

    def is_local_fallback_permitted(self) -> bool:
        """Determines if fallback to local cached documents is allowed."""
        if bool_env("ALLOW_LOCAL_FALLBACK", False):
            return True
        app_env = env("APP_ENV", "production").lower().strip()
        return app_env in ("development", "test", "local")

    @staticmethod
    def compute_file_hash(file_path: Union[str, Path]) -> str:
        """Computes SHA-256 fingerprint of a local file."""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def list_s3_documents(self) -> tuple[dict[str, dict[str, Any]], bool]:
        """
        Lists all valid documents in S3 prefix using list_objects_v2 pagination.
        Returns a tuple: (discovered_dict, is_complete).
        
        Raises:
            S3AccessError: If S3 returns AccessDenied, credentials error, or connection failure.
            S3PaginationError: If pagination fails midway after yielding partial pages.
        """
        if not self.is_configured():
            return {}, True

        discovered: dict[str, dict[str, Any]] = {}
        pages_processed = 0

        try:
            client = self._get_client()
            paginator = client.get_paginator("list_objects_v2")
            pages = paginator.paginate(Bucket=self.bucket_name, Prefix=self.prefix)
            for page in pages:
                pages_processed += 1
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

        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            msg = exc.response.get("Error", {}).get("Message", str(exc))
            if pages_processed > 0:
                raise S3PaginationError(f"S3 pagination interrupted midway on page {pages_processed + 1}: {code} - {msg}") from exc
            raise S3AccessError(f"S3 access denied or failed for bucket '{self.bucket_name}': {code} - {msg}") from exc
        except (NoCredentialsError, EndpointConnectionError) as exc:
            if pages_processed > 0:
                raise S3PaginationError(f"S3 connection dropped during pagination on page {pages_processed + 1}: {exc}") from exc
            raise S3AccessError(f"S3 credentials or network unavailable: {exc}") from exc
        except Exception as exc:
            if pages_processed > 0:
                raise S3PaginationError(f"Unexpected error during S3 pagination: {exc}") from exc
            raise S3AccessError(f"Failed to access S3: {exc}") from exc

        logger.info("Discovered %d supported document(s) in s3://%s/%s across %d page(s)", len(discovered), self.bucket_name, self.prefix, pages_processed)
        return discovered, True

    list_remote_documents = list_s3_documents

    def get_cache_path(self, s3_key: str) -> Path:
        """
        Resolves a deterministic, collision-free local cache Path for an S3 object key.
        Preserves relative folder structure under cache_dir to prevent collisions between
        files with identical basenames in different S3 prefixes (e.g. properties/chennai/projects.csv
        vs archive/chennai/projects.csv).
        """
        clean_key = s3_key.lstrip("/")
        # If key starts with prefix, mirror path relative to prefix
        rel_key = clean_key
        norm_prefix = self.prefix.strip("/")
        if norm_prefix and rel_key.startswith(norm_prefix):
            rel_key = rel_key[len(norm_prefix):].lstrip("/")
        
        dest = self.cache_dir / rel_key
        dest.parent.mkdir(parents=True, exist_ok=True)
        return dest

    def sync_documents_incremental(
        self,
        registry: Optional[DocumentRegistry] = None,
        allow_fallback: Optional[bool] = None,
    ) -> dict[str, list[Any]]:
        """
        Incrementally synchronizes S3 documents with local cache and DocumentRegistry.
        Detects:
        - new documents
        - modified documents (content/fingerprint change)
        - deleted documents (removed from S3) - ONLY after 100% complete pagination
        - unchanged documents

        Returns:
            {
                "new": [Path],
                "modified": [Path],
                "deleted": [str (s3_key or filename)],
                "unchanged": [Path],
                "failed": [str]
            }
        
        Raises:
            S3AccessError: If S3 access fails in production and local fallback is not permitted.
        """
        reg = registry or get_document_registry()
        result: dict[str, list[Any]] = {
            "new": [],
            "modified": [],
            "deleted": [],
            "unchanged": [],
            "failed": [],
        }

        fallback_allowed = allow_fallback if allow_fallback is not None else self.is_local_fallback_permitted()

        # Handle unconfigured bucket
        if not self.is_configured():
            if fallback_allowed:
                logger.info("S3 bucket not configured. Running incremental sync on local cache: %s", self.cache_dir)
                return self._sync_local_cache(reg)
            raise S3AccessError("S3_BUCKET_NAME is not configured and local fallback is disabled in production.")

        # Attempt complete S3 discovery
        try:
            s3_docs, listing_complete = self.list_s3_documents()
        except (S3AccessError, S3PaginationError) as s3_err:
            if fallback_allowed:
                logger.warning("S3 listing failed (%s). Local fallback explicitly permitted by configuration.", s3_err)
                return self._sync_local_cache(reg)
            logger.error("CRITICAL S3 ACCESS FAILURE: %s. Local fallback disallowed in production.", s3_err)
            raise

        client = self._get_client()

        # 1. SAFE DELETION RECONCILIATION
        # CRITICAL SAFETY RULE: ONLY reconcile deletions if pagination completed 100% successfully.
        if listing_complete:
            active_entries = reg.list_active()
            for entry in active_entries:
                key = entry.get("s3_key")
                # Only reconcile keys that originated from S3 prefix
                if key and key.startswith(self.prefix) and key not in s3_docs:
                    logger.info("Detected deleted document from S3 (full listing verified): %s", key)
                    result["deleted"].append(key)
        else:
            logger.warning("Skipping deletion reconciliation: S3 listing was not verified as 100% complete.")

        # 2. Process S3 documents (new, modified, unchanged)
        for key, meta in s3_docs.items():
            filename = meta["filename"]
            local_path = self.get_cache_path(key)
            s3_size = meta["size_bytes"]
            s3_last_mod = meta["last_modified"]
            file_type = meta["file_type"]

            reg_entry = reg.get(key)
            needs_download = True

            if local_path.exists():
                local_size = local_path.stat().st_size
                if local_size == s3_size:
                    local_hash = self.compute_file_hash(local_path)
                    if reg_entry and reg_entry.get("fingerprint") == local_hash and reg_entry.get("status") == "indexed":
                        needs_download = False
                        result["unchanged"].append(local_path)
                        continue

            if needs_download:
                part_file = local_path.with_name(f".{local_path.name}.part_{os.getpid()}_{int(time.time()*1000)}")
                try:
                    logger.info("Safely downloading s3://%s/%s -> %s (staged at %s)", self.bucket_name, key, local_path, part_file.name)
                    client.download_file(self.bucket_name, key, str(part_file))

                    # Validate completed download
                    if not part_file.exists() or part_file.stat().st_size == 0:
                        raise IOError(f"Zero-byte download received for s3://{self.bucket_name}/{key}")
                    if s3_size > 0 and part_file.stat().st_size != s3_size:
                        raise IOError(f"Truncated download for {key}: expected {s3_size} bytes, got {part_file.stat().st_size}")

                    # Atomic replacement into final cache location
                    part_file.replace(local_path)
                    new_hash = self.compute_file_hash(local_path)

                    if not reg_entry or reg_entry.get("status") == "deleted":
                        reg.register_or_update(
                            s3_key=key,
                            filename=key,
                            file_type=file_type,
                            fingerprint=new_hash,
                            size_bytes=s3_size,
                            last_modified=s3_last_mod,
                            status="pending",
                        )
                        result["new"].append(local_path)
                    else:
                        reg.register_or_update(
                            s3_key=key,
                            filename=key,
                            file_type=file_type,
                            fingerprint=new_hash,
                            size_bytes=s3_size,
                            last_modified=s3_last_mod,
                            status="pending",
                        )
                        result["modified"].append(local_path)

                except Exception as dl_err:
                    if part_file.exists():
                        part_file.unlink(missing_ok=True)
                    logger.error("Failed downloading s3://%s/%s: %s", self.bucket_name, key, dl_err)
                    reg.register_or_update(
                        s3_key=key,
                        filename=key,
                        file_type=file_type,
                        fingerprint="",
                        size_bytes=s3_size,
                        last_modified=s3_last_mod,
                        status="failed",
                        error_message=str(dl_err),
                    )
                    result["failed"].append(key)

        return result

    def _sync_local_cache(self, reg: DocumentRegistry) -> dict[str, list[Any]]:
        """Syncs local cache when running in offline/development mode."""
        result: dict[str, list[Any]] = {
            "new": [],
            "modified": [],
            "deleted": [],
            "unchanged": [],
            "failed": [],
        }

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

        # Detect locally deleted
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
                canonical_key = self.get_s3_key_for_path(path)
                reg_entry = reg.get(canonical_key) or reg.get(fname)
                f_type = path.suffix.lower().lstrip(".")
                f_size = path.stat().st_size

                if not reg_entry or reg_entry.get("status") == "deleted":
                    reg.register_or_update(
                        s3_key=canonical_key,
                        filename=canonical_key,
                        file_type=f_type,
                        fingerprint=f_hash,
                        size_bytes=f_size,
                        cached_path=str(path),
                        status="pending",
                    )
                    result["new"].append(path)
                elif reg_entry.get("fingerprint") != f_hash:
                    reg.register_or_update(
                        s3_key=canonical_key,
                        filename=canonical_key,
                        file_type=f_type,
                        fingerprint=f_hash,
                        size_bytes=f_size,
                        cached_path=str(path),
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

    def get_s3_key_for_path(self, local_path: Path) -> str:
        """
        Maps a local cached document Path to its canonical S3 object key.
        Preserves subdirectory structures to prevent key/name collisions.
        """
        try:
            rel = local_path.resolve().relative_to(self.cache_dir.resolve()).as_posix()
            prefix_clean = self.prefix.strip("/")
            if prefix_clean:
                return f"{prefix_clean}/{rel}"
            return rel
        except ValueError:
            # File is outside cache_dir (e.g. fallback local directory)
            return f"local://{local_path.name}"

    def upload_document(self, local_path: Path, s3_key: Optional[str] = None) -> bool:
        """
        Safely uploads a local document to the S3 bucket if configured.
        Enforces atomic collision rejection to protect original S3 source data:
        1. Pre-checks existence via head_object (fast local rejection).
        2. Executes atomic conditional write via put_object with IfNoneMatch='*'
           to eliminate TOCTOU race conditions under concurrent upload attempts.
        Never overwrites an existing remote S3 object.
        """
        if not self.is_configured():
            logger.warning("Cannot upload to S3: bucket not configured.")
            return False

        target_key = s3_key or self.get_s3_key_for_path(local_path)
        client = self._get_client()

        # Step 1: Explicit collision pre-check (fast local rejection)
        try:
            client.head_object(Bucket=self.bucket_name, Key=target_key)
            logger.error("Upload rejected: S3 object s3://%s/%s already exists. Original S3 objects are immutable.", self.bucket_name, target_key)
            raise FileExistsError(f"Collision rejected: S3 object '{target_key}' already exists in bucket '{self.bucket_name}'. Original S3 objects are immutable.")
        except ClientError as e:
            error_code = str(e.response.get("Error", {}).get("Code", ""))
            # 404 / NoSuchKey / NotFound means the object does not exist yet (safe to create)
            if error_code not in ("404", "NoSuchKey", "NotFound"):
                logger.error("Failed checking object existence for s3://%s/%s: %s", self.bucket_name, target_key, e)
                raise S3AccessError(f"Failed checking object existence in S3: {e}") from e

        # Step 2: Atomic conditional write (eliminates TOCTOU race condition under concurrent uploads)
        try:
            with open(local_path, "rb") as f_data:
                client.put_object(
                    Bucket=self.bucket_name,
                    Key=target_key,
                    Body=f_data,
                    IfNoneMatch="*",
                )
            logger.info("Successfully uploaded %s to s3://%s/%s with atomic concurrency protection", local_path, self.bucket_name, target_key)
            return True
        except ClientError as e:
            error_code = str(e.response.get("Error", {}).get("Code", ""))
            if error_code in ("PreconditionFailed", "412", "AtLeastOneConditionFailed"):
                logger.error("Upload rejected: S3 object s3://%s/%s already exists (concurrent write precondition failed).", self.bucket_name, target_key)
                raise FileExistsError(f"Concurrent collision rejected: S3 object '{target_key}' already exists in bucket '{self.bucket_name}'. Original S3 objects are immutable.")
            logger.error("Failed to upload %s to S3: %s", local_path, e)
            raise
        except Exception as e:
            logger.error("Failed to upload %s to S3: %s", local_path, e)
            raise
