# Recovery Agent

This package evaluates explicitly supplied fee, evidence, reimbursement, and trusted engine-state records. It is deterministic: it does not call an LLM, infer channel policy, submit claims, or treat the sample CSVs as authoritative policy or financial ground truth.

## Operational limits

- The only source contract rules carried over are the typed field checks, evidence mapping, exact-currency reimbursement arithmetic, and verdict projection in `src/recovery_manager/recovery_contract.py`.
- Claim windows and eligibility authority are not present in the sample files. Supply an authoritative rule record; otherwise the result is `insufficient_evidence`.
- Amounts use `Decimal`. Fee tolerance is exact (zero); no amount is rounded into a claim. The source code defines no business minimum-claim threshold, so this package invents none.
- Evidence must match the charge's exact unit, shipment, or order scope. Missing, late, uncertain, or unrelated evidence is not a pass.
- Prep, receiving, and returns adapters emit only directly observed registered checks. Return completeness, policy-dependent prep validity, and unavailable dimensions/weight remain uncertain. Fee, reimbursement, and inventory-adjustment rows are kept distinct; non-fee ledger rows are unresolved candidates, not proven credits.
- `internal_facts` must come from a trusted recovery-engine caller. Do not accept it directly from an untrusted client; it carries the currentness and remaining-actionable amount used in the decision.
- Allowed organisations are configured through `RECOVERY_ALLOWED_ORGS` as comma-separated IDs. An empty allowlist denies all requests.
- The HTTP wrapper also requires `RECOVERY_INTERNAL_TOKEN` and the `X-Recovery-Internal-Token` header. Do not expose this internal endpoint publicly.
- Reference fee values and requirement flags are synthetic. Prep image paths are identifiers only: there are no images or bounding-box coordinates in this package.
- The included PostgreSQL tables are a tenant-scoped audit/assessment store. Apply the agent migration before using them; PostgreSQL RLS is enabled and forced by that migration.

## Precision strategy

1. Validate exact input shape and fixed-point monetary values.
2. Join evidence only on the declared unit, shipment, or order identity.
3. Use only registered evidence keys and explicit `pass`, `fail`, or `uncertain` outcomes.
4. Net reimbursements only when currency and subject agree; require explicit reversal lineage.
5. Require known, current engine facts and available authoritative rules before projecting a claim verdict.
6. Convert unexpected handler failures to `uncertain` / `pending`, preserving the operator workflow.

## Run

From the repository root with the project dependencies installed:

```bash
export RECOVERY_ALLOWED_ORGS=org_demo_alpha,org_demo_bravo
printf '%s\n' '{"org_id":"org_demo_alpha","charge":{},"credits":[],"evidence":[],"rule":{},"internal_facts":{}}' | python -m agents.recovery.runner
pytest agents/recovery/tests
```

The example payload intentionally lacks decision inputs and will return `uncertain`; replace it with a normalized request matching the dataclasses in `domain/`. The HTTP app is available as `agents.recovery.app.app` for trusted in-process integration. The manifest selects `inproc` mode.

## Persistence

Configure `RECOVERY_DATABASE_URL` for runtime and `RECOVERY_MIGRATION_DATABASE_URL` for schema changes, install the package's existing SQLAlchemy/Alembic dependencies, then apply the migration with `alembic -c agents/recovery/db/alembic.ini upgrade head`. Every table access must occur inside `tenant_session()` so PostgreSQL receives transaction-local tenant context. Runtime database access requires the non-owner, non-superuser `recovery_app` role with RLS enabled.

## Evaluation limits

`tests/` exercises contract behavior and adapter joins. `run_eval.py` is a prediction/export harness, not a measured accuracy report. Report per-check false positives and false negatives only after independent labels exist; do not use the included dummy sample flags as truth.