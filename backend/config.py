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

    class Config:
        env_file = ".env"


settings = Settings()

#meu arquivo de configuração do backend
