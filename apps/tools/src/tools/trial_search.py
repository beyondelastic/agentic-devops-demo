"""Search synthetic clinical trials."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, Field


class Trial(BaseModel):
    id: str
    title: str
    condition: str
    phase: str
    location: str
    age_min: int
    age_max: int
    sex: Literal["all", "male", "female"]
    inclusion_criteria: list[str]
    exclusion_criteria: list[str]


class SearchRequest(BaseModel):
    condition: str | None = Field(
        default=None,
        description="Free-text condition keyword, e.g. 'lung cancer'",
    )
    location: str | None = Field(
        default=None,
        description="City, state, or substring; case-insensitive",
    )
    age: int | None = Field(default=None, ge=0, le=120)
    sex: Literal["male", "female", "all"] | None = None
    phase: str | None = None
    limit: int = Field(default=10, ge=1, le=50)


class TrialSummary(BaseModel):
    id: str
    title: str
    condition: str
    phase: str
    location: str
    age_range: str
    sex: str
    inclusion_count: int
    exclusion_count: int


class SearchResponse(BaseModel):
    count: int
    results: list[TrialSummary]


def _data_path() -> Path:
    """Resolve trials JSON; checks repo-relative and container-relative paths."""
    here = Path(__file__).resolve()
    candidates: list[Path] = [
        Path("/app/data/synthetic_trials.json"),  # container layout
        Path("data/synthetic_trials.json"),       # cwd
    ]
    # Walk up to repo root (any depth) — works in dev regardless of how deep
    # the source lives below the repo root.
    for parent in here.parents:
        candidates.append(parent / "data" / "synthetic_trials.json")
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError(
        "synthetic_trials.json not found in any expected location: "
        + ", ".join(str(p) for p in candidates)
    )


def load_trials() -> list[Trial]:
    raw = json.loads(_data_path().read_text(encoding="utf-8"))
    return [Trial(**item) for item in raw]


def _to_summary(trial: Trial) -> TrialSummary:
    return TrialSummary(
        id=trial.id,
        title=trial.title,
        condition=trial.condition,
        phase=trial.phase,
        location=trial.location,
        age_range=f"{trial.age_min}-{trial.age_max}",
        sex=trial.sex,
        inclusion_count=len(trial.inclusion_criteria),
        exclusion_count=len(trial.exclusion_criteria),
    )


def search_trials(trials: list[Trial], req: SearchRequest) -> SearchResponse:
    matches: list[Trial] = []
    cond = (req.condition or "").lower().strip()
    loc = (req.location or "").lower().strip()
    phase = (req.phase or "").lower().strip()

    for t in trials:
        if cond and cond not in t.condition.lower() and cond not in t.title.lower():
            continue
        if loc and loc not in t.location.lower():
            continue
        if phase and phase not in t.phase.lower():
            continue
        if req.age is not None and not (t.age_min <= req.age <= t.age_max):
            continue
        if req.sex and req.sex != "all" and t.sex != "all" and t.sex != req.sex:
            continue
        matches.append(t)

    truncated = matches[: req.limit]
    return SearchResponse(
        count=len(truncated),
        results=[_to_summary(t) for t in truncated],
    )


def summarize_trial(trials: list[Trial], trial_id: str) -> TrialSummary:
    for t in trials:
        if t.id == trial_id:
            return _to_summary(t)
    raise HTTPException(status_code=404, detail=f"Trial {trial_id} not found")
