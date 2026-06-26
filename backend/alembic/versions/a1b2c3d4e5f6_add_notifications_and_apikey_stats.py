"""add notifications table and api key lifecycle fields

Revision ID: a1b2c3d4e5f6
Revises: 03400aafd4e5
Create Date: 2026-06-26

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '03400aafd4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 通知记录表
    op.create_table(
        'notifications',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('recipient', sa.String(255), nullable=False, index=True),
        sa.Column('channel', sa.String(32), nullable=False, index=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('body', sa.Text(), nullable=False, server_default=''),
        sa.Column('priority', sa.String(16), nullable=False, server_default='normal'),
        sa.Column('status', sa.String(16), nullable=False, server_default='pending'),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # API Key 生命周期字段
    op.add_column('api_keys', sa.Column('first_used_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('api_keys', sa.Column('usage_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column(
        'api_keys',
        sa.Column('rotated_from', sa.String(36),
                   sa.ForeignKey('api_keys.id', ondelete='SET NULL'), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('api_keys', 'rotated_from')
    op.drop_column('api_keys', 'usage_count')
    op.drop_column('api_keys', 'first_used_at')
    op.drop_table('notifications')
