from sqlalchemy import Column, DateTime, Integer, String, Text, ForeignKey
from sqlalchemy.sql import func

from database import Base


class AuditLog(Base):
    """Registro de auditoria de ações administrativas sensíveis.

    Guarda quem executou, o que foi feito e um detalhe livre (ex.: tabelas
    afetadas, contagens). Usado pelas rotas de gestão de dados (admin).
    """

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False, index=True)
    detail = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)