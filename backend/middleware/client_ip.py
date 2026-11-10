"""Resolução do IP do cliente para rate limits e auditoria.

Atrás do proxy do hosting (Render), ``request.client.host`` é o IP interno do
balanceador — usar esse valor faria TODOS os usuários dividirem a mesma chave de
rate limit. O header ``X-Forwarded-For`` traz a cadeia de IPs; o **último** foi
acrescentado pelo proxy confiável, enquanto os anteriores podem ter sido
enviados pelo cliente e são falsificáveis (A7 da auditoria).

Regras:

1. usar o último IP **válido** da cadeia ``X-Forwarded-For``;
2. cair para ``request.client.host`` quando o header não existe/é inválido;
3. devolver ``"unknown"`` como último recurso.
"""
from __future__ import annotations

import ipaddress

from starlette.requests import Request


def _is_valid_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value.split("%", 1)[0])
    except ValueError:
        return False
    return True


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for") or ""
    for raw in reversed([part.strip() for part in forwarded.split(",") if part.strip()]):
        if _is_valid_ip(raw):
            return raw
    if request.client and request.client.host:
        return request.client.host
    return "unknown"
