"""add live analysis progress to tasks"""

from alembic import op
import sqlalchemy as sa


revision = "0002_task_progress"
down_revision = "0001_data_contract"
branch_labels = None
depends_on = None


def upgrade():
    existing = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("analysis_tasks")}
    columns = (
        sa.Column("progress_stage", sa.String(length=64), nullable=True),
        sa.Column("progress_current_frame", sa.Integer(), nullable=True),
        sa.Column("progress_total_frames", sa.Integer(), nullable=True),
        sa.Column("progress_detected_frames", sa.Integer(), nullable=True),
        sa.Column("progress_peak_reba", sa.Float(), nullable=True),
    )
    with op.batch_alter_table("analysis_tasks") as batch:
        for column in columns:
            if column.name not in existing:
                batch.add_column(column)


def downgrade():
    existing = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("analysis_tasks")}
    with op.batch_alter_table("analysis_tasks") as batch:
        for name in ("progress_peak_reba", "progress_detected_frames", "progress_total_frames", "progress_current_frame", "progress_stage"):
            if name in existing:
                batch.drop_column(name)
