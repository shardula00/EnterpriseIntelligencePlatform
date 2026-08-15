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
"""

_ML_KEYWORDS = (
    "forecast", "predict", "prediction", "train a model", "train model",
    "classification", "classify", "cluster", "segment", "anomaly", "suitability",
    "suitable for",
)
_RISK_KEYWORDS = ("risk", "flag", "alert", "warning sign", "concern")
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

AGENT_NAMES = ("data", "analytics", "ml", "research", "risk")


def route(question: str) -> list[str]:
    """Returns an ordered list of agent names the orchestrator should
    invoke, in that order. Never raises."""
    lowered = question.lower()

    ml_match = any(keyword in lowered for keyword in _ML_KEYWORDS)
    risk_match = any(keyword in lowered for keyword in _RISK_KEYWORDS)

    plan: list[str] = []
    if ml_match:
        plan.append("ml")
    if risk_match:
        plan.append("risk")
    if plan:
        return plan

    if any(keyword in lowered for keyword in _ANALYTICS_KEYWORDS):
        return ["analytics"]
    if any(keyword in lowered for keyword in _DATA_KEYWORDS):
        return ["data"]
    if any(keyword in lowered for keyword in _RESEARCH_KEYWORDS):
        return ["research"]
    return []
