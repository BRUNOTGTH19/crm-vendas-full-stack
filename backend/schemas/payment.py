from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class PaymentCreate(BaseModel):
    sale_id: int
    amount_paid: Decimal
    payment_date: date
    new_due_date: Optional[date] = None
    notes: Optional[str] = None


class PaymentResponse(BaseModel):
    id: int
    sale_id: int
    amount_paid: Decimal
    payment_date: date
    new_due_date: Optional[date]
    notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
