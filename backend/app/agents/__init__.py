"""Multi-agent workflows (Phase 10): compose the now-existing capabilities
(ingestion/BI, ML, MLOps, Analytics, RAG, Knowledge Graph) via a small set
of narrowly-scoped agents, coordinated by a hand-rolled, deterministic
orchestration layer - not a new framework, not a new database, not a new
LLM call. Every agent tool is a thin wrapper around a function that
already exists and already works standalone (Phase 2/3/5/6/7/8/9); this
package only ever *calls* those functions, in-process, never over HTTP to
this project's own API (see orchestrator.py).

Module map:
    errors.py         - exception hierarchy
    schemas.py         - Pydantic request/response contracts for
                         app/api/agents.py
    base.py             - ToolOutcome/AgentOutcome/RiskFlag: the shared
                         result shapes every agent returns
    data_agent.py        - read-only dataset/KPI tools (app.ingestion.service,
                         app.bi.service)
    analytics_agent.py    - Phase 8 NL analytics tool (app.analytics.service)
    ml_agent.py            - suitability + forecasting tool
                         (app.ml.service)
    research_agent.py      - Phase 7+9 hybrid RAG query tool
                         (app.rag.service - already hybrid-capable)
    risk_agent.py           - deterministic risk-flagging over an ML
                         forecast's own trend/confidence-interval data
                         and/or existing MonitoringEvent severity
                         (app.mlops.service) - explicitly NOT Phase 11's
                         Decision Intelligence (no recommendations, no
                         scenario simulation, no approval workflow)
    router.py               - deterministic keyword/domain matching -
                         question -> ordered list of agent names, same
                         "small synonym/keyword set, no LLM" approach
                         app/analytics/nl_parser.py and
                         app/kg/entity_extraction.py already established
    orchestrator.py          - the only module app/api/agents.py calls;
                         runs the routed plan, threads state between
                         agents (e.g. an ML forecast's run id -> Risk),
                         composes the final response

Pipeline: question (+ optional dataset_id) -> router (deterministic
keywords -> ordered agent names, or [] if nothing recognized - an honest
"I don't understand which capability this needs," never a guess) ->
orchestrator invokes each agent in order, passing a small mutable context
dict forward (e.g. ml_agent writes context["ml_run_id"], risk_agent reads
it) -> each agent tool independently re-checks the SAME permission the
equivalent direct API endpoint already requires, before doing any real
work - the agent layer is never a way to reach a capability a user
couldn't reach directly -> composed response: which agents ran, each
tool's own outcome, and a deterministic summary stitched from them.

Deliberately NOT implemented this phase (see the approved Phase 10 design
proposal and DEVELOPMENT_PLAN.md's Phase 10 section):
    - Visualization and Decision agents. Visualization has no backend
      capability to wrap (charts are pure frontend/Recharts, Phase 3) - an
      agent needs a tool surface *over an API*, and there is no
      server-side visualization service to expose one over. Decision
      requires Phase 11's not-yet-built recommendation/scenario-
      simulation/approval infrastructure - building it now would mean
      building Phase 11 early, which the Risk agent above is deliberately
      scoped short of doing.
    - Any agent framework (LangGraph, CrewAI, AutoGen, ...) - the router
      and orchestrator are both plain, deterministic Python, matching this
      project's consistent "no unnecessary infrastructure" precedent (no
      MLflow, no Neo4j, no Celery, no paid LLM by default).
    - An LLM call anywhere in routing or summary composition - the final
      summary is a deterministic template joining each agent's own
      already-human-readable tool summaries, not a natural-language
      synthesis. A real, documented trade-off, not an oversight.
    - A new `agent_runs` persistence table - every agent tool call
      delegates to a service that already persists its own result
      (ml_runs, rag_queries, analytics_queries); orchestration itself is
      captured by the existing AuditLog (AGENT_RUN_PERFORMED), not a new
      table duplicating data that's already stored once.
"""
