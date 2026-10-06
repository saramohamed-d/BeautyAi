"""doctor avatar

Which illustrated avatar a doctor shows on their profile and in search
results (the drawings live in the frontend, see components/ui/avatar.tsx).
Null means the neutral default avatar.

Revision ID: e4f1a9c2b7d0
Revises: acdaccd1b905
Create Date: 2026-10-06 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e4f1a9c2b7d0'
down_revision: Union[str, None] = 'acdaccd1b905'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('doctors', sa.Column('avatar', sa.String(length=32), nullable=True))
    # Existing seed doctors get a matching avatar (no-op on other databases).
    op.execute("UPDATE doctors SET avatar = 'woman-3' WHERE email = 'dr.amira.hassan@example.com'")
    op.execute("UPDATE doctors SET avatar = 'man-1' WHERE email = 'dr.khaled.ibrahim@example.com'")
    op.execute("UPDATE doctors SET avatar = 'woman-1' WHERE email = 'dr.mona.elsherif@example.com'")


def downgrade() -> None:
    op.drop_column('doctors', 'avatar')
