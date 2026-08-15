"""Exceptions raised by the natural-language analytics package."""


class AnalyticsError(Exception):
    """Base class for all analytics failures."""


class UnsupportedQuestionError(AnalyticsError):
    """Raised when a question cannot be confidently mapped to a known
    analytical pattern (see app/analytics/nl_parser.py) - e.g. no
    recognizable aggregation, or no dataset column matches what's being
    asked about. Caught by app/analytics/service.py and turned into a
    status="unsupported" result, never a 500 - an honest "I don't
    understand this question yet" is not a bug."""


class UnsafeSqlError(AnalyticsError):
    """Raised by app/analytics/sql_guard.py if the rendered SQL text ever
    fails its independent safety check - defense in depth, since
    app/analytics/query_builder.py can only structurally produce a single
    read-only SELECT in the first place (built via SQLAlchemy Core, never a
    hand-assembled string). Should never actually trigger in practice."""
