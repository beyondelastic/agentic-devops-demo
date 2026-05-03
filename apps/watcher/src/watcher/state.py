"""Watch storage on Redis.

Schema: a single Redis hash named `watches`. Each field is a watch id; each
value is a JSON document of shape:

    {
      "id": "...",
      "name": "...",
      "profile": {...},          # patient
      "search": {...},           # SearchRequest fields for tools/search_trials
      "created_at": "<iso8601>",
      "last_checked": "<iso8601>" | null,
      "results": [
        {"trial_id": "...", "score": 0-100, "reason": "...", "scored_at": "<iso8601>"}
      ]
    }

We keep all state in one document so the watcher can read+update atomically
with HSET. No transactions needed for the demo's single-watcher singleton.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as redis

WATCHES_KEY = "watches"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def make_client(url: str) -> redis.Redis:
    return redis.from_url(url, decode_responses=True)


async def list_watches(client: redis.Redis) -> list[dict[str, Any]]:
    raw = await client.hgetall(WATCHES_KEY)
    out: list[dict] = []
    for _, blob in raw.items():
        try:
            out.append(json.loads(blob))
        except json.JSONDecodeError:
            continue
    out.sort(key=lambda w: w.get("created_at", ""))
    return out


async def get_watch(client: redis.Redis, watch_id: str) -> dict[str, Any] | None:
    blob = await client.hget(WATCHES_KEY, watch_id)
    if not blob:
        return None
    return json.loads(blob)


async def put_watch(client: redis.Redis, watch: dict[str, Any]) -> None:
    await client.hset(WATCHES_KEY, watch["id"], json.dumps(watch))


async def delete_watch(client: redis.Redis, watch_id: str) -> bool:
    n = await client.hdel(WATCHES_KEY, watch_id)
    return bool(n)
