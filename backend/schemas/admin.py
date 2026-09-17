"""Schemas da gestão de dados (admin): exportação, importação e reset.

O formato exportado é um JSON consolidado com uma chave por tabela de dados.
Na importação, o mesmo formato é validado com Pydantic antes de persistir.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field


class ClientExport(BaseModel):
    id: int
    full_name: str
    name_normalized: str
    whatsapp: Optional[str] = None
    created_by_id: int
    created_at: Optional[datetime] = None


class SaleExport(BaseModel):
    id: int
    client_id: int
    user_id: int
    sale_date: date
    status: str
    total: Decimal
    amount_paid: Decimal
    remaining: Decimal
    due_date: Optional[date] = None
    created_at: Optional[datetime] = None


class SaleItemExport(BaseModel):
    id: int
    sale_id: int
    product_name: str
    quantity: int
    unit_price: Decimal
    subtotal: Decimal


class PaymentExport(BaseModel):
    id: int
    sale_id: int
    amount_paid: Decimal
    payment_date: date
    new_due_date: Optional[date] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None


class PushSubscriptionExport(BaseModel):
    id: int
    user_id: int
    endpoint: str
    p256dh: str
    auth: str
    created_at: Optional[datetime] = None


class DataTables(BaseModel):
    clients: list[ClientExport] = Field(default_factory=list)
    sales: list[SaleExport] = Field(default_factory=list)
    sale_items: list[SaleItemExport] = Field(default_factory=list)
    payments: list[PaymentExport] = Field(default_factory=list)
    push_subscriptions: list[PushSubscriptionExport] = Field(default_factory=list)


class ExportPayload(BaseModel):
    """Documento completo exportado por GET /admin/database/export."""

    version: int = 1
    exported_at: datetime
    tables: DataTables


class ImportResult(BaseModel):
    mode: Literal["skip", "overwrite"]
    inserted: dict[str, int]
    skipped: dict[str, int]
    updated: dict[str, int]


class ResetRequest(BaseModel):
    """Corpo do POST /admin/database/reset.

    `confirm` precisa ser exatamente `true` para evitar reset acidental.
    """

    confirm: bool = False


class ResetResult(BaseModel):
    cleared: dict[str, int]
    preserved: list[str]