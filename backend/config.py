from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings

# Caminho absoluto para o .env, independente do diretório de trabalho (CWD).
# Sem isso, iniciar o servidor de fora de `backend/` faria o pydantic-settings
# não encontrar o arquivo e as chaves VAPID ficariam vazias.
ENV_FILE = Path(__file__).resolve().parent / ".env"


class Settings(BaseSettings):

    app_name: str = "CRM Vendas API"
    environment: str = "development"
    allow_database_reset: bool = False

    database_url: str
    redis_url: str

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 480  # 8 horas
    refresh_token_expire_days: int = 7

    # --- Web Push (notificações de alerta de prazo de vendas) ---
    # Gere o par de chaves com: python gen_vapid_keys.py
    # A pública vai para o frontend (applicationServerKey); a privada fica aqui.
    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_subject: str = "mailto:admin@crm-vendas.com"

    # Zero preserva a regra atual: hoje e atrasadas. Ex.: 1 inclui amanhã.
    reminder_days_before: int = Field(default=0, ge=0, le=30)
    reminder_hour: int = Field(default=8, ge=0, le=23)
    reminder_timezone: str = "UTC"

    @field_validator("reminder_timezone")
    @classmethod
    def valid_reminder_timezone(cls, value: str) -> str:
        ZoneInfo(value)
        return value

    # --- Cobrança / WhatsApp (100% grátis, sem API paga) ---
    # Nome exibido no rodapé da mensagem de cobrança.
    company_name: str = "CRM Vendas"
    # Template da mensagem de cobrança personalizada. Placeholders:
    # {cliente}, {venda}, {valor}, {vencimento}, {situacao}, {empresa}
    collection_message_template: str = (
        "Olá {cliente}! Tudo bem? 😊\n"
        "Passando para lembrar do seu pagamento referente à venda #{venda}.\n"
        "💰 Valor em aberto: {valor}\n"
        "📅 Vencimento: {vencimento}\n"
        "{situacao}"
        "Segue em anexo o recibo com os detalhes da sua compra.\n"
        "Qualquer dúvida, estou à disposição. Obrigado!"
    )

    class Config:
        env_file = str(ENV_FILE)
        env_file_encoding = "utf-8"


settings = Settings()

#meu arquivo de configuração do backend
