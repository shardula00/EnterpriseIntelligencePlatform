"""Enterprise RAG foundation (Phase 7): document ingestion, chunking,
embeddings, vector retrieval, and grounded question-answering - built as a
sibling to `app/ml/` and `app/mlops/`, not inside either. Ingestion/ML/MLOps
answer "what can we learn from structured data"; this package answers "what
can we answer from unstructured enterprise documents, grounded in evidence
we can point back to."

Module map:
    errors.py      - exception hierarchy
    schemas.py     - Pydantic request/response contracts
    extraction.py  - safe per-format text extraction (PDF/DOCX/TXT/Markdown)
    chunking.py    - deterministic, provenance-preserving chunking
    embeddings.py  - EmbeddingProvider abstraction + implementations
    llm.py         - LLMProvider abstraction + implementations, and the
                     prompt-injection-safe prompt builder
    retrieval.py   - pgvector similarity search, access-scoped
    service.py     - the only module app/api/documents.py and app/api/rag.py
                     call; wires the above together with persistence

Pipeline: upload -> validate -> extract -> normalize -> chunk -> embed ->
store -> index. Query: question -> embed query -> vector search -> top-K
(access-scoped, threshold-filtered) -> build context -> LLM -> answer +
sources, or an explicit "insufficient evidence" result if nothing clears
the similarity threshold. The LLM is never given the question alone - see
service.run_query() and llm.build_prompt().

Deliberately NOT implemented (see DEVELOPMENT_PLAN.md's Phase 7 section):
    - A dedicated vector database (Pinecone/Weaviate/Qdrant/Chroma). The
      pgvector extension has been enabled in this project's Postgres since
      Phase 1 (see migrations/versions/43d2212be27c_*) specifically for
      this - one database to run and back up, joinable against every other
      table (e.g. an access-control filter is a normal SQL WHERE, not a
      second system's separate ACL layer).
    - Celery/Redis/async job processing. Document processing (extract ->
      chunk -> embed -> store) runs synchronously within one request, same
      documented tradeoff as Phase 5 training and Phase 6 monitoring checks
      at this project's data scale.
    - A required paid LLM/embedding API. The default embedding provider
      ("hashing") and LLM provider ("local_extractive") need no network
      access, no API key, and no model download - see embeddings.py and
      llm.py. Ollama and an OpenAI-compatible API are supported as opt-in
      config, never a requirement to run the project.
    - Cross-user document sharing/ACLs. A document is visible only to its
      uploader and to ADMIN users (see service.py's `_ensure_access`) -
      the simplest access model that satisfies "a user must not retrieve
      another user's document" without inventing a sharing/permissions UI
      this phase doesn't need. A future phase could add explicit sharing.
    - Knowledge graph / hybrid retrieval (Phase 9), agents (Phase 10) - RAG
      is a standalone capability here, composed by later phases, not
      pre-wired into either.
"""
