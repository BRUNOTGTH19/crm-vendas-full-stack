from sqlalchemy import Column, Integer, String, Enum, DateTime, Date, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from database import Base


class SaleStatus(str, enum.Enum):
    paid = "paid"
    pending = "pending"


class Sale(Base):
    __tablename__ = "sales"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    sale_date = Column(Date, nullable=False)
    status = Column(Enum(SaleStatus), nullable=False, default=SaleStatus.pending)
    total = Column(Numeric(10, 2), nullable=False, default=0)
    due_date = Column(Date, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    client = relationship("Client", back_populates="sales")
    user = relationship("User", back_populates="sales")
    items = relationship("SaleItem", back_populates="sale", cascade="all, delete-orphan")
