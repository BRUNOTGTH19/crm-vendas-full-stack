from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class CollectionReminder(BaseModel):
    """Lembrete de vencimento exibido na central de cobranças.

    Um lembrete existe para toda venda pendente que vence hoje ou que já venceu.
    É o mesmo conjunto de vendas que o APScheduler marca em Redis.
    """

    sale_id: int
    client_id: int
    client_name: str
    whatsapp: Optional[str] = None
    situation: str  # "vencida" | "hoje" | "a-vencer"
    amount: Decimal
    due_date: Optional[date] = None
    scheduled: bool = False


class CollectionMessage(BaseModel):
    """Mensagem de cobrança personalizada pronta para envio via WhatsApp."""

    sale_id: int
    client_id: int
    client_name: str
    whatsapp: Optional[str] = None
    whatsapp_digits: Optional[str] = None
    has_phone: bool
    amount: Decimal
    due_date: Optional[date] = None
    situation: str  # "vencida" | "hoje" | "a-vencer"
    message: str
    wa_link: Optional[str] = None