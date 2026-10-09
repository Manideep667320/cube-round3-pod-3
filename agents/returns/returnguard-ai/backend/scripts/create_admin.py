"""Create an administrator account (secure bootstrap; no public registration).

Usage:
    python -m scripts.create_admin --username admin --password <password> [--full-name "Name"]
    python -m scripts.create_admin            # prompts for the password

Password can also be provided via ADMIN_BOOTSTRAP_PASSWORD env var to avoid
shelling history exposure.
"""
from __future__ import annotations

import argparse
import getpass
import os
import sys

from sqlalchemy import func, select

from app.core.security import hash_password
from app.db.session import Base, SessionLocal, engine
from app.models import AuditAction, User, UserRole


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a ReturnGuard AI administrator")
    parser.add_argument("--username", required=True)
    parser.add_argument("--full-name", default="Administrator")
    args = parser.parse_args()

    password = os.environ.get("ADMIN_BOOTSTRAP_PASSWORD") or getpass.getpass("Admin password (min 8 chars): ")
    if len(password) < 8:
        print("Password must be at least 8 characters.", file=sys.stderr)
        return 1

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        username = args.username.lower()
        if db.scalar(select(User).where(User.username == username)) is not None:
            print(f"User '{username}' already exists.", file=sys.stderr)
            return 1
        admin_count = db.scalar(select(func.count(User.id)).where(User.role == UserRole.ADMIN)) or 0
        user = User(
            username=username,
            full_name=args.full_name,
            password_hash=hash_password(password),
            role=UserRole.ADMIN,
            is_active=True,
        )
        db.add(user)
        db.flush()
        record = AuditAction.USER_CREATED
        from app.services.audit_service import record_event

        record_event(
            db, action=record, entity_type="user", entity_id=user.id,
            actor_id=None, actor_role="SYSTEM", details={"username": username, "role": "ADMIN", "via": "cli"},
        )
        db.commit()
        first = "" if admin_count else " (first admin)"
        print(f"Administrator '{username}' created{first}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
