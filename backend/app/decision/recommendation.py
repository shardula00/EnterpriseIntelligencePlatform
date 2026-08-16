"""Deterministic recommendation composition. No LLM.

Given the ML forecast's own ToolOutcome, the Risk agent's own ToolOutcome,
and (optionally) a verified ScenarioResult, produces a short recommendation
sentence, a small fixed set of alternatives, an explicit assumptions list,
and a coarse confidence label - via a fixed rule table, not a generative
process. Risk data is read from Risk's own `overall_severity`, never
recomputed or re-represented (see app/agents/risk_agent.py) - this module
composes, it does not re-derive.
"""

from dataclasses import dataclass, field

from app.agents.base import ToolOutcome
from app.decision.scenario import ScenarioResult

_NO_ACTION = "Take no action and continue monitoring."


@dataclass
class ComposedRecommendation:
    text: str
    alternatives: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    confidence: str = "medium"  # "low" | "medium" | "high"


def _trend_direction(ml_outcome: ToolOutcome | None) -> str | None:
    """ml_agent.py's forecast tool only exposes trend direction inside its
    human-readable `summary` string, not as a structured field - parsed
    defensively here rather than modifying ml_agent.py (out of scope for
    Phase 11, see the approved design proposal)."""
    if ml_outcome is None:
        return None
    summary = ml_outcome.summary.lower()
    if "trending up" in summary:
        return "up"
    if "trending down" in summary:
        return "down"
    if "trending flat" in summary:
        return "flat"
    return None


def _overall_severity(risk_outcome: ToolOutcome | None) -> str:
    if risk_outcome is not None and risk_outcome.data:
        return risk_outcome.data.get("overall_severity", "info")
    return "info"


def compose(
    ml_outcome: ToolOutcome | None,
    risk_outcome: ToolOutcome | None,
    scenario_result: ScenarioResult | None,
) -> ComposedRecommendation:
    severity = _overall_severity(risk_outcome)
    trend = _trend_direction(ml_outcome)

    assumptions: list[str] = []
    if ml_outcome is None:
        assumptions.append(
            "No forecast was available - this recommendation is based on risk/monitoring signals only."
        )
    if risk_outcome is None:
        assumptions.append("No risk assessment was available for this recommendation.")
    if ml_outcome is not None and trend is None:
        assumptions.append("The forecast's trend direction could not be determined from its own output.")
    if scenario_result is not None and scenario_result.computed:
        assumptions.append(
            scenario_result.note
            or "Scenario impact is a linear extrapolation over verified historical totals, not a causal prediction."
        )
    elif scenario_result is not None and not scenario_result.computed and scenario_result.reason:
        assumptions.append(f"Requested what-if scenario could not be computed: {scenario_result.reason}")

    if severity == "critical":
        text = (
            "Investigate immediately - a critical risk signal was detected. "
            "Avoid acting on this forecast until it has been reviewed."
        )
        alternatives = [_NO_ACTION, "Escalate to a domain expert before proceeding"]
    elif severity == "warning":
        text = "Review closely before acting - a notable risk signal was detected."
        alternatives = [_NO_ACTION, "Proceed with a smaller, partial action and reassess"]
    elif trend == "down":
        text = "No critical risk was detected, but the forecast trend is declining - monitor closely."
        alternatives = [_NO_ACTION]
    elif trend in ("up", "flat"):
        text = "No significant risk signals were detected; the current approach appears reasonable to continue."
        alternatives = [_NO_ACTION]
    else:
        text = "Not enough evidence was available to generate a specific recommendation beyond monitoring."
        alternatives = [_NO_ACTION]

    has_narrow_ci = bool(ml_outcome and ml_outcome.data and ml_outcome.data.get("has_confidence_interval"))
    verified_scenario = bool(scenario_result and scenario_result.computed)
    if severity == "critical":
        confidence = "low"
    elif severity == "warning":
        confidence = "medium"
    elif has_narrow_ci or verified_scenario:
        confidence = "high"
    else:
        confidence = "medium"

    return ComposedRecommendation(
        text=text, alternatives=alternatives, assumptions=assumptions, confidence=confidence
    )
