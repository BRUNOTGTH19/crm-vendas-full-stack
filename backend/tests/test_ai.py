"""Testes do assistente de IA.

Cobrem os pontos de segurança combinados:

- sem JWT -> 401;
- ``user_id`` vem do token, nunca dos argumentos da tool;
- argumentos inválidos são rejeitados sem executar SQL;
- limite de iterações de tool calls;
- 429 (quota) e 503 (configuração ausente);
- geração de status sem tools e sem gravar no banco.

Todos os serviços externos (provedor de IA e Redis) são simulados pelo
``conftest.py``/monkeypatch; o banco é o SQLite em memória dos testes.
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from database import SessionLocal
from main import app
from models.client import Client
from models.sale import Sale, SaleStatus
from models.user import User
from routers.ai import RATE_LIMIT_MESSAGE, UNAVAILABLE_MESSAGE
from services import ai_service
from services.auth_service import create_access_token

client = TestClient(app)


def _configure_ai(monkeypatch) -> None:
    monkeypatch.setenv("AI_API_URL", "https://example.invalid/v1/chat/completions")
    monkeypatch.setenv("AI_API_KEY", "test-key-not-real")
    monkeypatch.setenv("AI_MODEL", "test-model")


def _auth(user_id: int) -> dict[str, str]:
    token = create_access_token({"sub": str(user_id)})
    return {"Authorization": f"Bearer {token}"}


def _completion(content: str | None = None, tool_calls: list[dict] | None = None) -> dict:
    message: dict = {"role": "assistant", "content": content}
    if tool_calls:
        message["tool_calls"] = tool_calls
    return {"choices": [{"message": message}]}


def _tool_call(call_id: str, name: str, arguments: dict) -> dict:
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments)},
    }


@pytest.fixture(scope="module")
def seed(isolated_services):
    """Cria dois usuários e vendas com valores distintos para provar o escopo."""
    stamp = datetime.now(timezone.utc).strftime("%H%M%S%f")
    with SessionLocal() as db:
        user_a = User(
            name="Usuario IA A",
            email=f"ai_a_{stamp}@example.com",
            password_hash="hash-de-teste",
            role="user",
        )
        user_b = User(
            name="Usuario IA B",
            email=f"ai_b_{stamp}@example.com",
            password_hash="hash-de-teste",
            role="user",
        )
        db.add_all([user_a, user_b])
        db.flush()

        client_a = Client(
            full_name="Cliente IA A",
            name_normalized=f"cliente-ia-a-{stamp}",
            created_by_id=user_a.id,
        )
        client_b = Client(
            full_name="Cliente IA B",
            name_normalized=f"cliente-ia-b-{stamp}",
            created_by_id=user_b.id,
        )
        db.add_all([client_a, client_b])
        db.flush()

        sale_a_paid = Sale(
            client_id=client_a.id,
            user_id=user_a.id,
            sale_date=date(2026, 10, 5),
            status=SaleStatus.paid,
            total=100,
            amount_paid=100,
            remaining=0,
        )
        sale_a_pending = Sale(
            client_id=client_a.id,
            user_id=user_a.id,
            sale_date=date(2026, 10, 10),
            status=SaleStatus.pending,
            total=50,
            amount_paid=10,
            remaining=40,
            due_date=date(2020, 1, 1),
        )
        sale_b = Sale(
            client_id=client_b.id,
            user_id=user_b.id,
            sale_date=date(2026, 10, 6),
            status=SaleStatus.paid,
            total=9999,
            amount_paid=9999,
            remaining=0,
        )
        db.add_all([sale_a_paid, sale_a_pending, sale_b])
        db.commit()
        db.refresh(sale_a_paid)
        db.refresh(sale_a_pending)
        db.refresh(sale_b)
        return {
            "user_a": user_a.id,
            "user_b": user_b.id,
            "sale_a_paid": sale_a_paid.id,
            "sale_a_pending": sale_a_pending.id,
            "sale_b": sale_b.id,
        }


def _second_call_payload(mock: AsyncMock) -> dict:
    assert mock.await_count >= 2
    return mock.await_args_list[1].args[1]


def _tool_message(payload: dict) -> dict:
    messages = payload["messages"]
    tool_messages = [m for m in messages if m.get("role") == "tool"]
    assert tool_messages, messages
    return json.loads(tool_messages[-1]["content"])


# ---------------------------------------------------------------------------
# Autenticação e configuração
# ---------------------------------------------------------------------------
def test_chat_without_jwt_is_blocked():
    response = client.post("/ai/chat", json={"message": "Quanto vendi?"})
    assert response.status_code == 401


def test_status_message_without_jwt_is_blocked():
    response = client.post("/ai/status-message", json={"motivo": "Pedido atrasou"})
    assert response.status_code == 401


def test_chat_returns_503_without_ai_environment(monkeypatch, seed):
    for name in ("AI_API_URL", "AI_API_KEY", "AI_MODEL"):
        monkeypatch.delenv(name, raising=False)

    response = client.post(
        "/ai/chat",
        json={"message": "Quanto vendi?"},
        headers=_auth(seed["user_a"]),
    )
    assert response.status_code == 503
    assert response.json()["detail"] == UNAVAILABLE_MESSAGE
    # A mensagem não pode revelar qual variável falta.
    assert "AI_API" not in response.text


def test_chat_returns_429_when_provider_quota_is_exhausted(monkeypatch, seed):
    _configure_ai(monkeypatch)
    provider = AsyncMock(side_effect=ai_service.AIProviderRateLimitError("quota"))
    monkeypatch.setattr(ai_service, "_request_chat_completion", provider)

    response = client.post(
        "/ai/chat",
        json={"message": "Quanto vendi?"},
        headers=_auth(seed["user_a"]),
    )
    assert response.status_code == 429
    assert response.json()["detail"] == RATE_LIMIT_MESSAGE


def test_logs_do_not_contain_prompt_reply_or_api_key(monkeypatch, seed, caplog):
    _configure_ai(monkeypatch)
    provider = AsyncMock(return_value=_completion("Resposta confidencial do provedor."))
    monkeypatch.setattr(ai_service, "_request_chat_completion", provider)

    caplog.set_level(logging.INFO, logger=ai_service.__name__)
    response = client.post(
        "/ai/chat",
        json={"message": "Minha pergunta confidencial"},
        headers=_auth(seed["user_a"]),
    )

    assert response.status_code == 200
    assert "ai_chat_completed" in caplog.text
    assert "test-key-not-real" not in caplog.text
    assert "Minha pergunta confidencial" not in caplog.text
    assert "Resposta confidencial do provedor." not in caplog.text


# ---------------------------------------------------------------------------
# Escopo e ferramentas somente leitura
# ---------------------------------------------------------------------------
def test_tool_uses_user_id_from_token_not_from_model(monkeypatch, seed):
    _configure_ai(monkeypatch)
    provider = AsyncMock(
        side_effect=[
            _completion(
                tool_calls=[
                    _tool_call(
                        "call_1",
                        "get_sales_summary",
                        {
                            "inicio": "2026-10-01",
                            "fim": "2026-10-31",
                            # Tentativa de trocar o dono dos dados:
                            "user_id": seed["user_b"],
                        },
                    )
                ]
            ),
            _completion("Não consegui consultar."),
        ]
    )
    monkeypatch.setattr(ai_service, "_request_chat_completion", provider)

    response = client.post(
        "/ai/chat",
        json={"message": "Quanto vendi em outubro?"},
        headers=_auth(seed["user_a"]),
    )
    assert response.status_code == 200, response.text
    payload = _second_call_payload(provider)
    tool_result = _tool_message(payload)
    assert "error" in tool_result
    assert "user_id" in tool_result["error"]
    assert "9999" not in json.dumps(tool_result)


def test_sales_summary_is_aggregated_and_scoped(monkeypatch, seed):
    _configure_ai(monkeypatch)
    provider = AsyncMock(
        side_effect=[
            _completion(
                tool_calls=[
                    _tool_call(
                        "call_1",
                        "get_sales_summary",
                        {"inicio": "2026-10-01", "fim": "2026-10-31"},
                    )
                ]
            ),
            _completion("Você vendeu R$ 150,00 no período."),
        ]
    )
    monkeypatch.setattr(ai_service, "_request_chat_completion", provider)

    response = client.post(
        "/ai/chat",
        json={"message": "Quanto vendi em outubro?"},
        headers=_auth(seed["user_a"]),
    )
    assert response.status_code == 200
    assert response.json()["reply"] == "Você vendeu R$ 150,00 no período."

    result = _tool_message(_second_call_payload(provider))
    assert result["sales_count"] == 2
    assert result["total"] == 150.0
    assert result["paid_total"] == 100.0
    assert result["pending_total"] == 40.0
    # A venda do usuário B (9999) nunca entra no agregado.
    assert "9999" not in json.dumps(result)


def test_overdue_list_only_returns_own_pending_sales(monkeypatch, seed):
    _configure_ai(monkeypatch)
    provider = AsyncMock(
        side_effect=[
            _completion(tool_calls=[_tool_call("call_1", "list_overdue", {})]),
            _completion("Há uma cobrança em atraso."),
        ]
    )
    monkeypatch.setattr(ai_service, "_request_chat_completion", provider)

    response = client.post(
        "/ai/chat",
        json={"message": "Quais cobranças estão atrasadas?"},
        headers=_auth(seed["user_a"]),
    )
    assert response.status_code == 200
    result = _tool_message(_second_call_payload(provider))
    assert result["total_count"] == 1
    assert result["sales"][0]["sale_id"] == seed["sale_a_pending"]
    assert result["sales"][0]["remaining"] == 40.0
    assert "whatsapp" not in json.dumps(result)
    assert "email" not in json.dumps(result)


def test_sale_status_from_another_user_is_not_found(monkeypatch, seed):
    _configure_ai(monkeypatch)
    provider = AsyncMock(
        side_effect=[
            _completion(
                tool_calls=[
                    _tool_call("call_1", "get_sale_status", {"sale_id": seed["sale_b"]})
                ]
            ),
            _completion("Venda não encontrada."),
        ]
    )
    monkeypatch.setattr(ai_service, "_request_chat_completion", provider)

    response = client.post(
        "/ai/chat",
        json={"message": "Qual o status da venda?"},
        headers=_auth(seed["user_a"]),
    )
    assert response.status_code == 200
    result = _tool_message(_second_call_payload(provider))
    assert result == {"found": False, "sale_id": seed["sale_b"]}


def test_extra_user_id_in_tool_arguments_is_rejected(seed):
    with SessionLocal() as db:
        with pytest.raises(ai_service.AIToolError):
            ai_service.execute_tool(
                db,
                seed["user_a"],
                "get_sales_summary",
                {
                    "inicio": "2026-10-01",
                    "fim": "2026-10-31",
                    "user_id": seed["user_b"],
                },
            )
        with pytest.raises(ai_service.AIToolError):
            ai_service.execute_tool(
                db,
                seed["user_a"],
                "list_overdue",
                {"user_id": seed["user_b"]},
            )


def test_invalid_tool_arguments_are_reported_without_executing_sql(monkeypatch, seed):
    _configure_ai(monkeypatch)
    provider = AsyncMock(
        side_effect=[
            _completion(
                tool_calls=[_tool_call("call_1", "get_sale_status", {"sale_id": "abc"})]
            ),
            _completion("Não consegui identificar a venda."),
        ]
    )
    monkeypatch.setattr(ai_service, "_request_chat_completion", provider)

    response = client.post(
        "/ai/chat",
        json={"message": "Status da venda abc"},
        headers=_auth(seed["user_a"]),
    )
    assert response.status_code == 200
    result = _tool_message(_second_call_payload(provider))
    assert "error" in result
    assert "sale_id" in result["error"]


def test_inverted_date_range_is_rejected(seed):
    with SessionLocal() as db, pytest.raises(ai_service.AIToolError):
        ai_service.execute_tool(
            db,
            seed["user_a"],
            "get_sales_summary",
            {"inicio": "2026-10-31", "fim": "2026-10-01"},
        )


def test_tool_iteration_limit_stops_the_model(monkeypatch, seed):
    _configure_ai(monkeypatch)
    provider = AsyncMock(
        return_value=_completion(tool_calls=[_tool_call("call_1", "list_overdue", {})])
    )
    monkeypatch.setattr(ai_service, "_request_chat_completion", provider)

    response = client.post(
        "/ai/chat",
        json={"message": "Liste as atrasadas"},
        headers=_auth(seed["user_a"]),
    )
    assert response.status_code == 200
    assert response.json()["reply"] == ai_service.FALLBACK_TOOL_LIMIT
    assert provider.await_count == ai_service.MAX_TOOL_ROUNDS


def test_tool_cache_key_is_scoped_by_user(monkeypatch, seed):
    seen_keys: list[str] = []

    def fake_get_json(key: str):
        seen_keys.append(key)
        return {"cached": True}

    monkeypatch.setattr(ai_service.cache, "get_json", fake_get_json)
    with SessionLocal() as db:
        args = {"inicio": "2026-10-01", "fim": "2026-10-31"}
        assert ai_service.execute_tool(db, seed["user_a"], "get_sales_summary", args) == {
            "cached": True
        }
        assert ai_service.execute_tool(db, seed["user_b"], "get_sales_summary", args) == {
            "cached": True
        }
    assert len(seen_keys) == 2
    assert seen_keys[0] != seen_keys[1]
    assert f":{seed['user_a']}:" in seen_keys[0]
    assert f":{seed['user_b']}:" in seen_keys[1]


# ---------------------------------------------------------------------------
# Geração de frase de status
# ---------------------------------------------------------------------------
def test_status_message_uses_no_tools_and_redacts_sensitive_data(monkeypatch, seed):
    _configure_ai(monkeypatch)
    provider = AsyncMock(return_value=_completion("Olá! Seu pedido 123 atrasou um dia."))
    monkeypatch.setattr(ai_service, "_request_chat_completion", provider)

    response = client.post(
        "/ai/status-message",
        json={
            "motivo": "Pedido atrasou; contato 11999998888 ou foo@example.com",
            "cliente": "Cliente Exemplo",
            "pedido": "123",
        },
        headers=_auth(seed["user_a"]),
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Olá! Seu pedido 123 atrasou um dia."

    payload = provider.await_args.args[1]
    assert "tools" not in payload
    assert payload["max_tokens"] == ai_service.STATUS_MAX_TOKENS
    serialized = json.dumps(payload, ensure_ascii=False)
    assert "11999998888" not in serialized
    assert "foo@example.com" not in serialized
    assert "Pedido atrasou" in serialized


def test_status_message_returns_503_without_ai_environment(monkeypatch, seed):
    for name in ("AI_API_URL", "AI_API_KEY", "AI_MODEL"):
        monkeypatch.delenv(name, raising=False)

    response = client.post(
        "/ai/status-message",
        json={"motivo": "Pedido atrasou"},
        headers=_auth(seed["user_a"]),
    )
    assert response.status_code == 503
    assert response.json()["detail"] == UNAVAILABLE_MESSAGE
