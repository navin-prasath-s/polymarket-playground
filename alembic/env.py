from logging.config import fileConfig
import os
from pathlib import Path

from dotenv import load_dotenv

from sqlalchemy import engine_from_config
from sqlalchemy import pool
from sqlmodel import SQLModel
from alembic import context

from src.models.market import Market
from src.models.market_change_log import MarketChangeLog
from src.models.market_outcome import MarketOutcome
from src.models.sync_hot_market import SyncHotMarket
from src.models.order import Order
from src.models.order_fill import OrderFill
from src.models.payout_log import PayoutLog
from src.models.user import User
from src.models.user_position import UserPosition
from src.models.reset_log import ResetLog


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv()



db_path_env = os.getenv("DB_PATH", "db/polymarket_playground.db")
db_path = (BASE_DIR / db_path_env).resolve()
db_path.parent.mkdir(parents=True, exist_ok=True)
db_url = f"sqlite:///{str(db_path)}"

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config
config.set_main_option("sqlalchemy.url", db_url)
# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = SQLModel.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()


# alembic revision --autogenerate -m "Initial tables"
# alembic upgrade head
# alembic downgrade base
