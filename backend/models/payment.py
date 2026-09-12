from sqlalchemy import Column, DateTime, Date, Integer, String, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    sale_id = Column(Integer, ForeignKey("sales.id"), nullable=False)
    amount_paid = Column(Numeric(10, 2), nullable=False)
    payment_date = Column(Date, nullable=False)
    new_due_date = Column(Date, nullable=True)
    notes = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    sale = relationship("Sale", back_populates="payments")
