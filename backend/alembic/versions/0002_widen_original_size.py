"""还原点 original_size 改为 BIGINT

VBR 上报的还原点原始大小是字节数（实测 5.7 GB = 5771363647），
已超过 MySQL INT 的 32 位上限，落库会报 DataError 1264。

Revision ID: 0002_widen_original_size
Revises: be9854d00e37
Create Date: 2026-10-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision: str = "0002_widen_original_size"
down_revision: Union[str, None] = "be9854d00e37"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "restore_point_snapshots",
        "original_size",
        existing_type=mysql.INTEGER(),
        type_=sa.BigInteger(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "restore_point_snapshots",
        "original_size",
        existing_type=sa.BigInteger(),
        type_=mysql.INTEGER(),
        existing_nullable=True,
    )
