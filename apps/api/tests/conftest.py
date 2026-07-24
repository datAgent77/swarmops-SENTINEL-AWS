"""Test configuration.

Points the app at a dedicated test database and runs the deterministic workflow
instantly. Environment must be set *before* importing app modules (the engine is
created at import time).
"""

import os

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://swarmops@localhost:5432/swarmops_test"
)
os.environ["DEMO_EVENT_DELAY_MS"] = "0"

import pytest  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db import models  # noqa: F401,E402  (register tables)
from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.seed import seed  # noqa: E402

_TABLES = (
    "performance_reports, agent_versions, "
    "cost_records, governance_decisions, approvals, events, mission_tasks, "
    "missions, policies, agents, organizations"
)


@pytest.fixture(scope="session", autouse=True)
def _schema():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture(autouse=True)
def _clean_and_seed():
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {_TABLES} RESTART IDENTITY CASCADE"))
    with SessionLocal() as session:
        seed(session)
        session.commit()
    yield
