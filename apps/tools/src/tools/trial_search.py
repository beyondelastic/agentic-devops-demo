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


# Words to drop from the condition keyword before matching. The agent often
# extracts phrases like "stage 2 lung cancer" or "advanced melanoma"; the
# dataset uses canonical names ("Non-Small Cell Lung Cancer", "Melanoma"),
# so a plain substring match misses. We tokenize and require that *any*
# remaining token appears in the trial's condition+title.
_STOPWORDS = {
    "a", "an", "and", "the", "of", "with", "for",
    "stage", "phase", "grade", "early", "late", "advanced", "metastatic",
    "recurrent", "chronic", "acute", "severe", "mild", "moderate",
    "i", "ii", "iii", "iv", "1", "2", "3", "4",
    "cancer", "disease", "syndrome", "disorder",
}


def _condition_tokens(condition: str) -> list[str]:
    """Split a free-text condition keyword into match tokens.

    Drops stopwords (stage/phase qualifiers, generic terms like 'cancer').
    Falls back to the original phrase if every token is a stopword, so e.g.
    'cancer' alone still matches against the canonical condition strings.
    """
    raw = [t for t in condition.replace("-", " ").split() if t]
    tokens = [t for t in raw if t not in _STOPWORDS]
    return tokens or raw


def search_trials(trials: list[Trial], req: SearchRequest) -> SearchResponse:
    matches: list[Trial] = []
    cond = (req.condition or "").lower().strip()
    cond_tokens = _condition_tokens(cond) if cond else []
    loc = (req.location or "").lower().strip()
    phase = (req.phase or "").lower().strip()

    for t in trials:
        haystack = f"{t.condition} {t.title}".lower()
        if cond_tokens and not any(tok in haystack for tok in cond_tokens):
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
