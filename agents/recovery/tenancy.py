from __future__ import annotations

from collections.abc import Iterator, Set
from contextlib import contextmanager
from contextvars import ContextVar

_current_org: ContextVar[str | None] = ContextVar("recovery_current_org", default=None)


def require_allowed_org(org_id: str, allowed_orgs: Set[str]) -> str:
    if not isinstance(org_id, str) or not org_id or org_id != org_id.strip():
        raise LookupError("Tenant context is missing or invalid")
    if org_id not in allowed_orgs:
        raise LookupError("Organization is not allowed")
    return org_id


def current_org() -> str:
    org_id = _current_org.get()
    if org_id is None:
        raise LookupError("Tenant context has not been established")
    return org_id


def assert_same_org(org_id: str) -> None:
    if org_id != current_org():
        raise LookupError("Cross-organization access refused")


@contextmanager
def tenant_scope(org_id: str, allowed_orgs: Set[str]) -> Iterator[str]:
    validated = require_allowed_org(org_id, allowed_orgs)
    token = _current_org.set(validated)
    try:
        yield validated
    finally:
        _current_org.reset(token)