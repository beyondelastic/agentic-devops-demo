"""Demo 6: env-flag-gated memory leak.

When ENABLE_MEMORY_LEAK=true, every chat request appends ~5 MB of bytes to a
module-level list. Container Apps OOM-kills the replica, the SRE Agent picks up
the pattern, and the presenter reverts the env var.

This is intentionally crude. Do NOT enable in production.
"""

from __future__ import annotations

import logging

log = logging.getLogger("api.leak")

# Module-level list — leaks survive across requests within a worker.
_LEAK_BUFFER: list[bytes] = []
_CHUNK_SIZE = 20 * 1024 * 1024  # 20 MB


def maybe_leak(enabled: bool) -> None:
    if not enabled:
        return
    _LEAK_BUFFER.append(b"x" * _CHUNK_SIZE)
    if len(_LEAK_BUFFER) % 5 == 0:
        log.warning(
            "[demo-leak] buffer holds %d chunks (~%d MB)",
            len(_LEAK_BUFFER),
            len(_LEAK_BUFFER) * _CHUNK_SIZE // (1024 * 1024),
        )


def leak_size_mb() -> int:
    return len(_LEAK_BUFFER) * _CHUNK_SIZE // (1024 * 1024)
