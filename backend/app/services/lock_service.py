"""
Cross-platform inter-process and inter-thread file lock for EstateAI.
Prevents concurrent workers or simultaneous HTTP requests from corrupting
the FAISS index, Document Registry, or structured property cache.
"""

import logging
import os
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

logger = logging.getLogger("estateai.lock_service")

LOCK_DIR = Path(__file__).resolve().parent.parent.parent / "data"
LOCK_FILE = LOCK_DIR / ".indexing.lock"

_THREAD_LOCK = threading.Lock()


class IndexingConflictError(Exception):
    """Raised when an indexing operation cannot acquire the lock due to concurrent execution."""
    pass


@contextmanager
def acquire_indexing_lock(timeout_seconds: float = 30.0, lock_path: Optional[Path] = None):
    """
    Context manager acquiring both in-process thread lock and cross-process file lock.
    Waits up to timeout_seconds before raising IndexingConflictError.
    """
    target_lock_file = lock_path or LOCK_FILE
    target_lock_file.parent.mkdir(parents=True, exist_ok=True)

    acquired_thread = _THREAD_LOCK.acquire(timeout=timeout_seconds)
    if not acquired_thread:
        raise IndexingConflictError("Could not acquire thread lock: another indexing operation is running in this process.")

    file_handle = None
    start_time = time.time()
    try:
        file_handle = open(target_lock_file, "a+")

        # Cross-platform file locking
        locked = False
        while time.time() - start_time < timeout_seconds:
            try:
                if sys.platform == "win32":
                    import msvcrt
                    # Lock 1 byte at position 0 in non-blocking mode
                    file_handle.seek(0)
                    msvcrt.locking(file_handle.fileno(), msvcrt.LK_NBLCK, 1)
                    locked = True
                    break
                else:
                    import fcntl
                    fcntl.flock(file_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    locked = True
                    break
            except (IOError, OSError, BlockingIOError):
                time.sleep(0.1)

        if not locked:
            raise IndexingConflictError(f"Could not acquire file lock on '{target_lock_file}' within {timeout_seconds}s: another worker is indexing.")

        logger.debug("Acquired exclusive indexing lock.")
        yield

    finally:
        if file_handle:
            try:
                if sys.platform == "win32":
                    import msvcrt
                    file_handle.seek(0)
                    msvcrt.locking(file_handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(file_handle.fileno(), fcntl.LOCK_UN)
            except Exception as unlock_err:
                logger.debug("Error releasing file lock: %s", unlock_err)
            finally:
                file_handle.close()

        _THREAD_LOCK.release()
        logger.debug("Released exclusive indexing lock.")

