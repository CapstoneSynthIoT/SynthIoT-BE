import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set. Check your .env file.")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def create_tables():
    """Create all tables in the database if they don't already exist.

    Retries 3 times with a short delay to handle Cloud SQL cold-start latency.
    Logs and continues (non-fatal) if the DB is unavailable — the app will still
    start and individual route handlers will surface DB errors per-request.
    """
    import time
    import logging
    logger = logging.getLogger("SynthIoT")

    from Database_files import models  # noqa: F401

    for attempt in range(1, 4):
        try:
            Base.metadata.create_all(bind=engine)
            logger.info("✅ Database tables verified.")
            return
        except Exception as e:
            logger.warning(f"⚠️ DB connect attempt {attempt}/3 failed: {e}")
            if attempt < 3:
                time.sleep(3)

    logger.error(
        "❌ Could not connect to the database after 3 attempts. "
        "The app will continue, but DB-dependent routes will fail. "
        "Check that the Cloud SQL instance is running and the connection name is correct."
    )


# Dependency to get DB session in FastAPI routes
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
