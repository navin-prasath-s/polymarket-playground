import os
from typing import Generator
from contextlib import contextmanager

from dotenv import load_dotenv
from sqlmodel import create_engine, Session

load_dotenv()


db_path = os.getenv("DB_PATH", "db/polymarket_playground.db")
db_url = f"sqlite:///{db_path}"


engine = create_engine(db_url, echo=False)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


@contextmanager
def get_session_context() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session