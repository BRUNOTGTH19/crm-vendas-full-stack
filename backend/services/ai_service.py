"""Assistente de IA do CRM — somente leitura, com dados do CRM e web.

Este módulo é a **fachada** do assistente: orquestra as chamadas ao provedor e
re-exporta as peças divididas para manter a API histórica (``execute_tool``,
``_fetch_url``, ``_is_public_ip``, ``TOOLS``...). A implementação vive em:

- ``ai_config``  — configuração do provedor e erros;
- ``ai_prompts`` — prompts, schemas das ferramentas e limites;
- ``ai_tools``   — ferramentas de leitura do CRM;
- ``ai_web``     — busca e leitura de páginas (proteção SSRF).

Regras de segurança centrais:

- a configuração do provedor vem **exclusivamente** de ``os.getenv``;
- o escopo dos dados (``owner_id``) nunca é aceito como argumento de ferramenta:
  ele é recebido do JWT/``resolve_data_owner`` pelo router e aplicado em toda
  consulta SQLAlchemy;
- as ferramentas são fixas e não geram SQL livre; não existe ferramenta de
  escrita, exclusão ou execução de ação;
- prompts, respostas, consultas web e chave nunca são registrados em log;
- o texto do usuário é sanitizado e dados sensíveis óbvios são removidos antes
  de qualquer envio ao provedor;
- ``fetch_url`` bloqueia esquemas perigosos, IPs privados/loopback e
  redirecionamentos para destinos internos (proteção SSRF);
- resultados da web são conteúdo **não confiável** e o prompt manda ignorar
  instruções vindas deles;
- a saída da IA é tratada como texto simples (o frontend não renderiza HTML).
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx
from sqlalchemy.orm import Session

import cache
from clock import local_today
from services.ai_config import (
    AI_TIMEOUT_SECONDS,
    AIConfig,
    AIConfigurationError,
    AIProviderError,
    AIProviderRateLimitError,
    AIToolError,
    load_ai_config,
)
from services.ai_prompts import (
    CHAT_MAX_TOKENS,
    FALLBACK_TOOL_LIMIT,
    MAX_CHAT_INPUT_CHARS,
    MAX_HISTORY_MESSAGES,
    MAX_HISTORY_TOTAL_CHARS,
    MAX_REPLY_CHARS,
    MAX_STATUS_FIELD_CHARS,
    MAX_TOOL_CALLS,
    MAX_TOOL_ROUNDS,
    MAX_TOOL_TEXT_CHARS,
    STATUS_MAX_TOKENS,
    STATUS_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    TOOLS,
    clean_reply,
    sanitize_user_text,
)
from services.ai_tools import (
    ADMIN_TOOL_NAMES,
    DB_TOOL_MODELS,
    WEB_TOOL_NAMES,
    CashflowArgs,
    ClientDetailsArgs,
    ClientRankingArgs,
    DashboardOverviewArgs,
    GlobalSearchArgs,
    ListOverdueArgs,
    ListPaymentsArgs,
    ListSalesArgs,
    ListUsersArgs,
    MyProfileArgs,
    SaleDetailsArgs,
    SaleStatusArgs,
    SalesSummaryArgs,
    SearchClientsArgs,
    ToolScope,
    TopProductsArgs,
    UserSummaryArgs,
    execute_tool,
    execute_tool_async,
)
from services.ai_web import (
    MAX_FETCH_BYTES,
    MAX_FETCH_REDIRECTS,
    MAX_FETCH_TEXT_CHARS,
    WEB_SEARCH_DEFAULT_RESULTS,
    WEB_SEARCH_MAX_RESULTS,
    WEB_TIMEOUT_SECONDS,
    WEB_USER_AGENT,
    FetchUrlArgs,
    WebSearchArgs,
    _duckduckgo_search,
    _ensure_public_host,
    _html_to_text,
    _is_public_ip,
    _parse_duckduckgo,
    _tavily_search,
    _validate_public_http_url,
    fetch_url,
    web_search,
)

logger = logging.getLogger(__name__)

# Aliases históricos usados por testes/chamadas internas.
_clean_reply = clean_reply
_web_search = web_search
_fetch_url = fetch_url

__all__ = [
    "AI_TIMEOUT_SECONDS",
    "AIConfig",
    "AIConfigurationError",
    "AIProviderError",
    "AIProviderRateLimitError",
    "AIToolError",
    "ADMIN_TOOL_NAMES",
    "CHAT_MAX_TOKENS",
    "CashflowArgs",
    "ClientDetailsArgs",
    "ClientRankingArgs",
    "DB_TOOL_MODELS",
    "DashboardOverviewArgs",
    "FALLBACK_TOOL_LIMIT",
    "FetchUrlArgs",
    "GlobalSearchArgs",
    "ListOverdueArgs",
    "ListPaymentsArgs",
    "ListSalesArgs",
    "ListUsersArgs",
    "MAX_CHAT_INPUT_CHARS",
    "MAX_FETCH_BYTES",
    "MAX_FETCH_REDIRECTS",
    "MAX_FETCH_TEXT_CHARS",
    "MAX_HISTORY_MESSAGES",
    "MAX_HISTORY_TOTAL_CHARS",
    "MAX_REPLY_CHARS",
    "MAX_STATUS_FIELD_CHARS",
    "MAX_TOOL_CALLS",
    "MAX_TOOL_ROUNDS",
    "MAX_TOOL_TEXT_CHARS",
    "MyProfileArgs",
    "STATUS_MAX_TOKENS",
    "STATUS_SYSTEM_PROMPT",
    "SYSTEM_PROMPT",
    "SaleDetailsArgs",
    "SaleStatusArgs",
    "SalesSummaryArgs",
    "SearchClientsArgs",
    "TOOLS",
    "ToolScope",
    "TopProductsArgs",
    "UserSummaryArgs",
    "WEB_SEARCH_DEFAULT_RESULTS",
    "WEB_SEARCH_MAX_RESULTS",
    "WEB_TIMEOUT_SECONDS",
    "WEB_TOOL_NAMES",
    "WEB_USER_AGENT",
    "WebSearchArgs",
    "_duckduckgo_search",
    "_ensure_public_host",
    "_fetch_url",
    "_html_to_text",
    "_is_public_ip",
    "_parse_duckduckgo",
    "_tavily_search",
    "_validate_public_http_url",
    "_web_search",
    "cache",
    "execute_tool",
    "execute_tool_async",
    "generate_chat_reply",
    "generate_status_message",
    "load_ai_config",
    "sanitize_user_text",
    "web_search",
]


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "".join(parts)
    return ""


def _normalize_tool_calls(raw_calls: Any) -> list[dict[str, str]]:
    if not isinstance(raw_calls, list):
        return []
    calls: list[dict[str, str]] = []
    for index, raw in enumerate(raw_calls):
        if not isinstance(raw, dict):
            continue
        function = raw.get("function")
        if not isinstance(function, dict):
            continue
        name = function.get("name")
        arguments = function.get("arguments", "{}")
        if not isinstance(name, str) or not name:
            continue
        if not isinstance(arguments, (str, dict)):
            arguments = "{}"
        calls.append(
            {
                "id": str(raw.get("id") or f"call_{index}"),
                "name": name,
                "arguments": arguments if isinstance(arguments, str) else json.dumps(arguments),
            }
        )
    return calls


# ---------------------------------------------------------------------------
# Chamadas ao provedor de IA
# ---------------------------------------------------------------------------


def _provider_error_detail(response: httpx.Response) -> str:
    """Resumo seguro do erro do provedor: só status e código/tipo.

    O corpo de erro pode conter prompt, geração do modelo ou detalhes internos;
    por isso apenas ``error.code``/``error.type`` (quando string curta) é
    reproduzido. Nunca inclui cabeçalhos, chave ou mensagens do usuário.
    """
    base = f"HTTP {response.status_code}"
    try:
        data = response.json()
    except ValueError:
        return base
    error = data.get("error") if isinstance(data, dict) else None
    if not isinstance(error, dict):
        return base
    for key in ("code", "type"):
        value = error.get(key)
        if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", value):
            return f"{base} {value}"
    return base


async def _request_chat_completion(config: AIConfig, payload: dict[str, Any]) -> dict[str, Any]:
    """POST no endpoint OpenAI-compatível. Não registra corpo nem cabeçalhos."""
    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=AI_TIMEOUT_SECONDS) as client:
            response = await client.post(config.api_url, headers=headers, json=payload)
    except httpx.TimeoutException as exc:
        raise AIProviderError("Tempo esgotado no provedor de IA.") from exc
    except httpx.HTTPError as exc:
        raise AIProviderError("Falha de conexão com o provedor de IA.") from exc

    if response.status_code == 429:
        raise AIProviderRateLimitError("Quota do provedor de IA atingida.")
    if response.status_code >= 400:
        # ``model`` não é segredo e ajuda a diagnosticar 404 model_not_found.
        # ``!r`` revela espaços/caracteres invisíveis vindos do ambiente.
        raise AIProviderError(
            f"Provedor de IA respondeu {_provider_error_detail(response)} "
            f"(model={config.model!r})."
        )
    try:
        data = response.json()
    except ValueError as exc:
        raise AIProviderError("Resposta inválida do provedor de IA.") from exc
    if not isinstance(data, dict):
        raise AIProviderError("Resposta inválida do provedor de IA.")
    return data


async def _complete(
    config: AIConfig,
    messages: list[dict[str, Any]],
    *,
    tools: list[dict[str, Any]] | None,
    max_tokens: int,
    temperature: float,
) -> tuple[dict[str, Any], str, list[dict[str, str]]]:
    payload: dict[str, Any] = {
        "model": config.model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    # GPT-OSS (Groq) é um modelo de raciocínio: sem controlar o esforço ele
    # consome boa parte do limite "pensando" e o texto final sai vazio/cortado.
    # O parâmetro é específico desse modelo; outros provedores não o recebem.
    if config.model.startswith("openai/gpt-oss"):
        payload["reasoning_effort"] = "low"
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    data = await _request_chat_completion(config, payload)
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise AIProviderError("Resposta do provedor sem escolhas.")
    message = choices[0].get("message")
    if not isinstance(message, dict):
        raise AIProviderError("Resposta do provedor sem mensagem.")

    content = _content_text(message.get("content"))
    calls = _normalize_tool_calls(message.get("tool_calls"))
    assistant_message: dict[str, Any] = {"role": "assistant", "content": message.get("content")}
    if message.get("tool_calls"):
        assistant_message["tool_calls"] = message["tool_calls"]
    return assistant_message, content, calls


def _sanitize_history(history: list[Any] | None) -> list[dict[str, str]]:
    """Valida e limita o histórico enviado pelo frontend.

    Apenas ``user``/``assistant`` são aceitos. O conteúdo do usuário passa pela
    mesma sanitização da mensagem atual; o do assistente é limpo/limitado.
    """
    if not history:
        return []

    messages: list[dict[str, str]] = []
    total_chars = 0
    for item in list(history)[-MAX_HISTORY_MESSAGES:]:
        if isinstance(item, dict):
            role = item.get("role")
            content = item.get("content")
        else:
            role = getattr(item, "role", None)
            content = getattr(item, "content", None)
        if role not in {"user", "assistant"} or not isinstance(content, str):
            continue
        if role == "user":
            clean = sanitize_user_text(content, MAX_CHAT_INPUT_CHARS)
        else:
            clean = _clean_reply(content)[: MAX_CHAT_INPUT_CHARS * 2]
        if not clean:
            continue
        if total_chars + len(clean) > MAX_HISTORY_TOTAL_CHARS:
            break
        total_chars += len(clean)
        messages.append({"role": role, "content": clean})
    return messages


def _system_prompt(scope: ToolScope) -> str:
    role = "administrador" if scope.is_admin else "usuário comum"
    if scope.scope_id is None:
        scope_text = "global (consolidado de todos os usuários)"
    else:
        scope_text = f"restrito ao usuário interno id {scope.scope_id}"
    return SYSTEM_PROMPT.format(today=local_today().isoformat(), role=role, scope=scope_text)


async def generate_chat_reply(
    db: Session,
    user_id: int,
    message: str,
    *,
    history: list[Any] | None = None,
    is_admin: bool = False,
    owner_id: int | None = None,
) -> str:
    clean_message = sanitize_user_text(message)
    if not clean_message:
        raise ValueError("Mensagem vazia.")

    scope = ToolScope(user_id=user_id, is_admin=is_admin, owner_id=owner_id)
    config = load_ai_config()
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": _system_prompt(scope)},
        *_sanitize_history(history),
        {"role": "user", "content": clean_message},
    ]
    calls_used = 0

    for _round in range(MAX_TOOL_ROUNDS):
        assistant_message, content, calls = await _complete(
            config,
            messages,
            tools=TOOLS,
            max_tokens=CHAT_MAX_TOKENS,
            temperature=0.2,
        )
        if not calls:
            reply = _clean_reply(content)
            if not reply and calls_used:
                # Modelos de raciocínio podem devolver content vazio depois de
                # receber o resultado da ferramenta. Uma última chamada SEM
                # ferramentas força a síntese em texto (recomendação da Groq).
                _assistant, content, _ignored = await _complete(
                    config,
                    messages,
                    tools=None,
                    max_tokens=CHAT_MAX_TOKENS,
                    temperature=0.2,
                )
                reply = _clean_reply(content)
            if not reply:
                raise AIProviderError("O provedor não retornou texto.")
            logger.info(
                "ai_chat_completed user_id=%s tool_calls=%s scope=%s",
                user_id,
                calls_used,
                scope.scope_key,
            )
            return reply

        messages.append(assistant_message)
        for call in calls:
            if calls_used >= MAX_TOOL_CALLS:
                logger.warning("ai_tool_limit_reached user_id=%s", user_id)
                return FALLBACK_TOOL_LIMIT
            calls_used += 1
            try:
                result = await execute_tool_async(db, scope, call["name"], call["arguments"])
                tool_content = json.dumps(result, ensure_ascii=False, default=str)
            except AIToolError as exc:
                tool_content = json.dumps({"error": str(exc)}, ensure_ascii=False)
            except Exception as exc:  # noqa: BLE001 - erro inesperado vira mensagem genérica
                logger.error(
                    "ai_tool_failed user_id=%s tool=%s error_type=%s",
                    user_id,
                    call["name"],
                    type(exc).__name__,
                )
                tool_content = json.dumps(
                    {"error": "Falha ao consultar os dados. Tente novamente."},
                    ensure_ascii=False,
                )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": tool_content,
                }
            )

    logger.warning("ai_tool_limit_reached user_id=%s", user_id)
    return FALLBACK_TOOL_LIMIT


async def generate_status_message(
    user_id: int,
    motivo: str,
    cliente: str | None = None,
    pedido: str | None = None,
) -> str:
    clean_reason = sanitize_user_text(motivo, MAX_STATUS_FIELD_CHARS)
    clean_client = sanitize_user_text(cliente, 100) if cliente else ""
    clean_order = sanitize_user_text(pedido, 60) if pedido else ""
    if not clean_reason:
        raise ValueError("Motivo vazio.")

    config = load_ai_config()
    user_prompt = (
        f"Motivo: {clean_reason}\n"
        f"Cliente: {clean_client or 'não informado'}\n"
        f"Pedido: {clean_order or 'não informado'}"
    )
    _assistant, content, calls = await _complete(
        config,
        [
            {"role": "system", "content": STATUS_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        tools=None,
        max_tokens=STATUS_MAX_TOKENS,
        temperature=0.4,
    )
    if calls:
        raise AIProviderError("O provedor tentou usar ferramenta na geração de status.")
    text = _clean_reply(content)
    if not text:
        raise AIProviderError("O provedor não retornou texto.")
    logger.info("ai_status_message_completed user_id=%s", user_id)
    return text
