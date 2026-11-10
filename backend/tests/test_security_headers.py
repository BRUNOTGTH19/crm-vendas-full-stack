"""Cabeçalhos de endurecimento do navegador (A12 da auditoria).

Não substituem uma CSP, mas removem vetores baratos: MIME sniffing,
framing (clickjacking), vazamento de referrer e acesso a sensores.
"""
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_health_response_carries_security_headers():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "camera=()" in response.headers["permissions-policy"]
    assert response.headers["cross-origin-opener-policy"] == "same-origin"


def test_error_responses_carry_security_headers():
    """Rotas de erro também passam pelo middleware (ex.: 404 de rota)."""
    response = client.get("/rota-que-nao-existe")

    assert response.status_code == 404
    assert response.headers["x-content-type-options"] == "nosniff"
