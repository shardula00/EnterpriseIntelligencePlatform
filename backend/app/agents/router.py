"""Deterministic question -> ordered agent names.

Same "match against a small, fixed keyword/synonym set, no LLM" approach
app/analytics/nl_parser.py and app/kg/entity_extraction.py already
established and proved out at this project's scale. Returns [] rather
than guessing when nothing recognizable matches - an honest "I don't
understand which capability this needs" (see orchestrator.py), never a
default fallback pretending to have understood.

ML and Risk are the only two agents that can appear together in one plan
today (the Phase 10 DoD scenario: "forecast ... and flag any risk
factors") - Analytics/Data/Research are mutually-exclusive fallbacks,
checked only when neither ML nor Risk matched, in a fixed priority order.
This is a deliberately simple v1 scope, not a general multi-domain planner
- see app/agents/__init__.py.

Phase 11: Decision keywords are checked *additionally*, never replacing
the above. If ML and/or Risk also matched, "decision" is appended after
them (the Phase 11 DoD scenario: "forecast ... and recommend an action if
there's a risk" -> ["ml", "risk", "decision"], so decision_agent can read
their already-produced output). If nothing else matched but decision
keywords did, the plan is ["decision"] alone (the Phase 11 what-if DoD
scenario: "what happens to profit if revenue decreases by 10%" has no
ml/risk/analytics keyword in it at all) - decision_agent then falls back
to a standalone scenario calculation. See app/agents/decision_agent.py.
"""

_ML_KEYWORDS = (
    "forecast", "predict", "prediction", "train a model", "train model",
    "classification", "classify", "cluster", "segment", "anomaly", "suitability",
    "suitable for",
)
_RISK_KEYWORDS = ("risk", "flag", "alert", "warning sign", "concern")
_DECISION_KEYWORDS = (
    "recommend", "recommendation", "should we", "what should", "decide", "decision",
    "what happens if", "what happens to", "what if",
)
_ANALYTICS_KEYWORDS = (
    "total", "sum of", "average", "how many", "breakdown", "top ", "trend",
    "monthly", "weekly", "by region", "by category", "by product",
)
_DATA_KEYWORDS = (
    "list dataset", "list datasets", "show dataset", "describe dataset", "columns",
    "schema", "preview", "quality score", "what datasets",
)
_RESEARCH_KEYWORDS = (
    "document", "policy", "handbook", "research", "knowledge graph", "explain",
    "according to",
)

AGENT_NAMES = ("data", "analytics", "ml", "research", "risk", "decision")


def route(question: str) -> list[str]:
    """Returns an ordered list of agent names the orchestrator should
    invoke, in that order. Never raises."""
    lowered = question.lower()

    ml_match = any(keyword in lowered for keyword in _ML_KEYWORDS)
    risk_match = any(keyword in lowered for keyword in _RISK_KEYWORDS)
    decision_match = any(keyword in lowered for keyword in _DECISION_KEYWORDS)

    plan: list[str] = []
    if ml_match:
        plan.append("ml")
    if risk_match:
        plan.append("risk")
    if plan:
        if decision_match:
            plan.append("decision")
        return plan

    if decision_match:
        return ["decision"]
    if any(keyword in lowered for keyword in _ANALYTICS_KEYWORDS):
        return ["analytics"]
    if any(keyword in lowered for keyword in _DATA_KEYWORDS):
        return ["data"]
    if any(keyword in lowered for keyword in _RESEARCH_KEYWORDS):
        return ["research"]
    return []
