"""Rate limiting em memória para o endpoint de login (anti força-bruta).

Contabiliza apenas tentativas **falhas** (HTTP 401) por endereço IP dentro de
uma janela deslizante. Não depende de Redis e funciona com o processo único do
servidor (uvicorn). Com vários workers/instâncias cada processo mantém seu
próprio contador — ainda assim reduz o ataque de força bruta.
"""
from __future__ import annotations

import time
from collections import defaultdict

# Limite por IP: 15 falhas de login em 5 minutos.
LOGIN_MAX_FAILURES = 15
LOGIN_WINDOW_SECONDS = 300

_failures: dict[str, list[float]] = defaultdict(list)


def _prune(key: str, now: float, window: float = LOGIN_WINDOW_SECONDS) -> None:
    stamps = _failures.get(key)
    if not stamps:
        _failures.pop(key, None)
        return
    stamps[:] = [t for t in stamps if now - t < window]
    if not stamps:
        _failures.pop(key, None)


def is_login_blocked(key: str, now: float | None = None) -> bool:
    """True quando o IP excedeu o número de falhas na janela."""
    now = time.monotonic() if now is None else now
    _prune(key, now)
    return len(_failures.get(key, ())) >= LOGIN_MAX_FAILURES


def record_login_failure(key: str, now: float | None = None) -> None:
    now = time.monotonic() if now is None else now
    _prune(key, now)
    _failures[key].append(now)


def reset_rate_limit() -> None:
    """Limpa contadores (usado pelos testes)."""
    _failures.clear()