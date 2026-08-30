from alembic import context
from app.db import Base, engine
from app.config import DATA_ROOT, ensure_data_directories

config = context.config
target_metadata = Base.metadata

def run_migrations_offline():
    context.configure(url=str(engine.url), target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    ensure_data_directories()
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
