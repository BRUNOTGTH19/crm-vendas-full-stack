from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "CRM Vendas API"
    environment: str = "development"

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
        env_file = ".env"


settings = Settings()

#meu arquivo de configuração do backend
