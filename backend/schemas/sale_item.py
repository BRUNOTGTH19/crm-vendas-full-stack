from decimal import Decimal

from pydantic import BaseModel, field_validator


class SaleItemCreate(BaseModel):
    product_name: str
    quantity: int
    unit_price: Decimal

    @field_validator("product_name")
    @classmethod
    def validate_product_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("O nome do produto é obrigatório")
        return value

    @field_validator("quantity")
    @classmethod
    def validate_quantity(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("A quantidade deve ser maior que zero")
        return value

    @field_validator("unit_price")
    @classmethod
    def validate_unit_price(cls, value: Decimal) -> Decimal:
        if value < 0:
            raise ValueError("O preço unitário não pode ser negativo")
        return value


class SaleItemResponse(BaseModel):
    id: int
    sale_id: int
    product_name: str
    quantity: int
    unit_price: Decimal
    subtotal: Decimal

    class Config:
        from_attributes = True