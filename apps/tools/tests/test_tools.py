from tools.eligibility import EligibilityRequest, PatientProfile, check_eligibility
from tools.trial_search import SearchRequest, load_trials, search_trials, summarize_trial

TRIALS = load_trials()


def test_load_trials_count() -> None:
    assert len(TRIALS) >= 25


def test_search_by_condition() -> None:
    res = search_trials(TRIALS, SearchRequest(condition="lung cancer"))
    assert res.count >= 1
    assert any("NSCLC" in r.title for r in res.results)


def test_search_filters_age_and_sex() -> None:
    res = search_trials(
        TRIALS,
        SearchRequest(condition="postpartum", age=30, sex="female"),
    )
    assert res.count >= 1
    assert all(r.sex in ("female", "all") for r in res.results)


def test_search_no_match() -> None:
    res = search_trials(TRIALS, SearchRequest(condition="zzz_no_match_zzz"))
    assert res.count == 0


def test_summarize_trial_ok() -> None:
    summary = summarize_trial(TRIALS, TRIALS[0].id)
    assert summary.id == TRIALS[0].id


def test_eligibility_pass() -> None:
    profile = PatientProfile(age=55, sex="male", primary_condition="NSCLC", location="Boston")
    res = check_eligibility(
        TRIALS, EligibilityRequest(trial_id="TM-2025-001", patient=profile)
    )
    assert res.overall in ("likely_eligible", "needs_review")
    assert any(f.factor == "age" and f.status == "pass" for f in res.findings)


def test_eligibility_fail_on_age() -> None:
    profile = PatientProfile(age=10, sex="male", primary_condition="NSCLC")
    res = check_eligibility(
        TRIALS, EligibilityRequest(trial_id="TM-2025-001", patient=profile)
    )
    assert res.overall == "likely_ineligible"
    assert any(f.factor == "age" and f.status == "fail" for f in res.findings)
