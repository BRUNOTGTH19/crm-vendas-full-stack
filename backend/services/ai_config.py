"""Configuração do provedor de IA e erros compartilhados.

Módulo pequeno e sem dependências internas: ``ai_prompts``, ``ai_web``,
``ai_tools`` e a fachada ``ai_service`` importam daqui sem criar ciclos.

A configuração vem **exclusivamente** de ``os.getenv`` e é lida a cada
requisição, então trocar a chave no provedor não exige reiniciar o processo.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse

AI_TIMEOUT_SECONDS = 18.0


class AIConfigurationError(RuntimeError):
    """Configuração ausente/inválida. O router transforma em 503 genérico."""


class AIProviderRateLimitError(RuntimeError):
    """O provedor respondeu 429 (quota do free tier)."""


class AIProviderError(RuntimeError):
    """Falha de comunicação/parse com o provedor."""


class AIToolError(ValueError):
    """Argumentos inválidos ou ferramenta não permitida."""


@dataclass(frozen=True)
class AIConfig:
    api_url: str
    api_key: str
    model: str


def load_ai_config() -> AIConfig:
    """Lê a configuração somente do ambiente, a cada requisição.

    Ler a cada chamada permite trocar a chave no Render sem reiniciar o
    processo e evita que valores de teste fiquem congelados no import.
    """
    api_url = (os.getenv("AI_API_URL") or "").strip()
    api_key = (os.getenv("AI_API_KEY") or "").strip()
    model = (os.getenv("AI_MODEL") or "").strip()
    if not api_url or not api_key or not model:
        raise AIConfigurationError("IA não configurada")

    parsed = urlparse(api_url)
    if not parsed.hostname:
        raise AIConfigurationError("URL da IA inválida")
    if parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1"}:
        raise AIConfigurationError("URL da IA inválida")

    return AIConfig(api_url=api_url, api_key=api_key, model=model)
