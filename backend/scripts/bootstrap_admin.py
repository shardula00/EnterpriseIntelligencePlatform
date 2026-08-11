"""Development-only bootstrap: seed roles/permissions and create the first
admin user.

Run from backend/, with the venv active and Postgres up and migrated:

    python -m scripts.bootstrap_admin

Reads BOOTSTRAP_ADMIN_EMAIL / BOOTSTRAP_ADMIN_PASSWORD from the environment
(backend/.env). There is no default password - this refuses to run without
one, so a real credential is never baked into source or committed.

Idempotent: safe to run again later (e.g. after a fresh migration) - it
will not duplicate the admin user or overwrite an existing password.
"""

import sys

from sqlalchemy import select

from app.auth.security import hash_password
from app.config import get_settings
from app.db import SessionLocal
from app.models.user import Role, User
from app.rbac.seed import seed_roles_and_permissions


def main() -> int:
    settings = get_settings()

    if not settings.bootstrap_admin_password:
        print(
            "ERROR: BOOTSTRAP_ADMIN_PASSWORD is not set.\n"
            "Set it in backend/.env (see .env.example) and re-run:\n"
            "    python -m scripts.bootstrap_admin",
            file=sys.stderr,
        )
        return 1

    db = SessionLocal()
    try:
        seed_roles_and_permissions(db)
        print("Seeded roles and permissions (or confirmed already present).")

        existing = db.execute(
            select(User).where(User.email == settings.bootstrap_admin_email)
        ).scalar_one_or_none()

        if existing is not None:
            admin_role = db.execute(select(Role).where(Role.name == "ADMIN")).scalar_one()
            if admin_role not in existing.roles:
                existing.roles.append(admin_role)
                db.commit()
                print(f"User '{existing.email}' already existed; granted ADMIN role.")
            else:
                print(f"Admin user '{existing.email}' already exists. Nothing to do.")
            return 0

        admin_role = db.execute(select(Role).where(Role.name == "ADMIN")).scalar_one()
        admin = User(
            email=settings.bootstrap_admin_email,
            password_hash=hash_password(settings.bootstrap_admin_password),
            full_name="Administrator",
            roles=[admin_role],
        )
        db.add(admin)
        db.commit()
        print(f"Created admin user '{admin.email}'.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
