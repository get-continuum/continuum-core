from __future__ import annotations

import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.config import get_database_url

DATABASE_URL = get_database_url()

_disable_pool = os.getenv("DB_DISABLE_SQLALCHEMY_POOL", "").strip().lower() in {"1", "true", "yes"}
# Supabase Poolers (PgBouncer) often work best with client-side pooling disabled.
if _disable_pool:
    engine = create_engine(DATABASE_URL, future=True, poolclass=NullPool)
else:
    engine = create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

