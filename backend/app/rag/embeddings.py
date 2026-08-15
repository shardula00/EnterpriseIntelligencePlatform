"""Embedding provider abstraction.

    EmbeddingProvider
        embed_documents(texts) -> list[vector]   # one call, many chunks
        embed_query(text)      -> vector

Two implementations:

- HashingEmbeddingProvider (default, "hashing"). A deterministic feature-
  hashing embedding (scikit-learn's HashingVectorizer, already a project
  dependency - no new package, no model download, no network access, no
  API key). It captures shared-vocabulary similarity well enough for a
  small enterprise document set (which is exactly this project's scale and
  exactly what the deterministic eval fixtures in tests/fixtures/rag/ are
  designed around) but it is NOT a semantic embedding model - it has no
  notion of synonyms or meaning beyond word overlap. This is the honest
  tradeoff documented in backend/README.md's Phase 7 section, made
  deliberately so the whole RAG pipeline is testable and runnable with
  zero downloads and zero cost (see Phase 7's resource-safety requirement).

- SentenceTransformerEmbeddingProvider (opt-in, "sentence_transformers").
  A real local semantic embedding model (all-MiniLM-L6-v2 by default, ~90MB
  download on first use) via the `sentence-transformers` package, which is
  NOT in requirements.txt - installing it (and the torch it pulls in) is a
  deliberate, documented opt-in (`pip install sentence-transformers`), not
  a default, per Phase 7's "do not download huge models unnecessarily"
  requirement. Selecting this provider without the package installed
  raises a clear configuration error rather than an opaque ImportError deep
  in a request.

Both providers produce the same fixed dimension (Settings.
rag_embedding_dimension, 384 - all-MiniLM-L6-v2's own real dimension, so
switching providers later never requires a migration) and L2-normalized
vectors, so pgvector's cosine distance behaves identically regardless of
which provider produced a given chunk's embedding.
"""

from abc import ABC, abstractmethod

from sklearn.feature_extraction.text import HashingVectorizer

from app.config import Settings
from app.rag.errors import RagError


class EmbeddingProvider(ABC):
    #: A short, stable identifier persisted on every chunk it embeds
    #: (DocumentChunk.embedding_model) - not necessarily a real "model
    #: name" for providers that aren't a trained model (e.g. hashing).
    name: str

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed one or more chunks of document text."""

    @abstractmethod
    def embed_query(self, text: str) -> list[float]:
        """Embed a user's question. Kept as a separate method (not just
        embed_documents([text])[0]) because some real embedding models use
        a different prefix/instruction for queries vs. documents - this
        provider is symmetric, but the interface doesn't assume every
        future provider will be."""


class HashingEmbeddingProvider(EmbeddingProvider):
    def __init__(self, dimension: int):
        self.dimension = dimension
        self.name = f"hashing-{dimension}"
        # norm="l2" (the default) makes cosine distance well-defined and
        # consistent across every embedding this provider produces.
        # stop_words="english" matters more than it would for a semantic
        # model: without it, shared function words ("the", "of", "is")
        # alone inflate cosine similarity between genuinely unrelated
        # text, which a hashing/word-overlap embedding has no other way
        # to discount.
        self._vectorizer = HashingVectorizer(
            n_features=dimension, alternate_sign=True, stop_words="english"
        )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        matrix = self._vectorizer.transform(texts)
        return matrix.toarray().tolist()

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


class SentenceTransformerEmbeddingProvider(EmbeddingProvider):
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RagError(
                "RAG_EMBEDDING_PROVIDER=sentence_transformers requires the "
                "'sentence-transformers' package, which is not installed. "
                "Run `pip install sentence-transformers` (this will also "
                "install torch - see backend/README.md's Phase 7 section "
                "for the resource tradeoff) or switch back to the default "
                "'hashing' provider."
            ) from exc
        self.name = model_name
        self._model = SentenceTransformer(model_name)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._model.encode(texts, normalize_embeddings=True).tolist()

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


def get_embedding_provider(settings: Settings) -> EmbeddingProvider:
    if settings.rag_embedding_provider == "hashing":
        return HashingEmbeddingProvider(settings.rag_embedding_dimension)
    if settings.rag_embedding_provider == "sentence_transformers":
        return SentenceTransformerEmbeddingProvider()
    raise RagError(
        f"Unknown RAG_EMBEDDING_PROVIDER '{settings.rag_embedding_provider}'. "
        "Supported: 'hashing', 'sentence_transformers'."
    )
