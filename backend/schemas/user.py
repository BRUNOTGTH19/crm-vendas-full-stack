from pydantic import BaseModel, EmailStr, Field
from typing import Literal
from datetime import datetime
from models.user import UserRole


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: Literal["user"] = "user"


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class PasswordResetRequest(BaseModel):
    """Corpo do POST /auth/reset-password (redefinição simples, sem link/código).

    Disponibilizado na tela de login para quem esqueceu a senha. ATENÇÃO: por
    decisão de produto, basta o e-mail cadastrado — qualquer pessoa que saiba
    o e-mail pode trocar a senha. O endpoint é protegido por rate limit por IP.
    """

    email: EmailStr
    new_password: str = Field(min_length=6, max_length=128)


class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    role: UserRole
    created_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
