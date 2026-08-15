"""Exceptions raised by the multi-agent orchestration package.

Deliberately thin: a dataset lookup failure inside an agent tool reuses
app.ingestion.errors.DatasetNotFoundError (the same error every other
dataset-scoped endpoint already maps to a 404 with), and "the router
didn't recognize this request" is not an exception at all - it's an
honest status="unsupported" result (see orchestrator.py), the same
"never raise for an expected failure mode" philosophy app/rag/service.py
and app/analytics/service.py already use.
"""


class AgentError(Exception):
    """Base class for all agent orchestration failures."""
