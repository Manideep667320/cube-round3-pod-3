from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class RecoverySettings:
    allowed_orgs: frozenset[str]
    database_url: str | None
    migration_database_url: str | None
    internal_token: str | None

    @classmethod
    def from_env(cls) -> RecoverySettings:
        raw_orgs = os.getenv("RECOVERY_ALLOWED_ORGS", "")
        if raw_orgs.strip():
            orgs = frozenset(
                value.strip()
                for value in raw_orgs.split(",")
                if value.strip()
            )
        else:
            orgs = frozenset({"org_demo_alpha", "org_demo_bravo"})
        return cls(
            allowed_orgs=orgs,
            database_url=os.getenv("RECOVERY_DATABASE_URL") or None,
            migration_database_url=os.getenv("RECOVERY_MIGRATION_DATABASE_URL") or None,
            internal_token=os.getenv("RECOVERY_INTERNAL_TOKEN") or None,
        )