"""baseline schema

Revision ID: 1e9c13445c12
Revises:
Create Date: 2026-07-15 19:25:50.644903

Represents the schema as created by SQLAlchemy's `Base.metadata.create_all`
prior to Alembic being introduced. Tables already exist in every deployed
environment, so `upgrade`/`downgrade` are no-ops — this revision exists as
the documented starting point that later revisions build on. New
environments should run `alembic upgrade head`, which will create the
tables via the later revisions instead.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1e9c13445c12'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """No-op: represents pre-Alembic state of already-deployed databases."""
    pass


def downgrade() -> None:
    """No-op: see upgrade()."""
    pass
