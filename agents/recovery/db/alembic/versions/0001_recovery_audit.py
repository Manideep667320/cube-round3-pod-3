"""Create tenant-isolated recovery assessment and audit tables."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_recovery_audit"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recovery_agent_assessment",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", sa.String(128), nullable=False),
        sa.Column("verdict", sa.String(40), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", "org_id", name="pk_recovery_agent_assessment"),
        sa.CheckConstraint("btrim(org_id) <> ''", name="ck_recovery_assessment_org_nonempty"),
    )
    op.create_table(
        "recovery_agent_audit",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", sa.String(128), nullable=False),
        sa.Column("actor_id", sa.String(128), nullable=True),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("details", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_recovery_agent_audit"),
        sa.CheckConstraint("btrim(org_id) <> ''", name="ck_recovery_audit_org_nonempty"),
    )
    for table in ("recovery_agent_assessment", "recovery_agent_audit"):
        op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'))
        op.execute(sa.text(
            f'''CREATE POLICY "{table}_tenant_policy" ON "{table}"
            USING (org_id = NULLIF(current_setting('app.current_org_id', true), ''))
            WITH CHECK (org_id = NULLIF(current_setting('app.current_org_id', true), ''))'''
        ))
    op.execute(sa.text("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'recovery_app') THEN
                EXECUTE 'GRANT SELECT, INSERT ON recovery_agent_assessment TO recovery_app';
                EXECUTE 'GRANT SELECT, INSERT ON recovery_agent_audit TO recovery_app';
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'recovery_worker') THEN
                EXECUTE 'GRANT SELECT, INSERT ON recovery_agent_assessment TO recovery_worker';
                EXECUTE 'GRANT SELECT, INSERT ON recovery_agent_audit TO recovery_worker';
            END IF;
        END $$
    """))


def downgrade() -> None:
    op.drop_table("recovery_agent_audit")
    op.drop_table("recovery_agent_assessment")