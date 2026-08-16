"""Unit tests for app/decision/recommendation.py - pure Python, no
database. Hand-crafted ToolOutcome/ScenarioResult inputs, same style
tests/agents/test_risk_agent.py already uses for its own deterministic
threshold coverage."""

from app.agents.base import ToolOutcome
from app.decision.recommendation import compose
from app.decision.scenario import ScenarioResult


def _ml_outcome(summary="Trained a forecast, trending up from 100 to 110.", has_ci=True):
    return ToolOutcome(
        tool="forecast", allowed=True, summary=summary,
        data={"run_id": "r1", "task_type": "forecasting", "has_confidence_interval": has_ci},
    )


def _risk_outcome(overall_severity):
    return ToolOutcome(
        tool="assess_risk", allowed=True, summary="...",
        data={"overall_severity": overall_severity, "flags": []},
    )


def test_critical_risk_yields_low_confidence_and_escalation_alternative():
    composed = compose(_ml_outcome(), _risk_outcome("critical"), None)
    assert composed.confidence == "low"
    assert "Investigate immediately" in composed.text
    assert any("Escalate" in alt for alt in composed.alternatives)
    assert "Take no action and continue monitoring." in composed.alternatives


def test_warning_risk_yields_medium_confidence():
    composed = compose(_ml_outcome(), _risk_outcome("warning"), None)
    assert composed.confidence == "medium"
    assert "Review closely" in composed.text


def test_declining_trend_with_no_risk_is_flagged_but_not_alarming():
    ml_outcome = _ml_outcome(summary="Trained a forecast, trending down from 100 to 80.")
    composed = compose(ml_outcome, _risk_outcome("info"), None)
    assert "declining" in composed.text.lower()
    assert composed.confidence in ("medium", "high")


def test_stable_forecast_with_no_risk_and_narrow_ci_is_high_confidence():
    composed = compose(_ml_outcome(has_ci=True), _risk_outcome("info"), None)
    assert composed.confidence == "high"
    assert "no significant risk" in composed.text.lower()


def test_no_ml_or_risk_context_yields_an_honest_not_enough_evidence_result():
    composed = compose(None, None, None)
    assert "not enough evidence" in composed.text.lower()
    assert any("no forecast was available" in a.lower() for a in composed.assumptions)
    assert any("no risk assessment was available" in a.lower() for a in composed.assumptions)


def test_risk_only_no_ml_still_produces_a_recommendation():
    composed = compose(None, _risk_outcome("warning"), None)
    assert composed.confidence == "medium"
    assert any("no forecast was available" in a.lower() for a in composed.assumptions)


def test_verified_scenario_boosts_confidence_and_is_named_in_assumptions():
    scenario_result = ScenarioResult(
        computed=True, question="q", affected_metric="profit", perturbed_metric="revenue",
        delta_percent=-10.0, relationship="profit = revenue - cost",
        note="This is a linear extrapolation using the verified relationship "
             "'profit = revenue - cost' over historical totals, not a causal or "
             "predictive model. Assumes 'cost' remains unchanged.",
    )
    composed = compose(None, None, scenario_result)
    assert composed.confidence == "high"
    assert any("linear extrapolation" in a.lower() for a in composed.assumptions)


def test_unverified_scenario_reason_is_recorded_as_an_assumption():
    scenario_result = ScenarioResult(
        computed=False, question="q", reason="No verified relationship could be found.",
    )
    composed = compose(None, None, scenario_result)
    assert any("could not be computed" in a.lower() for a in composed.assumptions)


def test_missing_trend_direction_is_named_as_an_assumption():
    ml_outcome = _ml_outcome(summary="Trained a forecast for 'revenue' over the next 14 period(s).")
    composed = compose(ml_outcome, None, None)
    assert any("trend direction could not be determined" in a.lower() for a in composed.assumptions)
