"""Schemas do assistente de IA.

As entradas são deliberadamente pequenas e fechadas: o chat aceita a mensagem
atual e um histórico opcional (apenas ``user``/``assistant``); a geração de
status aceita motivo + identificadores. Não existe campo de ``user_id`` — o dono
dos dados vem sempre do JWT/``resolve_data_owner``.
"""
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ChatHistoryMessage(BaseModel):
    """Uma mensagem anterior do chat, já no formato role/content."""

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=6000)

    @field_validator("content")
    @classmethod
    def strip_content(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Conteúdo vazio.")
        return value


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    history: list[ChatHistoryMessage] = Field(default_factory=list, max_length=12)

    @field_validator("message")
    @classmethod
    def strip_message(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Mensagem vazia.")
        return value


class StatusMessageRequest(BaseModel):
    motivo: str = Field(min_length=1, max_length=200)
    cliente: str | None = Field(default=None, max_length=100)
    pedido: str | None = Field(default=None, max_length=60)

    @field_validator("motivo")
    @classmethod
    def strip_reason(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Motivo vazio.")
        return value

    @field_validator("cliente", "pedido")
    @classmethod
    def strip_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class ChatResponse(BaseModel):
    reply: str


class StatusMessageResponse(BaseModel):
    message: str
