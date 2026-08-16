"""Unit tests for app/agents/router.py - pure Python, no database."""

from app.agents.router import route


def test_the_phase_10_dod_scenario_routes_to_ml_then_risk():
    plan = route("Forecast next quarter's revenue and flag any risk factors.")
    assert plan == ["ml", "risk"]


def test_risk_alone_routes_to_risk_only():
    plan = route("Are there any risk factors I should be concerned about?")
    assert plan == ["risk"]


def test_forecast_alone_routes_to_ml_only():
    plan = route("Please forecast sales for the next 30 days.")
    assert plan == ["ml"]


def test_total_question_routes_to_analytics():
    plan = route("What is the total revenue?")
    assert plan == ["analytics"]


def test_breakdown_question_routes_to_analytics():
    plan = route("Show total quantity by region.")
    assert plan == ["analytics"]


def test_list_datasets_question_routes_to_data():
    plan = route("List datasets available in the platform.")
    assert plan == ["data"]


def test_describe_dataset_question_routes_to_data():
    plan = route("Describe dataset columns and schema.")
    assert plan == ["data"]


def test_document_question_routes_to_research():
    plan = route("What does the employee handbook policy say about vacation days?")
    assert plan == ["research"]


def test_unrecognized_question_returns_an_empty_plan():
    assert route("asdkjfh qpwoeiru zxcvb nonsense") == []


def test_empty_question_returns_an_empty_plan():
    assert route("") == []


def test_ml_keywords_take_priority_over_analytics_keywords():
    # "predict" (ML) and "total" (analytics) both appear - ML wins per the
    # documented fixed priority order.
    plan = route("predict the total revenue trend")
    assert plan == ["ml"]


# ---------------------------------------------------------------------------
# Phase 11: decision routing (additive - must not change any of the above)
# ---------------------------------------------------------------------------


def test_the_phase_11_dod_scenario_routes_to_ml_risk_then_decision():
    plan = route("Forecast next quarter's revenue and recommend an action if there's a risk")
    assert plan == ["ml", "risk", "decision"]


def test_standalone_what_if_question_routes_to_decision_only():
    plan = route("What happens to profit if revenue decreases by 10%?")
    assert plan == ["decision"]


def test_recommend_alone_with_no_ml_or_risk_keyword_routes_to_decision_only():
    plan = route("What should we do about this dataset?")
    assert plan == ["decision"]


def test_decision_is_appended_after_risk_alone_when_both_match():
    plan = route("Are there any risk factors, and what should we do about them?")
    assert plan == ["risk", "decision"]


def test_the_phase_10_dod_scenario_still_has_no_decision_agent():
    # Regression: this exact Phase 10 question has no decision keyword in
    # it and must route exactly as it did before Phase 11 existed.
    plan = route("Forecast next quarter's revenue and flag any risk factors.")
    assert plan == ["ml", "risk"]
