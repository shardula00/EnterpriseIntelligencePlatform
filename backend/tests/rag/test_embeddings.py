"""Unit tests for app/rag/embeddings.py - no database, no network, no model
download (the default "hashing" provider needs neither)."""

import math

import pytest

from app.config import Settings
from app.rag.embeddings import HashingEmbeddingProvider, get_embedding_provider
from app.rag.errors import RagError


def test_hashing_provider_produces_the_configured_dimension():
    provider = HashingEmbeddingProvider(dimension=384)
    vectors = provider.embed_documents(["hello world", "second document"])
    assert len(vectors) == 2
    assert all(len(v) == 384 for v in vectors)


def test_hashing_provider_is_deterministic():
    provider = HashingEmbeddingProvider(dimension=384)
    first = provider.embed_query("What is the vacation policy?")
    second = provider.embed_query("What is the vacation policy?")
    assert first == second


def test_hashing_provider_embed_query_matches_embed_documents_for_the_same_text():
    provider = HashingEmbeddingProvider(dimension=384)
    assert provider.embed_query("hello world") == provider.embed_documents(["hello world"])[0]


def test_hashing_provider_vectors_are_l2_normalized():
    provider = HashingEmbeddingProvider(dimension=384)
    vector = provider.embed_query("some reasonably long piece of document text")
    norm = math.sqrt(sum(v * v for v in vector))
    assert norm == pytest.approx(1.0, abs=1e-6)


def test_hashing_provider_handles_empty_string_without_crashing():
    provider = HashingEmbeddingProvider(dimension=384)
    vector = provider.embed_query("")
    assert len(vector) == 384
    assert all(v == 0.0 for v in vector)


def test_similar_texts_score_higher_than_unrelated_texts():
    """Not a semantic model, but shared vocabulary should still pull
    cosine similarity up - the whole retrieval pipeline depends on this
    being true for at least word-overlap-level similarity."""
    provider = HashingEmbeddingProvider(dimension=384)
    query = provider.embed_query("How many vacation days do employees get?")
    related = provider.embed_documents(
        ["Employees receive 20 vacation days per year, granted annually."]
    )[0]
    unrelated = provider.embed_documents(
        ["The quarterly revenue report shows strong growth in the APAC region."]
    )[0]

    def cosine(a, b):
        return sum(x * y for x, y in zip(a, b, strict=True))  # both already L2-normalized

    assert cosine(query, related) > cosine(query, unrelated)


def test_get_embedding_provider_defaults_to_hashing():
    settings = Settings(rag_embedding_provider="hashing", rag_embedding_dimension=384)
    provider = get_embedding_provider(settings)
    assert isinstance(provider, HashingEmbeddingProvider)
    assert provider.name == "hashing-384"


def test_get_embedding_provider_rejects_an_unknown_provider_name():
    settings = Settings(rag_embedding_provider="not-a-real-provider")
    with pytest.raises(RagError):
        get_embedding_provider(settings)


def test_sentence_transformers_provider_raises_a_clear_error_when_not_installed():
    """sentence-transformers is a deliberate opt-in, not a project
    dependency (see app/rag/embeddings.py) - selecting it without
    installing it must fail with an explicit, actionable message, not an
    opaque ImportError deep in a request."""
    settings = Settings(rag_embedding_provider="sentence_transformers")
    try:
        import sentence_transformers  # noqa: F401

        pytest.skip("sentence-transformers is installed in this environment")
    except ImportError:
        pass
    with pytest.raises(RagError, match="sentence-transformers"):
        get_embedding_provider(settings)
