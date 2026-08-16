"""Decision Intelligence (Phase 11): turns Analytics/ML/Risk output into
an accountable recommendation, with a human approval workflow before
anything is treated as acted-on.

This is a composition layer, not a new analysis capability - it does not
re-derive facts Phase 8 (Analytics)/Phase 9 (KG)/Phase 10 (ML/Risk) already
compute. Two genuinely new things exist here that nothing else in this
project already provides:

    1. A verified-relationship "what-if" scenario calculator
       (scenario.py) - given a question like "what happens to profit if
       revenue decreases by 10%", it gets real baseline totals from
       app.analytics.query_builder (reused directly, never reimplemented),
       then EMPIRICALLY VERIFIES a linear relationship between the named
       metrics against the dataset's actual rows before using it - the
       same "verify, don't assume" discipline app/kg/entity_extraction.py
       already applies to relationship data. If no such relationship can
       be verified, this honestly declines rather than fabricating a
       number. Always linear extrapolation over historical totals, never
       claimed to be causal or predictive.

    2. A deterministic recommendation composer (recommendation.py) - a
       fixed rule table over Risk's own `overall_severity` and the ML
       forecast's own trend direction, never an LLM (consistent with this
       project's zero-cost-by-default precedent everywhere else:
       app/rag/embeddings.py's "hashing" default, app/rag/llm.py's
       "local_extractive" default, app/analytics/nl_parser.py,
       app/agents/router.py).

Module map:
    errors.py            - exception hierarchy
    schemas.py             - Pydantic request/response contracts for
                            app/api/decisions.py
    scenario.py             - the verified-relationship what-if engine
    recommendation.py        - the deterministic recommendation composer
    service.py                - the only module app/api/decisions.py and
                            app/agents/decision_agent.py call; persists
                            Recommendation rows and manages the
                            pending -> approved/rejected lifecycle

Persistence: exactly one new table, `recommendations` (see
app/models/decision.py) - it's this project's first genuinely *stateful*
object (created, then later mutated by a separate approve/reject request),
which is why it needs real persistence where Phase 10's agents needed
none. Scenario calculations are deliberately NOT persisted - see
scenario.py's own docstring.

Deliberately NOT implemented (see the approved Phase 11 design proposal):
    - A `scenario_runs` table - scenario results are stateless/ephemeral,
      returned directly in the response.
    - Any causal or predictive what-if capability beyond a verified
      linear relationship between two already-existing numeric columns.
    - LLM-generated recommendation text.
    - decision:approve for anyone but ADMIN (mirrors the existing
      mlops:promote precedent - proposing/evaluating is ANALYST-reachable,
      signing off is not).
"""
