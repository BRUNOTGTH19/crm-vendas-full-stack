"""Smoke test temporario - modulo de clientes (Fase 1)."""
import sys
from datetime import datetime

from fastapi.testclient import TestClient

from database import SessionLocal
from main import app
from models.client import Client
from models.sale import Sale
from models.sale_item import SaleItem
from models.user import User

client = TestClient(app)
results = []


def check(name: str, ok: bool, extra: str = "") -> None:
    results.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'} | {name} {extra}")


email = f"smoke_{datetime.now().strftime('%H%M%S')}@crm.com"

# 1. Register
r = client.post("/auth/register", json={"name": "Smoke", "email": email, "password": "123456"})
check("register", r.status_code == 201, f"status={r.status_code}")

# 2. Login
r = client.post("/auth/login", json={"email": email, "password": "123456"})
check("login", r.status_code == 200, f"status={r.status_code}")
headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

# 3. Create client com acento
r = client.post("/clients", json={"full_name": "Maria Oliveira"}, headers=headers)
ok = r.status_code == 201 and r.json()["name_normalized"] == "maria oliveira"
check("create client", ok, f"status={r.status_code} body={r.json()}")
client_id = r.json().get("id")

# 4. Duplicado por normalizacao -> 400
r = client.post("/clients", json={"full_name": "maria  oliveira"}, headers=headers)
check("duplicate blocked", r.status_code == 400, f"status={r.status_code} detail={r.json()}")

# 5. Lista
r = client.get("/clients", headers=headers)
check("list clients", r.status_code == 200 and len(r.json()) >= 1, f"status={r.status_code} count={len(r.json())}")

# 6. Busca
r = client.get("/clients?search=OLIVEIRA", headers=headers)
check("search", r.status_code == 200 and len(r.json()) >= 1, f"status={r.status_code} count={len(r.json())}")

# 7. Sem token -> 401
r = client.get("/clients")
check("no token 401", r.status_code == 401, f"status={r.status_code}")

# 8. Nome curto -> 422
r = client.post("/clients", json={"full_name": "ab"}, headers=headers)
check("short name 422", r.status_code == 422, f"status={r.status_code}")

# cleanup
print("--- cleanup ---")
db = SessionLocal()
if client_id:
    c = db.query(Client).filter(Client.id == client_id).first()
    if c:
        for s in c.sales:
            db.query(SaleItem).filter(SaleItem.sale_id == s.id).delete(synchronize_session=False)
            db.query(Sale).filter(Sale.id == s.id).delete(synchronize_session=False)
        db.delete(c)
        db.commit()
# remove usuario de teste criado nesta execucion
db.query(User).filter(User.email == email).delete(synchronize_session=False)
db.commit()
db.close()

fails = [n for n, ok in results if not ok]
print("=" * 40)
print(f"{len(results) - len(fails)}/{len(results)} passed")
sys.exit(1 if fails else 0)