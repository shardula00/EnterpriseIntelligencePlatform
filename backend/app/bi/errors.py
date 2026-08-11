"""Exceptions raised by the BI/KPI module."""


class InvalidKpiRequestError(Exception):
    """Raised when a requested column/aggregation/granularity isn't valid
    for the target dataset (e.g. an unknown column, or a non-numeric metric)."""
