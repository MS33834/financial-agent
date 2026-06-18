"""add report error message

Revision ID: fcec2006310a
Revises: d04c33d13d30
Create Date: 2026-06-18 15:44:53.541509

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'fcec2006310a'
down_revision: str | None = 'd04c33d13d30'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """为 reports 表添加 error_message 字段."""
    op.add_column(
        'reports',
        sa.Column('error_message', sa.Text(), nullable=True),
    )


def downgrade() -> None:
    """移除 reports 表的 error_message 字段."""
    op.drop_column('reports', 'error_message')
