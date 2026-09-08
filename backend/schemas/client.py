from datetime import datetime

from pydantic import BaseModel, field_validator


class ClientCreate(BaseModel):
    full_name: str

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError("O nome deve ter pelo menos 3 caracteres")
        return value


class ClientResponse(BaseModel):
    id: int
    full_name: str
    name_normalized: str
    created_by_id: int
    created_at: datetime

    class Config:
        from_attributes = True