"""Lightweight rule-based eligibility check over synthetic trials.

Demo-only: this is *not* clinical-grade reasoning. The Foundry agent uses the LLM to
pull structured signals out of the user's free-text request, then calls this tool to
filter on the structured fields.
"""

from __future__ import annotations

from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, Field

from .trial_search import Trial


class PatientProfile(BaseModel):
    age: int = Field(ge=0, le=120)
    sex: Literal["male", "female"]
    primary_condition: str = Field(description="Free-text primary condition")
    location: str | None = None
    notes: str | None = Field(default=None, description="Optional free-text notes")


class EligibilityRequest(BaseModel):
    trial_id: str
    patient: PatientProfile


class EligibilityFinding(BaseModel):
    factor: str
    status: Literal["pass", "fail", "unknown"]
    detail: str


class EligibilityResponse(BaseModel):
    trial_id: str
    overall: Literal["likely_eligible", "likely_ineligible", "needs_review"]
    findings: list[EligibilityFinding]


def check_eligibility(trials: list[Trial], req: EligibilityRequest) -> EligibilityResponse:
    trial = next((t for t in trials if t.id == req.trial_id), None)
    if trial is None:
        raise HTTPException(status_code=404, detail=f"Trial {req.trial_id} not found")

    findings: list[EligibilityFinding] = []
    failures = 0

    if trial.age_min <= req.patient.age <= trial.age_max:
        findings.append(
            EligibilityFinding(
                factor="age",
                status="pass",
                detail=f"Age {req.patient.age} in range {trial.age_min}-{trial.age_max}",
            )
        )
    else:
        failures += 1
        findings.append(
            EligibilityFinding(
                factor="age",
                status="fail",
                detail=f"Age {req.patient.age} outside range {trial.age_min}-{trial.age_max}",
            )
        )

    if trial.sex == "all" or trial.sex == req.patient.sex:
        findings.append(
            EligibilityFinding(
                factor="sex",
                status="pass",
                detail=f"Trial accepts {trial.sex}; patient is {req.patient.sex}",
            )
        )
    else:
        failures += 1
        findings.append(
            EligibilityFinding(
                factor="sex",
                status="fail",
                detail=f"Trial requires {trial.sex}; patient is {req.patient.sex}",
            )
        )

    cond = req.patient.primary_condition.lower()
    if cond and (cond in trial.condition.lower() or cond in trial.title.lower()):
        findings.append(
            EligibilityFinding(
                factor="condition",
                status="pass",
                detail=f"Condition '{req.patient.primary_condition}' matches '{trial.condition}'",
            )
        )
    else:
        findings.append(
            EligibilityFinding(
                factor="condition",
                status="unknown",
                detail=(
                    f"Condition '{req.patient.primary_condition}' did not obviously match "
                    f"'{trial.condition}'. Manual review needed."
                ),
            )
        )

    if req.patient.location and trial.location:
        if req.patient.location.lower() in trial.location.lower():
            findings.append(
                EligibilityFinding(
                    factor="location",
                    status="pass",
                    detail=f"Patient near {trial.location}",
                )
            )
        else:
            findings.append(
                EligibilityFinding(
                    factor="location",
                    status="unknown",
                    detail=(
                        f"Trial site is {trial.location}; patient location "
                        f"'{req.patient.location}' may require travel."
                    ),
                )
            )

    if failures > 0:
        overall: Literal["likely_eligible", "likely_ineligible", "needs_review"] = (
            "likely_ineligible"
        )
    elif any(f.status == "unknown" for f in findings):
        overall = "needs_review"
    else:
        overall = "likely_eligible"

    return EligibilityResponse(trial_id=trial.id, overall=overall, findings=findings)
