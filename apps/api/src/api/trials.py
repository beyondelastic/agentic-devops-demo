"""Demo proxy: append a trial to the tools service.

The tools service holds the trial list in-memory; this passes the call
through with the shared API key so the frontend doesn't need to know it.
A subsequent watcher tick re-runs `search_trials` and surfaces the new
trial in any matching watch (with `is_new=true`).
"""

from __future__ import annotations

import logging
import os

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

log = logging.getLogger("api.trials")

router = APIRouter(prefix="/api/trials", tags=["trials"])


class NewTrial(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    condition: str = Field(min_length=1, max_length=120)
    phase: str | None = None
    location: str | None = None
    age_min: int | None = None
    age_max: int | None = None
    sex: str | None = None
    inclusion_criteria: list[str] | None = None
    exclusion_criteria: list[str] | None = None


def _tools_url() -> str:
    return os.getenv("TOOLS_SERVICE_URL", "http://tools:8000")


def _tools_key() -> str:
    return os.getenv("TOOLS_API_KEY", "demo-key")


@router.post("", status_code=201)
async def add_trial(req: NewTrial) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            r = await client.post(
                f"{_tools_url()}/admin/trials",
                json=req.model_dump(exclude_none=True),
                headers={"x-api-key": _tools_key()},
            )
        except httpx.HTTPError as exc:
            log.warning("tools admin call failed: %s", exc)
            raise HTTPException(status_code=502, detail=f"tools unreachable: {exc}")
    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail=r.text)
    log.info("added trial via tools admin: %s", r.json())
    return r.json()
