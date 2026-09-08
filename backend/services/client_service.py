import unicodedata

from sqlalchemy.orm import Session

from models.client import Client
from schemas.client import ClientCreate


def normalize_name(name: str) -> str:
    """Normaliza o nome: minúsculas, sem acentos e com espaços colapsados."""
    name = name.strip().lower()
    name = "".join(
        char for char in unicodedata.normalize("NFD", name)
        if unicodedata.category(char) != "Mn"
    )
    return " ".join(name.split())


def create_client(db: Session, data: ClientCreate, user_id: int) -> Client:
    name_normalized = normalize_name(data.full_name)
    existing = (
        db.query(Client)
        .filter(Client.name_normalized == name_normalized)
        .first()
    )
    if existing:
        raise ValueError("Já existe um cliente com esse nome")

    client = Client(
        full_name=data.full_name.strip(),
        name_normalized=name_normalized,
        created_by_id=user_id,
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


def list_clients(db: Session, search: str | None = None) -> list[Client]:
    query = db.query(Client)
    if search:
        term = normalize_name(search)
        query = query.filter(Client.name_normalized.like(f"%{term}%"))
    return query.order_by(Client.full_name).all()


def get_client(db: Session, client_id: int) -> Client | None:
    return db.query(Client).filter(Client.id == client_id).first()


def update_client(db: Session, client: Client, data: ClientUpdate) -> Client:
    name_normalized = normalize_name(data.full_name)
    existing = (
        db.query(Client)
        .filter(Client.name_normalized == name_normalized, Client.id != client.id)
        .first()
    )
    if existing:
        raise ValueError("Já existe um cliente com esse nome")

    client.full_name = data.full_name.strip()
    client.name_normalized = name_normalized
    db.commit()
    db.refresh(client)
    return client


def delete_client(db: Session, client: Client) -> None:
    if client.sales:
        raise ValueError("Cliente possui vendas registradas e não pode ser excluído")
    db.delete(client)
    db.commit()