"""Knowledge graph & hybrid retrieval (Phase 9): structured entity/
relationship data derived from ingested dataset data, queried alongside
Phase 7's vector retrieval - built as a sibling to `app/rag/` and
`app/analytics/`, not merged into either. Ingestion/BI/ML answer
"what can we learn from structured data," RAG answers "what can we answer
from unstructured documents"; this package answers "what do we know about
how the *entities* in our structured data relate to each other," and
lets a RAG question draw on both kinds of evidence at once.

Module map:
    errors.py            - exception hierarchy
    schemas.py            - Pydantic response contract for the build endpoint
    entity_extraction.py   - dataset columns/rows -> Entity/Relationship rows
                             (the "population" step)
    graph_retrieval.py     - question -> matched entities -> connected facts,
                             packaged as app.rag.retrieval.RetrievedChunk so
                             app/rag/llm.py and app/rag/service.py need no
                             changes to consume either kind of evidence
    service.py             - the only module app/api/kg.py and
                             app/rag/service.py call

Pipeline: POST /datasets/{id}/graph/build -> detect which text/boolean
columns look like Customer/Product/Category/Region -> one Order entity per
row (the hub) -> one HAS_<TYPE> relationship per row per detected column -
every relationship is a literal fact copied from one source row, never a
pre-computed/inferred edge between two leaf entities (see
entity_extraction.py's docstring for why). Query: a hybrid-mode RAG
question -> scan for any known entity *name* literally mentioned in the
question text -> its directly-connected entities via shared Order edges ->
one evidence block per match, or none if nothing matches (an honest
"no useful graph answer," not an error).

Deliberately NOT implemented (see DEVELOPMENT_PLAN.md's Phase 9 section
and the approved Phase 9 design proposal):
    - Neo4j or any dedicated graph database - entities/relationships are
      plain Postgres tables (`kg_entities`/`kg_relationships`), joined
      like any other table. ARCHITECTURE.md §6/§7 already committed to
      trying this first; nothing here has hit a SQL traversal query that's
      actually awkward enough to justify a second database.
    - Automatic graph population at ingestion time. Building a dataset's
      graph is a separate, explicit action (POST /datasets/{id}/graph/build),
      mirroring RAG's own upload -> process split - Phase 2's ingestion
      pipeline is untouched.
    - Pre-computed/inferred relationships (e.g. a materialized
      Product -> Category edge derived from "every row where Product=X has
      Category=Y"). Only relationships that are literal facts already
      present in a source row are stored - multi-hop questions are
      answered by traversing through the Order hub at query time instead.
    - A standalone graph-browsing API. Graph evidence only ever surfaces
      as citations inside a hybrid-mode POST /rag/query response.
    - Per-user ownership of entities/relationships. Like Dataset itself
      (and unlike RAG documents - see app/rag/__init__.py), the knowledge
      graph is global/org-wide: built from a dataset anyone with
      dataset:read can already query, visible to anyone whose RAG query
      runs in hybrid mode.
"""
