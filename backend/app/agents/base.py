"""Shared result shapes every agent returns.

Deliberately plain dataclasses, not a generic Tool-registry/dispatch
framework - this is a hand-rolled, deterministic system (see
app/agents/__init__.py), and a dynamic plugin mechanism would be
infrastructure the approved Phase 10 design explicitly said not to add.
Each agent module instead exposes a small, fixed number of clearly-named
functions (its "tools"), directly callable by tests and by
orchestrator.py alike.
"""

from dataclasses import dataclass, field
from typing import Any, Literal

Severity = Literal["info", "warning", "critical"]

_SEVERITY_RANK: dict[Severity, int] = {"info": 0, "warning": 1, "critical": 2}


@dataclass
class ToolOutcome:
    """The result of one agent tool call.

    `allowed` is strictly about *permission* - False only when the current
    user lacks the domain permission the equivalent direct API endpoint
    would also require (see each agent module's own permission map).
    Any other reason a tool couldn't produce a real answer (no dataset_id
    given, dataset not suitable, nothing matched) is communicated through
    `summary`/`data` with `allowed=True`, so a permission-filtering test
    can check `allowed` specifically without it being conflated with
    "the answer happened to be empty."
    """

    tool: str
    allowed: bool
    summary: str
    data: dict[str, Any] | None = None


@dataclass
class AgentOutcome:
    agent: str
    outcomes: list[ToolOutcome] = field(default_factory=list)


@dataclass
class RiskFlag:
    severity: Severity
    message: str
    source: str  # "forecast_trend" | "forecast_uncertainty" | "monitoring_event" | "none"


def highest_severity(flags: list[RiskFlag]) -> Severity:
    if not flags:
        return "info"
    return max((f.severity for f in flags), key=lambda s: _SEVERITY_RANK[s])
