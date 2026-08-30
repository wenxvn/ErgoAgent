"""create data contract tables"""
from alembic import op
from app.db import Base

revision = "0001_data_contract"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    Base.metadata.create_all(op.get_bind())

def downgrade():
    Base.metadata.drop_all(op.get_bind())
