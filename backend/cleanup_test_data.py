"""Limpa os dados de teste criados durante a execucao dos testes."""
from sqlalchemy import or_

from database import SessionLocal
from models.client import Client
from models.sale import Sale
from models.sale_item import SaleItem
from models.user import User

db = SessionLocal()

# Usuarios de teste: nomes conhecidos + padroes usados pelos smoke tests
candidates = (
    db.query(User)
    .filter(
        or_(
            User.email.like("smoke_%@crm.com"),
            User.email.like("sales_smoke_%@crm.com"),
            User.email.like("e2e_%@test.com"),
            User.email.like("faseA_%@test.com"),
            User.email.like("diag%@test.com"),
            User.email == "teste1@crm.com",
        )
    )
    .all()
)
tids = [u.id for u in candidates] or [0]

if tids:
    # vendas dos usuarios de teste
    sale_ids = [s.id for s in db.query(Sale).filter(Sale.user_id.in_(tids)).all()]
    if sale_ids:
        db.query(SaleItem).filter(SaleItem.sale_id.in_(sale_ids)).delete(synchronize_session=False)
        db.query(Sale).filter(Sale.id.in_(sale_ids)).delete(synchronize_session=False)
    # clientes criados por eles (e vendas remanescentes)
    cl_ids = [c.id for c in db.query(Client).filter(Client.created_by_id.in_(tids)).all()]
    if cl_ids:
        s2 = [s.id for s in db.query(Sale).filter(Sale.client_id.in_(cl_ids)).all()]
        if s2:
            db.query(SaleItem).filter(SaleItem.sale_id.in_(s2)).delete(synchronize_session=False)
            db.query(Sale).filter(Sale.id.in_(s2)).delete(synchronize_session=False)
        db.query(Client).filter(Client.id.in_(cl_ids)).delete(synchronize_session=False)
    db.query(User).filter(User.id.in_(tids)).delete(synchronize_session=False)

db.commit()
print("users:", db.query(User).count(), "| clients:", db.query(Client).count(), "| sales:", db.query(Sale).count(), "| items:", db.query(SaleItem).count())
db.close()