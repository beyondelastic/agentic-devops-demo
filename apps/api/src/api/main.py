"""API orchestrator entry point."""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .foundry_client import health_snapshot, stream_chat
from .leak_toggle import leak_size_mb, maybe_leak
from .settings import get_settings

log = logging.getLogger("api")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

app = FastAPI(
    title="Clinical Trial Matcher — API",
    description="Orchestrator that proxies chat requests to the Foundry prompt agent.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


@app.get("/healthz", tags=["probes"])
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/version", tags=["probes"])
def version() -> dict[str, str]:
    settings = get_settings()
    return {"git_sha": settings.git_sha, "built_at": settings.built_at}


@app.get("/readyz", tags=["probes"])
def readyz() -> dict[str, object]:
    return {"status": "ok", "foundry": health_snapshot(), "leak_mb": leak_size_mb()}


@app.post("/api/chat", tags=["chat"])
async def chat(req: ChatRequest) -> StreamingResponse:
    settings = get_settings()
    maybe_leak(settings.enable_memory_leak)

    async def event_stream():
        async for chunk in stream_chat(req.message, settings):
            yield chunk

    return StreamingResponse(event_stream(), media_type="text/plain; charset=utf-8")


# OpenTelemetry / Application Insights wiring is opt-in via env var.
def _wire_telemetry() -> None:
    settings = get_settings()
    if not settings.applicationinsights_connection_string:
        return
    try:
        from azure.monitor.opentelemetry import configure_azure_monitor

        configure_azure_monitor(
            connection_string=settings.applicationinsights_connection_string,
            disable_offline_storage=True,
        )
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)
        log.info("App Insights telemetry configured")
    except Exception as e:  # noqa: BLE001
        log.warning("Failed to wire telemetry: %s", e)


_wire_telemetry()
