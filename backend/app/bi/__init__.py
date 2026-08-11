"""Business Intelligence: generic KPI computation over ingested datasets.

Nothing here names a business concept ("revenue", "churn", etc.) - a KPI
is {aggregation, column} computed against whatever columns a dataset
actually has, using the type metadata Phase 2 already recorded in
dataset_columns. See service.py for the computation logic.
"""
