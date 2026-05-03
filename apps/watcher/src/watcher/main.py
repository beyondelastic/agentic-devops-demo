"""Watcher worker loop.

Each tick:
  1. Read the current set of watches from Redis (`watches` hash)
  2. For each watch:
     a. Fetch candidate trials from the tools service
     b. Score each trial against the patient profile via the local model
     c. Persist the updated watch document back to Redis
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import time

import httpx

from .scoring import score_match
from .settings import seed_watches, settings
from .state import list_watches, make_client, now_iso, put_watch

log = logging.getLogger("watcher")


async def _search(client: httpx.AsyncClient, search: dict) -> list[dict]:
    r = await client.post(
        f"{settings.tools_url}/tools/search_trials",
        json=search,
        headers={"x-api-key": settings.tools_api_key},
        timeout=10.0,
    )
    r.raise_for_status()
    body = r.json()
    return body.get("results", [])


async def _process_watch(http: httpx.AsyncClient, redis_client, watch: dict) -> None:
    watch_id = watch.get("id", "?")
    name = watch.get("name", watch_id)
    profile = watch.get("profile", {})
    search = watch.get("search", {})

    # Snapshot previous scores per trial so we can compute deltas + "is_new".
    prev_by_trial: dict[str, dict] = {}
    for r in watch.get("results", []) or []:
        tid = r.get("trial_id")
        if tid:
            prev_by_trial[tid] = r

    t0 = time.monotonic()
    try:
        trials = await _search(http, search)
    except Exception as exc:  # noqa: BLE001
        log.error("watch=%s search failed: %s", watch_id, exc)
        return

    trials = trials[: settings.max_trials_per_watch]
    log.info("watch=%s name=%r trials_found=%d", watch_id, name, len(trials))

    results: list[dict] = []
    for trial in trials:
        try:
            score, reason = await score_match(http, profile, trial)
        except Exception as exc:  # noqa: BLE001
            log.error("watch=%s trial=%s scoring failed: %s", watch_id, trial.get("id"), exc)
            continue
        tid = trial.get("id")
        prev = prev_by_trial.get(tid) if tid else None
        prev_score = prev.get("score") if prev else None
        is_new = prev is None
        results.append(
            {
                "trial_id": tid,
                "trial_title": trial.get("title"),
                "trial_condition": trial.get("condition"),
                "score": score,
                "prev_score": prev_score,
                "is_new": is_new,
                "reason": reason,
                "scored_at": now_iso(),
            }
        )
        log.info(
            "match watch=%s trial=%s score=%d prev=%s new=%s reason=%r",
            watch_id,
            tid,
            score,
            prev_score,
            is_new,
            reason,
        )

    # Sort highest score first so the UI can take results[:N] without re-sorting.
    results.sort(key=lambda r: r["score"], reverse=True)

    watch["results"] = results
    watch["last_checked"] = now_iso()
    await put_watch(redis_client, watch)
    log.info("watch=%s done in %.1fs results=%d", watch_id, time.monotonic() - t0, len(results))


async def _maybe_seed(redis_client) -> None:
    if not settings.seed_demo_watches:
        return
    existing = {w["id"] for w in await list_watches(redis_client)}
    seeds = seed_watches()
    added = 0
    for s in seeds:
        if s["id"] in existing:
            continue
        s.setdefault("created_at", now_iso())
        s.setdefault("last_checked", None)
        s.setdefault("results", [])
        await put_watch(redis_client, s)
        added += 1
    if added:
        log.info("seeded %d demo watches (existing=%d)", added, len(existing))
    else:
        log.info("seed skipped: all %d demo watches already present", len(seeds))


async def _tick(http: httpx.AsyncClient, redis_client) -> None:
    watches = await list_watches(redis_client)
    log.info("tick start watches=%d", len(watches))
    for watch in watches:
        await _process_watch(http, redis_client, watch)
    log.info("tick done")


async def _run() -> None:
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    log.info(
        "watcher starting tools=%s model=%s redis=%s tick=%ds",
        settings.tools_url,
        settings.local_model_url,
        settings.redis_url,
        settings.tick_seconds,
    )

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    redis_client = make_client(settings.redis_url)
    try:
        await redis_client.ping()
        log.info("redis ping ok")
    except Exception as exc:  # noqa: BLE001
        log.error("redis ping failed: %s", exc)
        raise

    await _maybe_seed(redis_client)

    async with httpx.AsyncClient() as http:
        if os.getenv("RUN_ONCE") == "1":
            await _tick(http, redis_client)
            return

        while not stop.is_set():
            try:
                await _tick(http, redis_client)
            except Exception as exc:  # noqa: BLE001
                log.exception("tick crashed: %s", exc)
            try:
                await asyncio.wait_for(stop.wait(), timeout=settings.tick_seconds)
            except TimeoutError:
                continue

    await redis_client.aclose()
    log.info("watcher stopped")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
