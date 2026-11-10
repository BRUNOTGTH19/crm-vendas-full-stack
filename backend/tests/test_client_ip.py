"""Resolução do IP do cliente para rate limit e auditoria (A7/A8).

Atrás do proxy do hosting, ``request.client.host`` é o IP interno do
balanceador. Usar o **primeiro** item de ``X-Forwarded-For`` permitia que o
cliente escolhesse o próprio IP e burlasse o rate limit; usar o último IP
válido da cadeia é o que o proxy confiável acrescentou.
"""
from starlette.requests import Request

from middleware.client_ip import client_ip


def _request(forwarded: str | None = None, client_host: str | None = "10.0.0.5") -> Request:
    headers = []
    if forwarded is not None:
        headers.append((b"x-forwarded-for", forwarded.encode("latin-1")))
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": headers,
        "client": (client_host, 12345) if client_host else None,
    }
    return Request(scope)


def test_uses_last_valid_ip_from_forwarded_chain():
    """O IP do proxy confiável é o último; o primeiro é do cliente."""
    request = _request("203.0.113.7, 198.51.100.9, 192.0.2.10")
    assert client_ip(request) == "192.0.2.10"


def test_ignores_invalid_entries_at_the_end():
    request = _request("203.0.113.7, not-an-ip")
    assert client_ip(request) == "203.0.113.7"


def test_falls_back_to_socket_when_header_is_absent():
    assert client_ip(_request(client_host="10.0.0.5")) == "10.0.0.5"


def test_falls_back_to_socket_when_header_has_no_valid_ip():
    request = _request("garbage, still-garbage", client_host="10.0.0.5")
    assert client_ip(request) == "10.0.0.5"


def test_unknown_when_nothing_is_available():
    assert client_ip(_request(client_host=None)) == "unknown"
