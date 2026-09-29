from alembic import context
from sqlalchemy import create_engine, pool, text

from research_copilot.db.models import Base

config = context.config
url = config.attributes.get('url')
schema = config.attributes.get('schema')
if not url:
    from research_copilot.db.engine import database_url, sqlalchemy_url
    url = sqlalchemy_url(database_url())

engine = create_engine(url, poolclass=pool.NullPool)
with engine.connect() as connection:
    if schema:
        connection.execute(text(f'SET search_path TO "{schema}"'))
        connection.commit()
    context.configure(connection=connection, target_metadata=Base.metadata,
                      version_table_schema=schema)
    with context.begin_transaction():
        context.run_migrations()
engine.dispose()
