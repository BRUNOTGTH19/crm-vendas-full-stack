from pydantic import BaseModel, model_validator
from typing import Optional, List
from datetime import date, datetime
from decimal import Decimal
from models.sale import SaleStatus
from schemas.sale_item import SaleItemCreate, SaleItemResponse


class SaleCreate(BaseModel):
    client_id: int
    sale_date: date
    status: SaleStatus
    due_date: Optional[date] = None
    items: List[SaleItemCreate]

    @model_validator(mode="after")
    def check_due_date_if_pending(self):
        if self.status == SaleStatus.pending and not self.due_date:
            raise ValueError("due_date é obrigatório para vendas pendentes")
        return self


class SaleResponse(BaseModel):
    id: int
    client_id: int
    user_id: int
    sale_date: date
    status: SaleStatus
    total: Decimal
    due_date: Optional[date]
    created_at: datetime
    items: List[SaleItemResponse]

    class Config:
        from_attributes = True