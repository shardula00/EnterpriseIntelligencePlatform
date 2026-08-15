"""Orchestration layer for the knowledge graph - the only module
app/api/kg.py and app/rag/service.py call directly.
"""

import uuid

from sqlalchemy.orm import Session

from app.ingestion import service as ingestion_service
from app.kg import graph_retrieval
from app.kg.entity_extraction import BuildResult, build_graph
from app.rag.retrieval import RetrievedChunk


def build_graph_for_dataset(db: Session, dataset_id: uuid.UUID) -> BuildResult:
    """Raises DatasetNotFoundError (app.ingestion.errors) if the dataset
    doesn't exist - the same error every other dataset-scoped endpoint
    already maps to a 404 with."""
    dataset = ingestion_service.get_dataset(db, dataset_id)
    columns = sorted(dataset.columns, key=lambda c: c.position)
    return build_graph(db, dataset, columns)


def retrieve_graph_evidence(db: Session, question: str, max_facts: int) -> list[RetrievedChunk]:
    return graph_retrieval.retrieve(db, question, max_facts)
