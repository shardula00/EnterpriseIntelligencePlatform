"""Exceptions raised by the knowledge graph package.

Deliberately thin: dataset lookup for the build endpoint reuses
app.ingestion.errors.DatasetNotFoundError (the same error every other
dataset-scoped endpoint already maps to a 404 with - no reason to invent a
second one), and graph_retrieval.retrieve() never raises for "nothing
matched" - see its own docstring for why that's a normal, honest outcome
rather than an error.
"""


class KgError(Exception):
    """Base class for all knowledge graph failures."""
