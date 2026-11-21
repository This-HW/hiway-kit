"""Policy limits for automatic indexed C/C++ navigation."""
from __future__ import annotations

NEW_KEY_SECONDS = 30.0
EXISTING_KEY_SECONDS = 5.0
CLEANUP_SECONDS = 1.0
LOCK_SECONDS = 1.0
ADDITIONAL_ATTEMPTS = 2
WORKERS = 2
RSS_BYTES = 768 * 1024 * 1024
SAMPLE_SECONDS = 0.1
KEY_BYTES = 128 * 1024 * 1024
TRANSIENT_BYTES = 512 * 1024 * 1024
RETAINED_BYTES = 512 * 1024 * 1024
RETAINED_KEYS = 16
CDB_BYTES = 8 * 1024 * 1024
CDB_ENTRIES = 20000
MAX_DEPTH = 64
SHARD_BYTES = 1024 * 1024
STRINGS_BYTES = 8 * 1024 * 1024
STRINGS_COUNT = 20000
COMMAND_ARGS = 4096
SHARD_VERSIONS = frozenset({20})
SCHEMA = 1
SEMANTIC_ENV = ("CPATH", "C_INCLUDE_PATH", "CPLUS_INCLUDE_PATH", "SDKROOT", "DEVELOPER_DIR")


class IndexUnavailable(Exception):
    """An indexed path cannot be certified; retain partial data at the caller."""

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason
        self.message = message
