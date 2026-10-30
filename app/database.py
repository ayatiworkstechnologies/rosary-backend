from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool
from dotenv import load_dotenv
import os


load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL and DATABASE_URL.startswith("sqlite"):
    # In-memory SQLite is shared across threads via a single pooled
    # connection so the automated test suite (TestClient worker threads)
    # sees one consistent schema. Production URLs are unaffected.
    if ":memory:" in DATABASE_URL:
        engine = create_engine(
            DATABASE_URL,
            pool_pre_ping=True,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    else:
        # File-based SQLite (the disposable E2E server) must hand every
        # thread its own connection: FastAPI runs sync endpoints in a
        # threadpool, and a single shared StaticPool connection lets
        # concurrent requests interleave statements on one cursor,
        # causing random failures ("IndexError: tuple index out of
        # range" from SQLAlchemy row processors). A regular pool gives
        # one connection per session; a busy_timeout tolerates brief
        # write locks when requests overlap.
        from sqlalchemy import event

        engine = create_engine(
            DATABASE_URL,
            pool_pre_ping=True,
            connect_args={"check_same_thread": False},
        )

        @event.listens_for(engine, "connect")
        def _sqlite_concurrency_pragmas(dbapi_connection, _record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA busy_timeout=10000")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()
else:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True
    )

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()