"""Tests never use the configured application database or external services."""
import os
from unittest.mock import MagicMock

# Set before importing any application module (including test modules).
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["REDIS_URL"] = "redis://127.0.0.1:1/15"
os.environ["JWT_SECRET_KEY"] = "isolated-test-key-not-for-production"
os.environ["ENVIRONMENT"] = "test"
os.environ["ALLOW_DATABASE_RESET"] = "true"
os.environ["REMINDER_DAYS_BEFORE"] = "0"
os.environ["REMINDER_HOUR"] = "8"
os.environ["REMINDER_TIMEZONE"] = "UTC"

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool

import database
import models  # noqa: F401

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)


@event.listens_for(engine, "connect")
def enable_foreign_keys(connection, _):
    connection.execute("PRAGMA foreign_keys=ON")


database.engine = engine
database.SessionLocal.configure(bind=engine)


@pytest.fixture(autouse=True, scope="module")
def isolated_services():
    import cache
    import scheduler
    from services import auth_service, push_service, queue_service

    with pytest.MonkeyPatch.context() as patch:
        redis_mock = MagicMock()
        redis_mock.scan_iter.return_value = []
        redis_mock.get.return_value = None
        redis_mock.smembers.return_value = set()
        for module in (cache, auth_service, queue_service):
            patch.setattr(module, "redis_client", redis_mock)
        patch.setattr(scheduler.scheduler, "start", lambda: None)
        patch.setattr(scheduler.scheduler, "shutdown", lambda **kwargs: None)
        patch.setattr(push_service, "webpush", MagicMock())
        database.Base.metadata.create_all(engine)
        yield redis_mock
        database.Base.metadata.drop_all(engine)
