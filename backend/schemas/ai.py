"""Schemas do assistente de IA.

As entradas são deliberadamente pequenas e fechadas: o chat aceita apenas uma
mensagem de texto e a geração de status aceita motivo + identificadores. Não
existe campo de ``user_id`` — o dono dos dados vem sempre do JWT.
"""
from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)

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
