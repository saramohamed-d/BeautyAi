"""booking rules

Sprint 6:
- Double-booking guard becomes "one *active* appointment per slot"
  (partial unique index ignoring cancelled ones), so a cancelled slot can
  be booked again.
- Slot holds during payment (availability.held_by_patient_id / held_until).
- Cancellation metadata on appointments.
- Per-clinic cancellation cutoff (hours before the appointment).

Revision ID: 56b733b79e88
Revises: bc36cfae70a0
Create Date: 2026-09-19 16:02:11.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '56b733b79e88'
down_revision: Union[str, None] = 'bc36cfae70a0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint('appointments_availability_id_key', 'appointments', type_='unique')
    op.create_index(
        'uq_appointments_active_availability', 'appointments', ['availability_id'],
        unique=True, postgresql_where=sa.text("status <> 'cancelled'"),
    )
    op.add_column('appointments', sa.Column('cancellable_until', sa.DateTime(timezone=True), nullable=True))
    op.add_column('appointments', sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('appointments', sa.Column('cancelled_by_user_id', sa.UUID(), nullable=True))
    op.add_column('appointments', sa.Column('cancellation_reason', sa.Text(), nullable=True))
    op.create_foreign_key(
        'fk_appointments_cancelled_by_user_id_users', 'appointments', 'users',
        ['cancelled_by_user_id'], ['id'], ondelete='SET NULL',
    )

    op.add_column('availability', sa.Column('held_by_patient_id', sa.UUID(), nullable=True))
    op.add_column('availability', sa.Column('held_until', sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(
        'fk_availability_held_by_patient_id_patients', 'availability', 'patients',
        ['held_by_patient_id'], ['id'], ondelete='SET NULL',
    )

    op.add_column('clinics', sa.Column('cancellation_cutoff_hours', sa.Integer(), server_default='24', nullable=False))
    op.create_check_constraint(
        'ck_clinics_cancellation_cutoff_non_negative', 'clinics', 'cancellation_cutoff_hours >= 0'
    )
    # Existing appointments get the default policy's deadline.
    op.execute(
        "UPDATE appointments a SET cancellable_until = a.scheduled_start - make_interval(hours => c.cancellation_cutoff_hours) "
        "FROM clinics c WHERE c.id = a.clinic_id"
    )


def downgrade() -> None:
    op.drop_constraint('ck_clinics_cancellation_cutoff_non_negative', 'clinics', type_='check')
    op.drop_column('clinics', 'cancellation_cutoff_hours')

    op.drop_constraint('fk_availability_held_by_patient_id_patients', 'availability', type_='foreignkey')
    op.drop_column('availability', 'held_until')
    op.drop_column('availability', 'held_by_patient_id')

    op.drop_constraint('fk_appointments_cancelled_by_user_id_users', 'appointments', type_='foreignkey')
    op.drop_column('appointments', 'cancellation_reason')
    op.drop_column('appointments', 'cancelled_by_user_id')
    op.drop_column('appointments', 'cancelled_at')
    op.drop_column('appointments', 'cancellable_until')
    op.drop_index('uq_appointments_active_availability', table_name='appointments')
    # The old one-appointment-per-slot constraint can't hold cancelled
    # history alongside rebookings, so cancelled rows lose their slot link.
    op.execute("UPDATE appointments SET availability_id = NULL WHERE status = 'cancelled'")
    op.create_unique_constraint('appointments_availability_id_key', 'appointments', ['availability_id'])
