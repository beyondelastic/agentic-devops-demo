"""Settings for the watcher service.

All configuration is via env vars; defaults are dev-friendly and match the
in-cluster service names defined by the helm chart.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field


def _env(name: str, default: str) -> str:
    val = os.getenv(name)
    return val if val is not None and val != "" else default


@dataclass(frozen=True)
class Settings:
    # Where to find the tools service (search_trials endpoint).
    tools_url: str = field(default_factory=lambda: _env("TOOLS_SERVICE_URL", "http://tools:8000"))
    tools_api_key: str = field(default_factory=lambda: _env("TOOLS_API_KEY", "demo-key"))

    # Where to find the in-cluster small model (OpenAI-compatible /v1/...).
    local_model_url: str = field(
        default_factory=lambda: _env("LOCAL_MODEL_URL", "http://workspace-llama-3-3b")
    )
    local_model_name: str = field(
        default_factory=lambda: _env("LOCAL_MODEL_NAME", "llama-3.2-3b-instruct")
    )

    # Redis (shared with api).
    redis_url: str = field(default_factory=lambda: _env("REDIS_URL", "redis://redis:6379/0"))

    # Auto-seed Redis with demo watches if empty on startup.
    seed_demo_watches: bool = field(
        default_factory=lambda: _env("SEED_DEMO_WATCHES", "1") == "1"
    )

    # Loop control.
    tick_seconds: int = field(default_factory=lambda: int(_env("WATCHER_TICK_SECONDS", "60")))
    max_trials_per_watch: int = field(
        default_factory=lambda: int(_env("WATCHER_MAX_TRIALS", "5"))
    )
    score_timeout_seconds: float = field(
        default_factory=lambda: float(_env("WATCHER_SCORE_TIMEOUT", "30"))
    )

    log_level: str = field(default_factory=lambda: _env("LOG_LEVEL", "INFO"))


settings = Settings()


# Demo seed: a list of WatchSpec dicts inserted into Redis on first startup
# when SEED_DEMO_WATCHES=1 and the watches hash is empty.
_DEFAULT_WATCHES_JSON = json.dumps(
    [
        {
            "id": "demo-w1",
            "name": "Aunt Helen — NSCLC",
            "profile": {
                "age": 62,
                "sex": "female",
                "condition": "non-small cell lung cancer",
                "stage": "stage 3",
                "location": "Cleveland, OH",
                "prior_treatments": ["platinum chemotherapy"],
            },
            "search": {"condition": "lung cancer", "limit": 5},
        },
        {
            "id": "demo-w2",
            "name": "Patient B — melanoma",
            "profile": {
                "age": 47,
                "sex": "male",
                "condition": "metastatic melanoma",
                "location": "Boston, MA",
                "prior_treatments": [],
            },
            "search": {"condition": "melanoma", "limit": 5},
        },
        {
            "id": "demo-w3",
            "name": "Cohort — cancer screening",
            "profile": {
                "age": 55,
                "sex": "female",
                "condition": "cancer",
                "location": "New York",
                "prior_treatments": [],
            },
            "search": {"condition": "cancer", "limit": 5},
        },
    ]
)


def seed_watches() -> list[dict]:
    """Demo seed list. Caller is responsible for writing them to Redis."""
    raw = _env("WATCHES_JSON", _DEFAULT_WATCHES_JSON)
    return json.loads(raw)
