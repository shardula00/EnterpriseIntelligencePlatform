"""Natural-language business analytics (Phase 8): ask a plain-English
question about an already-ingested dataset and get back a real, executed,
read-only SQL result - built as a sibling to `app/bi/` (Phase 3's
configurable KPI engine), not a replacement for it. `app/bi/` answers "show
me the numbers this dataset's schema suggests"; this package answers "let
me ask my own question about it."

Module map:
    errors.py        - exception hierarchy
    schemas.py        - Pydantic request/response contracts
    nl_parser.py       - deterministic (no LLM) question -> ParsedIntent
    query_builder.py    - ParsedIntent -> a safe SQLAlchemy Core SELECT,
                          reusing app/bi/service.py's exact table-
                          reconstruction pattern
    sql_guard.py        - independent, defense-in-depth textual validation
                          of the rendered SQL before it's ever returned
    service.py          - the only module app/api/analytics.py calls; wires
                          the above together with AnalyticsQuery persistence

Pipeline: question + dataset_id -> parse (question -> intent, using only
that dataset's real, already-detected columns) -> build (intent -> a single
read-only SELECT via SQLAlchemy Core - never a hand-assembled SQL string)
-> guard (independent textual re-check) -> execute -> persist -> structured
result with the rendered SQL shown alongside it for transparency.

Deliberately NOT implemented in this first version (see
DEVELOPMENT_PLAN.md's Phase 8 section):
    - An LLM-backed generator. The default (and only) generator is
      deterministic pattern-matching against the dataset's real column
      metadata (see nl_parser.py) - zero cost, zero network, zero model
      download, and a stronger safety property than an LLM-produced SQL
      string would have: a question can only ever resolve to one of four
      closed-set query shapes, never arbitrary text. A future phase could
      add an opt-in LLM-backed parser behind the same ParsedIntent
      interface, the same way app/rag/embeddings.py and app/rag/llm.py
      offer opt-in real-model providers behind their own abstractions -
      nl_parser.parse()'s signature is already shaped to allow that.
    - Row-level filtering ("revenue in the West region"), multi-metric
      questions, or joins across datasets - out of scope for "select a
      dataset, ask an aggregate question about it."
    - Per-user query ownership. Like datasets themselves (see
      app/bi/service.py's docstring for the same point) and unlike RAG
      documents, analytics queries are visible to anyone with
      analytics:read - permission-gated, not ownership-scoped.
"""
