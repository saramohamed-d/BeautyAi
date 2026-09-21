"""users and auth

Adds central login identities (users), refresh tokens, and links the
patient / doctor / clinic-staff profiles to them. Also renames the audit
actor type `super_admin` to `platform_admin` to match the spec's role name.

Revision ID: bc36cfae70a0
Revises: 7867ecd1f62c
Create Date: 2026-09-19 14:24:02.770379

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bc36cfae70a0'
down_revision: Union[str, None] = '7867ecd1f62c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('users',
    sa.Column('email', sa.String(length=255), nullable=True),
    sa.Column('phone', sa.String(length=32), nullable=True),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('role', sa.Enum('patient', 'doctor', 'clinic_admin', 'platform_admin', name='user_role'), nullable=False),
    sa.Column('status', sa.Enum('active', 'pending', 'suspended', name='user_status'), server_default='active', nullable=False),
    sa.Column('email_verified_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('phone_verified_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('email IS NOT NULL OR phone IS NOT NULL', name='ck_users_email_or_phone'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email', name='uq_users_email'),
    sa.UniqueConstraint('phone', name='uq_users_phone')
    )
    op.create_index(op.f('ix_users_role'), 'users', ['role'], unique=False)
    op.create_table('refresh_tokens',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('family_id', sa.UUID(), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('token_hash', name='uq_refresh_tokens_token_hash')
    )
    op.create_index('ix_refresh_tokens_family_id', 'refresh_tokens', ['family_id'], unique=False)
    op.create_index('ix_refresh_tokens_user_id', 'refresh_tokens', ['user_id'], unique=False)

    op.add_column('clinic_staff', sa.Column('user_id', sa.UUID(), nullable=True))
    op.create_index(op.f('ix_clinic_staff_user_id'), 'clinic_staff', ['user_id'], unique=False)
    op.create_unique_constraint('uq_clinic_staff_clinic_user', 'clinic_staff', ['clinic_id', 'user_id'])
    op.create_foreign_key('fk_clinic_staff_user_id_users', 'clinic_staff', 'users', ['user_id'], ['id'], ondelete='SET NULL')

    op.add_column('doctors', sa.Column('user_id', sa.UUID(), nullable=True))
    op.create_unique_constraint('uq_doctors_user_id', 'doctors', ['user_id'])
    op.create_foreign_key('fk_doctors_user_id_users', 'doctors', 'users', ['user_id'], ['id'], ondelete='SET NULL')

    op.add_column('patients', sa.Column('user_id', sa.UUID(), nullable=True))
    op.add_column('patients', sa.Column('city', sa.String(length=128), nullable=True))
    op.create_unique_constraint('uq_patients_user_id', 'patients', ['user_id'])
    op.create_foreign_key('fk_patients_user_id_users', 'patients', 'users', ['user_id'], ['id'], ondelete='SET NULL')

    op.execute("ALTER TYPE actor_type RENAME VALUE 'super_admin' TO 'platform_admin'")


def downgrade() -> None:
    op.execute("ALTER TYPE actor_type RENAME VALUE 'platform_admin' TO 'super_admin'")

    op.drop_constraint('fk_patients_user_id_users', 'patients', type_='foreignkey')
    op.drop_constraint('uq_patients_user_id', 'patients', type_='unique')
    op.drop_column('patients', 'city')
    op.drop_column('patients', 'user_id')

    op.drop_constraint('fk_doctors_user_id_users', 'doctors', type_='foreignkey')
    op.drop_constraint('uq_doctors_user_id', 'doctors', type_='unique')
    op.drop_column('doctors', 'user_id')

    op.drop_constraint('fk_clinic_staff_user_id_users', 'clinic_staff', type_='foreignkey')
    op.drop_constraint('uq_clinic_staff_clinic_user', 'clinic_staff', type_='unique')
    op.drop_index(op.f('ix_clinic_staff_user_id'), table_name='clinic_staff')
    op.drop_column('clinic_staff', 'user_id')

    op.drop_index('ix_refresh_tokens_user_id', table_name='refresh_tokens')
    op.drop_index('ix_refresh_tokens_family_id', table_name='refresh_tokens')
    op.drop_table('refresh_tokens')
    op.drop_index(op.f('ix_users_role'), table_name='users')
    op.drop_table('users')

    # Enum types outlive their tables in Postgres; see the initial migration.
    op.execute("DROP TYPE IF EXISTS user_role, user_status")
