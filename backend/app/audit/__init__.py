"""Centralized audit event recording and querying.

Every security/administration-relevant action goes through
record_event() - never a direct `AuditLog(...)` insert elsewhere - so the
secret-scrubbing rule in service.py is always applied.
"""
