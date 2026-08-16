"""Exceptions raised by the Decision Intelligence package.

Deliberately thin: dataset lookup reuses
app.ingestion.errors.DatasetNotFoundError (the same error every other
dataset-scoped endpoint already maps to a 404 with), and a scenario that
can't be computed is never an exception - it's an honest
ScenarioResult(computed=False, reason=...) (see scenario.py), the same
"never raise for an expected failure mode" philosophy every other Phase
7-10 service already uses.
"""


class DecisionError(Exception):
    """Base class for all Decision Intelligence failures."""


class RecommendationNotFoundError(DecisionError):
    """Raised when a recommendation id doesn't exist."""


class InvalidDecisionActionError(DecisionError):
    """Raised when approve/reject is attempted on a recommendation that's
    no longer "pending" - a decision, once made, is not silently
    overwritten by a second one."""
