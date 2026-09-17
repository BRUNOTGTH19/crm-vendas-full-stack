"""Prova isolada de autenticação: sem banco, Redis ou envio de push."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from config import settings
from database import get_db
from middleware.auth_middleware import get_current_user_dependency
from services.auth_service import create_access_token


@pytest.fixture
def auth_client(monkeypatch):
    monkeypatch.setattr(settings, "jwt_secret_key", "isolated-test-key-not-for-production")
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(id=7)
    app = FastAPI()
    app.dependency_overrides[get_db] = lambda: db

    @app.get("/protected")
    def protected(user=Depends(get_current_user_dependency)):
        return {"id": user.id}

    with TestClient(app) as client:
        yield client


def test_missing_authentication(auth_client):
    assert auth_client.get("/protected").status_code == 401


def test_valid_authentication(auth_client):
    token = create_access_token({"sub": "7"})
    response = auth_client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json() == {"id": 7}
