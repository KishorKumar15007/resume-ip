"""add optional TOTP MFA fields to users

Revision ID: a4c7b6d92e10
Revises: ce1c22c4205c
Create Date: 2026-10-27 18:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a4c7b6d92e10"
down_revision: Union[str, Sequence[str], None] = "ce1c22c4205c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "mfa_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "users",
        sa.Column("totp_secret_encrypted", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "totp_secret_encrypted")
    op.drop_column("users", "mfa_enabled")
