"""Watch CRUD router.

Backed by the same Redis hash the watcher reads from. We don't trigger any
scoring here — we just write the watch and the watcher picks it up on its
next tick.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncIterator

import redis.asyncio as redis
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

log = logging.getLogger("api.watches")

WATCHES_KEY = "watches"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _redis_url() -> str:
    return os.getenv("REDIS_URL", "redis://redis:6379/0")


_client: redis.Redis | None = None


def _get_client() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(_redis_url(), decode_responses=True)
    return _client


# ----- request / response shapes --------------------------------------------


class Profile(BaseModel):
    age: int | None = None
    sex: str | None = None
    condition: str | None = None
    stage: str | None = None
    location: str | None = None
    prior_treatments: list[str] = Field(default_factory=list)


class SearchSpec(BaseModel):
    condition: str | None = None
    location: str | None = None
    age: int | None = None
    sex: str | None = None
    phase: str | None = None
    limit: int = 5


class WatchCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    profile: Profile
    search: SearchSpec


class WatchResult(BaseModel):
    trial_id: str | None = None
    trial_title: str | None = None
    trial_condition: str | None = None
    score: int = 0
    prev_score: int | None = None
    is_new: bool = False
    reason: str = ""
    scored_at: str | None = None


class Watch(BaseModel):
    id: str
    name: str
    profile: Profile
    search: SearchSpec
    created_at: str
    last_checked: str | None = None
    results: list[WatchResult] = Field(default_factory=list)


# ----- router ---------------------------------------------------------------

router = APIRouter(prefix="/api/watches", tags=["watches"])


@router.get("", response_model=list[Watch])
async def list_watches() -> list[Watch]:
    raw = await _get_client().hgetall(WATCHES_KEY)
    out: list[Watch] = []
    for blob in raw.values():
        try:
            out.append(Watch(**json.loads(blob)))
        except Exception as exc:  # noqa: BLE001
            log.warning("skip malformed watch: %s", exc)
    out.sort(key=lambda w: w.created_at)
    return out


@router.get("/stream")
async def stream_watches(request: Request) -> StreamingResponse:
    """Server-Sent Events feed of the watches hash.

    Polls Redis every ~2s and emits a `data:` frame whenever the snapshot
    changes (or every 15s as a heartbeat so proxies don't kill the connection).
    """
    interval = 2.0
    heartbeat_every = 15.0

    async def gen() -> AsyncIterator[bytes]:
        client = _get_client()
        last_payload: str | None = None
        last_emit = 0.0
        # Send an initial snapshot immediately so the UI doesn't sit empty.
        while True:
            if await request.is_disconnected():
                break
            try:
                raw = await client.hgetall(WATCHES_KEY)
                items = []
                for blob in raw.values():
                    try:
                        items.append(json.loads(blob))
                    except Exception:  # noqa: BLE001
                        continue
                items.sort(key=lambda w: w.get("created_at", ""))
                payload = json.dumps(items, separators=(",", ":"))
            except Exception as exc:  # noqa: BLE001
                log.warning("watches stream redis error: %s", exc)
                payload = last_payload or "[]"

            now = asyncio.get_event_loop().time()
            if payload != last_payload or (now - last_emit) >= heartbeat_every:
                yield f"data: {payload}\n\n".encode()
                last_payload = payload
                last_emit = now
            await asyncio.sleep(interval)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/{watch_id}", response_model=Watch)
async def get_watch(watch_id: str) -> Watch:
    blob = await _get_client().hget(WATCHES_KEY, watch_id)
    if not blob:
        raise HTTPException(status_code=404, detail="watch not found")
    return Watch(**json.loads(blob))


@router.post("", response_model=Watch, status_code=201)
async def create_watch(req: WatchCreate) -> Watch:
    watch: dict[str, Any] = {
        "id": uuid.uuid4().hex[:12],
        "name": req.name,
        "profile": req.profile.model_dump(),
        "search": req.search.model_dump(),
        "created_at": _now_iso(),
        "last_checked": None,
        "results": [],
    }
    await _get_client().hset(WATCHES_KEY, watch["id"], json.dumps(watch))
    log.info("created watch id=%s name=%r", watch["id"], watch["name"])
    return Watch(**watch)


@router.delete("/{watch_id}")
async def delete_watch(watch_id: str) -> Response:
    n = await _get_client().hdel(WATCHES_KEY, watch_id)
    if not n:
        raise HTTPException(status_code=404, detail="watch not found")
    log.info("deleted watch id=%s", watch_id)
    return Response(status_code=204)
