"""Trial matching tools service.

Exposes three endpoints that the Foundry prompt agent calls as an OpenAPI tool:

* POST /tools/search_trials
* POST /tools/check_eligibility
* GET  /tools/trials/{trial_id}/summary

Plus standard /healthz and /readyz probes for Container Apps.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from .eligibility import EligibilityRequest, EligibilityResponse, check_eligibility
from .trial_search import (
    NewTrialRequest,
    SearchRequest,
    SearchResponse,
    Trial,
    TrialSummary,
    _to_summary,
    load_trials,
    search_trials,
    summarize_trial,
)

log = logging.getLogger("tools")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.trials = load_trials()
    log.info("Loaded %d trials", len(app.state.trials))
    yield


app = FastAPI(
    title="Clinical Trial Matcher — Tools",
    description=(
        "Tools exposed to the Foundry prompt agent as an OpenAPI tool. "
        "Operates over a synthetic, demo-only trial dataset."
    ),
    version="0.1.0",
    lifespan=lifespan,
    # Advertise the public base URL in the OpenAPI doc so Foundry's OpenAPI
    # tool integration knows where to call. PUBLIC_BASE_URL is injected by
    # Bicep from the Container App's external FQDN.
    servers=(
        [{"url": os.environ["PUBLIC_BASE_URL"]}]
        if os.getenv("PUBLIC_BASE_URL")
        else None
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# Foundry's OpenAPI tool requires the spec to declare an `apiKey` security
# scheme when "Connection" / "API Key" auth is configured on the tool. Patch
# FastAPI's generated schema to add it once.
def _custom_openapi() -> dict:
    if app.openapi_schema:
        return app.openapi_schema
    from fastapi.openapi.utils import get_openapi

    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        servers=app.servers,
    )
    schema.setdefault("components", {}).setdefault("securitySchemes", {})[
        "ApiKeyAuth"
    ] = {
        "type": "apiKey",
        "in": "header",
        "name": "x-api-key",
    }
    schema["security"] = [{"ApiKeyAuth": []}]
    app.openapi_schema = schema
    return schema


app.openapi = _custom_openapi  # type: ignore[assignment]


# Simple shared-secret check so the Foundry portal's "API Key" auth flow has
# something to send. The /tools/* operations require it; probes do not.
TOOLS_API_KEY = os.getenv("TOOLS_API_KEY", "demo-key")


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if x_api_key != TOOLS_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing or invalid x-api-key",
        )


@app.get("/healthz", tags=["probes"])
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz", tags=["probes"])
def readyz() -> dict[str, object]:
    return {"status": "ok", "trials_loaded": len(app.state.trials)}


@app.post(
    "/tools/search_trials",
    response_model=SearchResponse,
    operation_id="search_trials",
    summary="Search clinical trials by condition, location, and demographics",
    tags=["tools"],
    dependencies=[Depends(require_api_key)],
)
def search_trials_endpoint(req: SearchRequest) -> SearchResponse:
    return search_trials(app.state.trials, req)


@app.post(
    "/tools/check_eligibility",
    response_model=EligibilityResponse,
    operation_id="check_eligibility",
    summary="Check whether a synthetic patient profile likely meets a trial's criteria",
    tags=["tools"],
    dependencies=[Depends(require_api_key)],
)
def check_eligibility_endpoint(req: EligibilityRequest) -> EligibilityResponse:
    return check_eligibility(app.state.trials, req)


@app.get(
    "/tools/trials/{trial_id}/summary",
    response_model=TrialSummary,
    operation_id="summarize_trial",
    summary="Summarize a single trial by id",
    tags=["tools"],
    dependencies=[Depends(require_api_key)],
)
def summarize_trial_endpoint(trial_id: str) -> TrialSummary:
    return summarize_trial(app.state.trials, trial_id)


# ----- demo admin: add a trial at runtime -----------------------------------
# Lets the UI inject new synthetic trials so the watcher's next tick picks
# them up and emits NEW pills. Not part of the Foundry tool surface.


@app.post(
    "/admin/trials",
    response_model=TrialSummary,
    tags=["admin"],
    dependencies=[Depends(require_api_key)],
)
def add_trial_endpoint(req: NewTrialRequest) -> TrialSummary:
    import uuid as _uuid

    existing_ids = {t.id for t in app.state.trials}
    new_id = req.id or f"TM-DEMO-{_uuid.uuid4().hex[:6].upper()}"
    if new_id in existing_ids:
        raise HTTPException(status_code=409, detail=f"trial id {new_id} already exists")

    trial = Trial(
        id=new_id,
        title=req.title,
        condition=req.condition,
        phase=req.phase or "Phase 2",
        location=req.location or "Multi-site",
        age_min=req.age_min if req.age_min is not None else 18,
        age_max=req.age_max if req.age_max is not None else 99,
        sex=req.sex or "all",
        inclusion_criteria=req.inclusion_criteria or [],
        exclusion_criteria=req.exclusion_criteria or [],
    )
    app.state.trials.append(trial)
    log.info(
        "admin: added trial id=%s title=%r (total=%d)",
        trial.id,
        trial.title,
        len(app.state.trials),
    )
    return _to_summary(trial)
