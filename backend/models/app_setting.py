from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from database import Base


class AppSetting(Base):
    """Configuração chave-valor persistida no banco.

    Usada, por exemplo, para guardar o par de chaves VAPID gerado
    automaticamente quando as variáveis de ambiente não estão definidas.
    Persistir no banco garante que as chaves permaneçam estáveis entre
    reinícios do servidor (essencial para o Web Push: se a chave mudar,
    as subscrições existentes deixam de funcionar).
    """

    __tablename__ = "app_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), nullable=False, unique=True, index=True)
    value = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
