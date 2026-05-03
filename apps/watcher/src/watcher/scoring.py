"""Local-model scoring client.

Calls the in-cluster aikit/llama.cpp endpoint (OpenAI-compatible) to score how
well a clinical trial matches a patient profile. Returns a `(score, reason)`
tuple. Defensive parsing — the small model may emit prose around its JSON.
"""

from __future__ import annotations

import json
import logging
import re

import httpx

from .settings import settings

log = logging.getLogger("watcher.scoring")

_SYSTEM_PROMPT = (
    "You score how well a clinical trial matches a patient profile.\n"
    "You are given pre-computed VERDICTS for hard eligibility checks "
    "(age in range, sex match, location match) — treat these as GROUND TRUTH. "
    "Do not contradict them or re-derive them yourself.\n"
    "Use the verdicts plus the condition / title / criteria text to judge soft fit.\n"
    "Respond ONLY with compact JSON of the form: "
    '{"score": <0-100>, "reason": "<one short sentence>"}.\n'
    "Scoring guide: 90-100 all hard verdicts match AND condition is a strong fit; "
    "70-89 all hard verdicts match but condition fit is partial; "
    "40-69 one hard verdict fails; 0-39 condition unrelated or multiple hard fails.\n"
    "No preamble, no markdown, no extra keys."
)


def _hard_facts(profile: dict, trial: dict) -> dict:
    """Compute deterministic eligibility checks the LLM should not re-derive."""
    facts: dict = {
        "age_in_range": None,
        "sex_match": None,
        "location_match": None,
    }
    age = profile.get("age")
    age_range = trial.get("age_range") or ""
    if isinstance(age, int) and "-" in age_range:
        try:
            lo, hi = (int(x) for x in age_range.split("-", 1))
            facts["age_in_range"] = lo <= age <= hi
            facts["_age_detail"] = f"patient {age} vs trial {lo}-{hi}"
        except ValueError:
            pass

    p_sex = (profile.get("sex") or "").lower().strip() or None
    t_sex = (trial.get("sex") or "").lower().strip() or None
    if p_sex and t_sex:
        facts["sex_match"] = t_sex == "all" or p_sex == t_sex
        facts["_sex_detail"] = f"patient {p_sex} vs trial {t_sex}"

    p_loc = (profile.get("location") or "").lower().strip()
    t_loc = (trial.get("location") or "").lower().strip()
    if p_loc and t_loc:
        # Loose: any token from the patient location appears in the trial location.
        toks = [t for t in p_loc.replace(",", " ").split() if len(t) > 2]
        facts["location_match"] = any(t in t_loc for t in toks) if toks else None
        facts["_loc_detail"] = f"patient {p_loc!r} vs trial {t_loc!r}"

    return facts


def _facts_block(facts: dict) -> str:
    def verdict(v: bool | None) -> str:
        if v is True:
            return "MATCH"
        if v is False:
            return "FAIL"
        return "unknown"

    lines = ["Verdicts (computed, ground truth):"]
    if facts["age_in_range"] is not None:
        lines.append(f"  age_in_range: {verdict(facts['age_in_range'])}  ({facts.get('_age_detail', '')})")
    if facts["sex_match"] is not None:
        lines.append(f"  sex_match:    {verdict(facts['sex_match'])}  ({facts.get('_sex_detail', '')})")
    if facts["location_match"] is not None:
        lines.append(f"  location_match: {verdict(facts['location_match'])}  ({facts.get('_loc_detail', '')})")
    return "\n".join(lines)


def _build_user_prompt(profile: dict, trial: dict, facts: dict) -> str:
    p = profile
    parts: list[str] = ["Patient:"]
    if "age" in p:
        parts.append(f"  age: {p['age']}")
    if "sex" in p:
        parts.append(f"  sex: {p['sex']}")
    if "condition" in p:
        parts.append(f"  condition: {p['condition']}")
    if "stage" in p:
        parts.append(f"  stage: {p['stage']}")
    if "location" in p:
        parts.append(f"  location: {p['location']}")
    if p.get("prior_treatments"):
        parts.append(f"  prior treatments: {', '.join(p['prior_treatments'])}")

    parts.append("")
    parts.append("Trial:")
    parts.append(f"  id: {trial.get('id', '?')}")
    parts.append(f"  title: {trial.get('title', '?')}")
    parts.append(f"  condition: {trial.get('condition', '?')}")
    parts.append(f"  phase: {trial.get('phase', '?')}")
    parts.append(f"  location: {trial.get('location', '?')}")
    parts.append(f"  age range: {trial.get('age_range', '?')}")
    parts.append(f"  sex: {trial.get('sex', '?')}")

    parts.append("")
    parts.append(_facts_block(facts))
    return "\n".join(parts)


_JSON_RE = re.compile(r"\{[^{}]*\}", re.DOTALL)


def _extract_json(text: str) -> dict:
    """Pull the first JSON object out of a model response."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = _JSON_RE.search(text)
    if not m:
        raise ValueError(f"no JSON found in model response: {text!r}")
    return json.loads(m.group(0))


async def score_match(
    client: httpx.AsyncClient, profile: dict, trial: dict
) -> tuple[int, str]:
    """Return (score 0-100, reason) for one (profile, trial) pair."""
    facts = _hard_facts(profile, trial)
    payload = {
        "model": settings.local_model_name,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(profile, trial, facts)},
        ],
        "max_tokens": 120,
        # Deterministic: same (profile, trial) → same score. Deltas in the UI
        # only fire when the underlying data actually changes (new trial,
        # edited profile).
        "temperature": 0,
    }
    r = await client.post(
        f"{settings.local_model_url}/v1/chat/completions",
        json=payload,
        timeout=settings.score_timeout_seconds,
    )
    r.raise_for_status()
    body = r.json()
    raw = body["choices"][0]["message"]["content"]

    try:
        parsed = _extract_json(raw)
        score = int(parsed.get("score", 0))
        reason = str(parsed.get("reason", "")).strip()
    except Exception as exc:  # noqa: BLE001 — defensive against any small-model weirdness
        log.warning("score parse failed (%s); raw=%r", exc, raw)
        return (0, f"unparseable model output: {raw[:80]}")

    score = max(0, min(100, score))
    score, reason = _apply_hard_facts(score, reason, facts)
    return score, reason or "(no reason given)"


def _apply_hard_facts(score: int, reason: str, facts: dict) -> tuple[int, str]:
    """Clamp the model's score against deterministic eligibility verdicts.

    The 3B model occasionally hallucinates an age/sex mismatch. If our
    pre-computed verdicts say all hard checks pass, refuse to drop the score
    below 80 and rewrite a reason that mentions a hard fail. If a hard check
    actually fails, ceiling the score at 60.
    """
    hard = [facts.get("age_in_range"), facts.get("sex_match"), facts.get("location_match")]
    known = [v for v in hard if v is not None]
    if not known:
        return score, reason

    all_pass = all(v is True for v in known)
    any_fail = any(v is False for v in known)
    rl = reason.lower()
    mentions_age = "age" in rl
    mentions_sex = "sex" in rl or "gender" in rl
    mentions_loc = "location" in rl or "site" in rl

    if all_pass:
        # Strip phantom mismatch language; floor the score.
        if (mentions_age and facts.get("age_in_range")) or (
            mentions_sex and facts.get("sex_match")
        ) or (mentions_loc and facts.get("location_match")):
            reason = "Age, sex, and location all match — eligibility looks strong on hard criteria."
        if score < 80:
            score = 80
    elif any_fail and score > 60:
        score = 60

    return score, reason
