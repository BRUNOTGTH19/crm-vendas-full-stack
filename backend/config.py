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

    # Habilita o reset de dados (POST /admin/database/reset).
    # Opt-in: DESLIGADO por padrão. Em produção, só ligue
    # ALLOW_DATABASE_RESET=true durante a operação de zerar os dados e desligue
    # em seguida. Um admin comprometido não consegue apagar a base sem isso.
    allow_database_reset: bool = False

    # Redefinição "simples" de senha (POST /auth/reset-password): basta o e-mail
    # cadastrado + a nova senha. É um vetor de tomada de conta (A1 da auditoria),
    # por isso vem DESLIGADA. O fluxo seguro por token continua disponível em
    # /auth/reset-password/confirm e o admin gera o token na área de gestão.
    allow_legacy_password_reset: bool = False

    # Custo do bcrypt. 11 mantém boa margem de segurança e responde ~2x mais
    # rápido que o padrão 12 do passlib (que dominava o tempo do login).
    bcrypt_rounds: int = Field(default=11, ge=10, le=14)

    # Cota de mensagens do assistente de IA por usuário/hora (A3 da auditoria).
    # Cada mensagem pode gerar várias chamadas ao provedor; 0 desabilita a IA.
    ai_max_messages_per_hour: int = Field(default=30, ge=0, le=1000)

    # Onde os contadores de rate limit vivem (A17 da auditoria).
    # "memory": um contador por processo (padrão, sem dependências).
    # "redis": contador compartilhado entre instâncias; com Redis indisponível
    # o limite volta para a memória em vez de derrubar o login.
    rate_limit_backend: str = "memory"

    # Origens permitidas no CORS, separadas por vírgula. "*" libera todas
    # (adequado para um app público sem cookies). Nunca combine "*" com
    # credenciais: o token viaja no header Authorization, não em cookie.
    cors_allow_origins: str = "*"

    database_url: str
    redis_url: str

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 480  # 8 horas
    refresh_token_expire_days: int = 7

    # Bootstrap de administrador: e-mail que deve ser promovido a admin no
    # login/validação do token. Deixe vazio (padrão) para não promover ninguém.
    # O cadastro público nunca cria admin; defina ADMIN_EMAIL no Render para
    # liberar a área administrativa para a sua conta já cadastrada.
    admin_email: str = ""

    # Alternativa de ativação: código secreto que o usuário logado digita no
    # app para virar admin. Se vazio, o backend gera um código aleatório na
    # primeira vez que alguém abre o app sem existir admin e o registra no log
    # do servidor (Render/terminal). O código gerado é de uso único.
    admin_setup_code: str = ""

    # --- Recuperação de senha por e-mail (self-service) ---
    # Com SMTP configurado, o usuário pede o link em "Esqueci minha senha" e
    # recebe um token de uso único. Sem SMTP, o endpoint continua respondendo de
    # forma genérica, mas quem redefine é o administrador (token no painel ou
    # ``manage.py set-password`` no servidor).
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_starttls: bool = True
    # URL pública do frontend usada no link do e-mail (ex.: https://app.vercel.app).
    app_public_url: str = ""

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

    @field_validator("rate_limit_backend")
    @classmethod
    def valid_rate_limit_backend(cls, value: str) -> str:
        normalized = (value or "memory").strip().lower()
        if normalized not in {"memory", "redis"}:
            raise ValueError("RATE_LIMIT_BACKEND deve ser 'memory' ou 'redis'.")
        return normalized

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
