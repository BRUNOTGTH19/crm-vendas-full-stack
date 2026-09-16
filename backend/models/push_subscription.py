from sqlalchemy import Column, DateTime, Integer, String, ForeignKey
from sqlalchemy.sql import func

from database import Base


class PushSubscription(Base):
    """Subscrição Web Push de um dispositivo (endpoint + chaves do navegador).

    Cada usuário pode ter várias subscrições (celular, desktop, etc.).
    """

    __tablename__ = "push_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    endpoint = Column(String(500), nullable=False, unique=True, index=True)
    p256dh = Column(String(200), nullable=False)
    auth = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())