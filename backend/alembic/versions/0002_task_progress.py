"""add live analysis progress to tasks"""

from alembic import op
import sqlalchemy as sa


revision = "0002_task_progress"
down_revision = "0001_data_contract"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("analysis_tasks") as batch:
        batch.add_column(sa.Column("progress_stage", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("progress_current_frame", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("progress_total_frames", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("progress_detected_frames", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("progress_peak_reba", sa.Float(), nullable=True))


def downgrade():
    with op.batch_alter_table("analysis_tasks") as batch:
        batch.drop_column("progress_peak_reba")
        batch.drop_column("progress_detected_frames")
        batch.drop_column("progress_total_frames")
        batch.drop_column("progress_current_frame")
        batch.drop_column("progress_stage")
