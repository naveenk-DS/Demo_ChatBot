"""
Persistent Document Registry for EstateAI.
Tracks all structured (CSV, XLSX, JSON) and unstructured (PDF) documents
ingested from Amazon S3 or local storage.

Maintains document lifecycle:
- Status: 'pending', 'processing', 'indexed', 'failed', 'deleted'
- S3 Key, filename, file type, SHA-256 fingerprint, last modified timestamp
- Record / chunk count and error messages
- Persistent on EC2 local storage (registry.json)
"""

import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Union

from app.config import env

logger = logging.getLogger("estateai.document_registry")

DEFAULT_REGISTRY_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "document_registry.json"


class DocumentRegistry:
    def __init__(self, registry_file: Optional[Union[str, Path]] = None):
        self.registry_file = Path(registry_file or env("DOCUMENT_REGISTRY_PATH", str(DEFAULT_REGISTRY_PATH)))
        self.registry_file.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._registry: dict[str, dict[str, Any]] = {}
        self.load()

    def load(self) -> None:
        """Loads the registry from disk."""
        with self._lock:
            if not self.registry_file.exists():
                self._registry = {}
                return

            try:
                with open(self.registry_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self._registry = data
                    else:
                        self._registry = {}
                logger.info("Loaded document registry with %d entries from %s", len(self._registry), self.registry_file)
            except Exception as e:
                logger.error("Failed to load document registry from %s: %s", self.registry_file, e)
                self._registry = {}

    def save(self) -> None:
        """Persists the registry to disk atomically."""
        with self._lock:
            try:
                temp_file = self.registry_file.with_suffix(".tmp")
                with open(temp_file, "w", encoding="utf-8") as f:
                    json.dump(self._registry, f, indent=2, default=str)
                temp_file.replace(self.registry_file)
            except Exception as e:
                logger.error("Failed to persist document registry to %s: %s", self.registry_file, e)

    def register_or_update(
        self,
        s3_key: str,
        filename: str,
        file_type: str,
        fingerprint: str,
        size_bytes: int = 0,
        last_modified: Optional[str] = None,
        status: str = "pending",
        record_count: int = 0,
        chunk_count: int = 0,
        error_message: Optional[str] = None,
    ) -> dict[str, Any]:
        """Registers a new document or updates an existing document entry."""
        with self._lock:
            now_iso = datetime.now(timezone.utc).isoformat()
            existing = self._registry.get(s3_key)

            version = 1
            if existing:
                version = existing.get("indexing_version", 1)
                # Increment version if fingerprint changed
                if existing.get("fingerprint") != fingerprint:
                    version += 1

            entry: dict[str, Any] = {
                "s3_key": s3_key,
                "filename": filename,
                "file_type": file_type.lower().strip("."),
                "fingerprint": fingerprint,
                "size_bytes": size_bytes,
                "last_modified": last_modified or now_iso,
                "status": status,
                "indexing_version": version,
                "record_count": record_count,
                "chunk_count": chunk_count,
                "error_message": error_message,
                "updated_at": now_iso,
            }
            self._registry[s3_key] = entry

        self.save()
        return entry

    def update_status(
        self,
        s3_key: str,
        status: str,
        record_count: Optional[int] = None,
        chunk_count: Optional[int] = None,
        error_message: Optional[str] = None,
        fingerprint: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """Updates status and counts of an existing document."""
        with self._lock:
            entry = self._registry.get(s3_key)
            if not entry:
                # Also try looking up by filename
                for k, v in self._registry.items():
                    if v.get("filename") == s3_key:
                        entry = v
                        s3_key = k
                        break

            if not entry:
                logger.warning("Attempted to update non-registered document: %s", s3_key)
                return None

            entry["status"] = status
            entry["updated_at"] = datetime.now(timezone.utc).isoformat()

            if record_count is not None:
                entry["record_count"] = record_count
            if chunk_count is not None:
                entry["chunk_count"] = chunk_count
            if error_message is not None:
                entry["error_message"] = error_message
            elif status in ("indexed", "pending"):
                entry["error_message"] = None
            if fingerprint is not None:
                entry["fingerprint"] = fingerprint

        self.save()
        return entry

    def mark_deleted(self, s3_key: str) -> Optional[dict[str, Any]]:
        """Marks a document as deleted in the registry."""
        with self._lock:
            entry = self._registry.get(s3_key)
            if not entry:
                for k, v in self._registry.items():
                    if v.get("filename") == s3_key:
                        entry = v
                        s3_key = k
                        break

            if entry:
                entry["status"] = "deleted"
                entry["updated_at"] = datetime.now(timezone.utc).isoformat()

        self.save()
        return entry

    def remove(self, s3_key: str) -> bool:
        """Completely purges a document entry from the registry."""
        with self._lock:
            if s3_key in self._registry:
                del self._registry[s3_key]
                self.save()
                return True
            for k, v in list(self._registry.items()):
                if v.get("filename") == s3_key:
                    del self._registry[k]
                    self.save()
                    return True
        return False

    def get(self, s3_key_or_filename: str) -> Optional[dict[str, Any]]:
        """Retrieves an entry by S3 key or filename."""
        with self._lock:
            if s3_key_or_filename in self._registry:
                return dict(self._registry[s3_key_or_filename])
            for k, v in self._registry.items():
                if v.get("filename") == s3_key_or_filename:
                    return dict(v)
        return None

    def list_all(self) -> list[dict[str, Any]]:
        """Returns all registered documents."""
        with self._lock:
            return [dict(v) for v in self._registry.values()]

    def list_active(self) -> list[dict[str, Any]]:
        """Returns all documents that are not deleted."""
        with self._lock:
            return [dict(v) for v in self._registry.values() if v.get("status") != "deleted"]

    def is_indexed(self, s3_key_or_filename: str, current_fingerprint: str) -> bool:
        """Returns True if document is indexed with matching fingerprint."""
        entry = self.get(s3_key_or_filename)
        if not entry:
            return False
        return (
            entry.get("status") == "indexed"
            and entry.get("fingerprint") == current_fingerprint
        )


_GLOBAL_REGISTRY: Optional[DocumentRegistry] = None


def get_document_registry() -> DocumentRegistry:
    global _GLOBAL_REGISTRY
    if _GLOBAL_REGISTRY is None:
        _GLOBAL_REGISTRY = DocumentRegistry()
    return _GLOBAL_REGISTRY
