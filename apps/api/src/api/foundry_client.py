"""Foundry client wrapper (current SDK).

Uses the latest Foundry Python SDK:

* ``azure-ai-projects`` ``AIProjectClient`` is the entry point.
* ``project_client.agents.*`` exposes threads / messages / runs.
* For streaming we use the OpenAI-compatible Responses API obtained via
  ``project_client.get_openai_client()`` and reference the existing prompt agent
  with ``extra_body={"agent": {"name": ..., "type": "agent_reference"}}``.

In ``mock`` mode the call to Foundry is replaced with a deterministic
echo-style response so the demo runs locally without Azure.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator
from functools import lru_cache

import httpx

from .settings import Settings, get_settings

log = logging.getLogger("api.foundry")


@lru_cache
def _project_client():  # type: ignore[no-untyped-def]
    """Lazily build an AIProjectClient using DefaultAzureCredential."""
    settings = get_settings()
    if settings.foundry_mode == "mock" or not settings.foundry_project_endpoint:
        return None
    # Imported lazily so mock mode (and tests) doesn't require the Azure SDK to be importable.
    from azure.ai.projects import AIProjectClient
    from azure.identity import DefaultAzureCredential

    return AIProjectClient(
        endpoint=settings.foundry_project_endpoint,
        credential=DefaultAzureCredential(),
        allow_preview=True,
    )


async def stream_chat(user_message: str, settings: Settings | None = None) -> AsyncIterator[str]:
    """Yield text deltas from the Foundry agent.

    In ``mock`` mode, fall back to a local trial search via the tools service.
    """
    settings = settings or get_settings()

    if settings.foundry_mode == "mock":
        async for chunk in _mock_stream(user_message, settings):
            yield chunk
        return

    client = _project_client()
    if client is None:
        async for chunk in _mock_stream(user_message, settings):
            yield chunk
        return

    try:
        # `get_openai_client(agent_name=...)` returns an OpenAI client pre-bound to
        # the declarative agent. The Responses API streams text deltas.
        openai_client = client.get_openai_client(agent_name=settings.foundry_agent_name)

        def _start_stream():  # type: ignore[no-untyped-def]
            return openai_client.responses.create(
                stream=True,
                input=user_message,
            )

        loop = asyncio.get_running_loop()
        # Cap the connect/handshake so a missing/invalid agent surfaces fast
        # instead of stalling the whole HTTP request behind ingress.
        stream = await asyncio.wait_for(
            loop.run_in_executor(None, _start_stream), timeout=20.0
        )
    except TimeoutError:
        log.error("Foundry responses.create timed out after 20s")
        yield (
            f"⚠️  The Foundry agent **'{settings.foundry_agent_name}'** did not respond "
            f"within 20s.\n\n"
            f"This usually means the agent has not been created yet. Run **Demo 2** "
            f"(create the prompt agent in the Foundry VS Code extension and commit "
            f"`.foundry/agent-metadata.yaml`) and redeploy, then try again.\n"
        )
        return
    except Exception as e:  # noqa: BLE001
        log.error("Foundry responses.create failed: %s", e)
        yield (
            f"⚠️  Could not reach Foundry agent **'{settings.foundry_agent_name}'**.\n\n"
            f"Most likely the agent does not exist yet — create it via the Foundry "
            f"VS Code extension (Demo 2) and redeploy.\n\n"
            f"Underlying error: `{e}`\n"
        )
        return

    def _next(it):  # type: ignore[no-untyped-def]
        try:
            return next(it)
        except StopIteration:
            return None
        except Exception as e:  # noqa: BLE001
            return ("__error__", e)

    iterator = iter(stream)
    while True:
        event = await loop.run_in_executor(None, _next, iterator)
        if event is None:
            break
        if isinstance(event, tuple) and event and event[0] == "__error__":
            log.error("Foundry stream iteration error: %s", event[1])
            yield f"\n\n[stream error: {event[1]}]"
            break
        # Text delta events stream the assistant's tokens.
        event_type = getattr(event, "type", None)
        if event_type == "response.output_text.delta":
            delta = getattr(event, "delta", None)
            if delta:
                yield delta
        elif event_type == "response.error":
            log.error("Foundry stream error: %s", getattr(event, "error", "unknown"))
            yield "\n\n[error from agent]"
            break


async def _mock_stream(user_message: str, settings: Settings) -> AsyncIterator[str]:
    """Mock path: query the tools service directly so the UX still works locally."""
    yield "Looking up trials for you...\n\n"
    await asyncio.sleep(0.05)

    condition = _guess_condition(user_message)
    async with httpx.AsyncClient(timeout=10.0) as http:
        try:
            resp = await http.post(
                f"{settings.tools_service_url}/tools/search_trials",
                json={"condition": condition, "limit": 3},
                headers={"x-api-key": settings.tools_api_key},
            )
            resp.raise_for_status()
            payload = resp.json()
        except Exception as e:  # noqa: BLE001 - surface to the user in mock mode
            yield f"(mock) tools service error: {e}\n"
            return

    if payload["count"] == 0:
        yield f"(mock) No trials matched condition='{condition}'.\n"
        return

    yield f"(mock) Found {payload['count']} trial(s) for condition='{condition}':\n\n"
    for r in payload["results"]:
        line = (
            f"- **{r['title']}** ({r['phase']}) — {r['location']}, "
            f"ages {r['age_range']}, sex={r['sex']}\n"
        )
        for ch in line:
            yield ch
            await asyncio.sleep(0.001)


def _guess_condition(text: str) -> str:
    """Tiny heuristic so the mock path returns reasonable results without an LLM."""
    keywords = [
        "lung",
        "diabetes",
        "alzheimer",
        "melanoma",
        "sickle",
        "psoriasis",
        "lymphoma",
        "epilepsy",
        "asthma",
        "covid",
        "ptsd",
        "obesity",
        "ra",
        "copd",
    ]
    lowered = text.lower()
    for kw in keywords:
        if kw in lowered:
            return kw
    return ""


def health_snapshot() -> dict[str, object]:
    """Best-effort health snapshot for /readyz."""
    settings = get_settings()
    return {
        "mode": settings.foundry_mode,
        "agent_name": settings.foundry_agent_name,
        "endpoint_configured": bool(settings.foundry_project_endpoint),
        "ts": int(time.time()),
    }


def _to_jsonable(obj: object) -> object:
    try:
        return json.loads(json.dumps(obj, default=str))
    except Exception:  # noqa: BLE001
        return str(obj)
