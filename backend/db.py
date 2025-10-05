from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session


DATABASE_URL = "sqlite:///./data.sqlite3"


class Base(DeclarativeBase):
	pass


engine = create_engine(
	DATABASE_URL,
	connect_args={"check_same_thread": False},
	pool_pre_ping=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
	db = SessionLocal()
	try:
		yield db
	finally:
		db.close()


