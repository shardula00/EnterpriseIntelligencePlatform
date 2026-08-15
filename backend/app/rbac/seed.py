"""The fixed roles/permissions catalog and its default mapping.

Seeding is additive-only and idempotent: re-running never removes a role,
permission, or role->permission link that already exists (including any an
admin added by hand later) - it only ever adds what's missing. Called from
scripts/bootstrap_admin.py; safe to call as often as needed.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import Permission, Role

ROLE_NAMES = ["ADMIN", "ANALYST", "VIEWER"]

# name -> human-readable description
PERMISSION_CATALOG: dict[str, str] = {
    "dataset:read": "View datasets and their schema, quality, preview, and lineage.",
    "dataset:create": "Upload new datasets.",
    "dataset:delete": "Delete datasets.",
    "dashboard:read": "View KPI summary stat tiles.",
    "dashboard:configure": "Choose breakdown/trend params (group-by, metric, agg, granularity).",
    "user:read": "View users.",
    "user:create": "Create users.",
    "user:update": "Update users: profile, activation status, role assignment.",
    "user:delete": "Delete users.",
    "audit:read": "View the audit log.",
    "ml:read": "View ML run history, results, metrics, and predictions.",
    "ml:train": "Train a new ML model run on a dataset.",
    "ml:predict": "Generate predictions from a previously trained ML run.",
    "mlops:read": "View the model registry, versions, drift checks, and monitoring alerts.",
    "mlops:evaluate": "Register a model version and run drift/performance monitoring checks.",
    "mlops:promote": "Promote, demote, or archive a model version.",
    "rag:read": "View your own uploaded documents and past RAG query history.",
    "rag:upload": "Upload, process, and delete your own documents.",
    "rag:query": "Ask questions against the enterprise knowledge assistant (RAG).",
    "analytics:read": "View past natural-language analytics query history.",
    "analytics:query": "Ask natural-language analytical questions against a dataset.",
    "agents:run": "Run the multi-agent orchestrator against a question and optional dataset.",
}

# Deliberately explicit rather than derived: dataset:delete is ADMIN-only by
# design, not an accident of set-difference logic.
DEFAULT_ROLE_PERMISSIONS: dict[str, list[str]] = {
    "VIEWER": [
        "dataset:read", "dashboard:read", "ml:read", "mlops:read", "rag:read", "analytics:read",
    ],
    "ANALYST": [
        "dataset:read",
        "dataset:create",
        "dashboard:read",
        "dashboard:configure",
        "ml:read",
        "ml:train",
        "ml:predict",
        "mlops:read",
        "mlops:evaluate",
        "rag:read",
        "rag:upload",
        "rag:query",
        "analytics:read",
        "analytics:query",
        "agents:run",
    ],
    "ADMIN": list(PERMISSION_CATALOG.keys()),
}


def seed_roles_and_permissions(db: Session) -> None:
    existing_roles = {r.name: r for r in db.execute(select(Role)).scalars()}
    for name in ROLE_NAMES:
        if name not in existing_roles:
            role = Role(name=name)
            db.add(role)
            existing_roles[name] = role
    db.flush()  # assign ids to any newly-added roles before linking permissions

    existing_permissions = {p.name: p for p in db.execute(select(Permission)).scalars()}
    for name, description in PERMISSION_CATALOG.items():
        if name not in existing_permissions:
            permission = Permission(name=name, description=description)
            db.add(permission)
            existing_permissions[name] = permission
    db.flush()

    for role_name, permission_names in DEFAULT_ROLE_PERMISSIONS.items():
        role = existing_roles[role_name]
        already_granted = {p.name for p in role.permissions}
        for permission_name in permission_names:
            if permission_name not in already_granted:
                role.permissions.append(existing_permissions[permission_name])

    db.commit()
