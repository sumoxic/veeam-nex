"""目标增加 VBR 版本字段

version_preference 记录用户选择（auto/12/13）；
api_version 缓存自动探测到的 REST API 版本；
detected_version 记录最近一次读取到的 VBR 构建号。

Revision ID: 0003_target_vbr_version
Revises: 0002_widen_original_size
Create Date: 2026-10-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003_target_vbr_version"
down_revision: Union[str, None] = "0002_widen_original_size"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "targets",
        sa.Column(
            "version_preference",
            sa.String(length=16),
            nullable=False,
            server_default="auto",
        ),
    )
    op.add_column(
        "targets",
        sa.Column("api_version", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "targets",
        sa.Column("detected_version", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("targets", "detected_version")
    op.drop_column("targets", "api_version")
    op.drop_column("targets", "version_preference")
