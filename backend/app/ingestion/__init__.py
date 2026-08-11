"""Generic dataset ingestion pipeline.

Nothing in this package refers to a specific business schema. A file's
columns and types are always discovered from the file itself at upload
time - see naming.py, parsers.py, type_inference.py, profiling.py,
quality.py, and table_builder.py for the individual pipeline stages, and
service.py for how they're composed.
"""
