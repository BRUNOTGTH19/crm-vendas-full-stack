import unicodedata

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.client import Client
from schemas.client import ClientCreate, ClientUpdate

NAME_CONFLICT_MESSAGE = "Já existe um cliente com esse nome"


def normalize_name(name: str) -> str:
    """Normaliza o nome: minúsculas, sem acentos e com espaços colapsados."""
    name = name.strip().lower()
    name = "".join(
        char for char in unicodedata.normalize("NFD", name)
        if unicodedata.category(char) != "Mn"
    )
    return " ".join(name.split())


def _commit(db: Session) -> None:
    """Grava o cliente traduzindo conflito de nome em erro de negócio.

    A checagem acima é por DONO, mas o índice ``clients.name_normalized`` é
    GLOBAL (migration inicial). Renomear/criar um cliente com nome já usado
    por outro usuário passava pela checagem, estourava ``IntegrityError`` no
    commit e a API devolvia 500 — agora vira 400 com mensagem clara.
    """
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ValueError(NAME_CONFLICT_MESSAGE) from exc


def create_client(db: Session, data: ClientCreate, user_id: int) -> Client:
    name_normalized = normalize_name(data.full_name)
    # Unicidade por DONO: cada usuário pode ter o próprio cadastro do mesmo
    # nome; nomes iguais só conflitam dentro da mesma base de dados.
    existing = (
        db.query(Client)
        .filter(
            Client.name_normalized == name_normalized,
            Client.created_by_id == user_id,
        )
        .first()
    )
    if existing:
        raise ValueError(NAME_CONFLICT_MESSAGE)

    client = Client(
        full_name=data.full_name.strip(),
        name_normalized=name_normalized,
        whatsapp=(data.whatsapp or "").strip() or None,
        created_by_id=user_id,
    )
    db.add(client)
    _commit(db)
    db.refresh(client)
    return client


def list_clients(
    db: Session, search: str | None = None, owner_id: int | None = None
) -> list[Client]:
    query = db.query(Client)
    if owner_id is not None:
        query = query.filter(Client.created_by_id == owner_id)
    if search:
        term = normalize_name(search)
        query = query.filter(Client.name_normalized.like(f"%{term}%"))
    return query.order_by(Client.full_name).all()


def get_client(db: Session, client_id: int, owner_id: int | None = None) -> Client | None:
    query = db.query(Client).filter(Client.id == client_id)
    if owner_id is not None:
        query = query.filter(Client.created_by_id == owner_id)
    return query.first()


def update_client(db: Session, client: Client, data: ClientUpdate) -> Client:
    name_normalized = normalize_name(data.full_name)
    existing = (
        db.query(Client)
        .filter(
            Client.name_normalized == name_normalized,
            Client.created_by_id == client.created_by_id,
            Client.id != client.id,
        )
        .first()
    )
    if existing:
        raise ValueError(NAME_CONFLICT_MESSAGE)

    client.full_name = data.full_name.strip()
    client.name_normalized = name_normalized
    client.whatsapp = (data.whatsapp or "").strip() or None
    _commit(db)
    db.refresh(client)
    return client


def delete_client(db: Session, client: Client) -> None:
    if client.sales:
        raise ValueError("Cliente possui vendas registradas e não pode ser excluído")
    db.delete(client)
    db.commit()