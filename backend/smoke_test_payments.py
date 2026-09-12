"""Teste funcional: WhatsApp no cliente + pagamentos parciais."""
import sys
from datetime import date, datetime, timedelta

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)
results = []


def check(name, ok, extra=""):
    results.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'} | {name} {extra}")


email = f"pay_{datetime.now().strftime('%H%M%S')}@crm.com"
client_name = f"Ana Silva {datetime.now().strftime('%H%M%S')}"

# Register + login
r = client.post("/auth/register", json={"name": "Pay Test", "email": email, "password": "123456"})
check("register", r.status_code == 201, f"status={r.status_code}")
r = client.post("/auth/login", json={"email": email, "password": "123456"})
check("login", r.status_code == 200, f"status={r.status_code}")
h = {"Authorization": f"Bearer {r.json()['access_token']}"}

# --- IMPL 1: cliente com whatsapp ---
r = client.post("/clients", json={"full_name": client_name, "whatsapp": "5511999998888"}, headers=h)
check("create client whatsapp", r.status_code == 201 and r.json().get("whatsapp") == "5511999998888",
      f"status={r.status_code} body={r.json()}")
client_id = r.json()["id"]

r = client.get("/clients", headers=h)
me = next((x for x in r.json() if x["id"] == client_id), None)
check("get client whatsapp", bool(me and me.get("whatsapp") == "5511999998888"), f"whatsapp={me and me.get('whatsapp')}")

# --- IMPL 2: pagamentos parciais ---
r = client.post("/sales", json={
    "client_id": client_id,
    "sale_date": date.today().isoformat(),
    "status": "pending",
    "due_date": (date.today() + timedelta(days=30)).isoformat(),
    "items": [{"product_name": "Produto X", "quantity": 1, "unit_price": "200.00"}],
}, headers=h)
check("create sale 200", r.status_code == 201, f"status={r.status_code}")
sale = r.json()
sale_id = sale["id"]
check("sale initial remaining", sale["remaining"] == "200.00" and sale["amount_paid"] == "0.00",
      f"remaining={sale['remaining']} amount_paid={sale['amount_paid']}")

r = client.get(f"/sales/{sale_id}", headers=h)
check("sale response has amount fields", "amount_paid" in r.json() and "remaining" in r.json(),
      f"keys={list(r.json().keys())}")

# Pagamento parcial: 80
r = client.post("/payments", json={
    "sale_id": sale_id,
    "amount_paid": "80.00",
    "payment_date": date.today().isoformat(),
    "new_due_date": (date.today() + timedelta(days=20)).isoformat(),
    "notes": "primeira parcela",
}, headers=h)
check("payment partial 80", r.status_code == 201, f"status={r.status_code} body={r.json()}")
pay1 = r.json()
check("payment response fields", all(k in pay1 for k in ("id", "sale_id", "amount_paid", "payment_date", "new_due_date", "notes")),
      f"keys={list(pay1.keys())}")

r = client.get(f"/sales/{sale_id}", headers=h)
sale = r.json()
check("after 80: remaining 120, amount_paid 80", sale["remaining"] == "120.00" and sale["amount_paid"] == "80.00",
      f"remaining={sale['remaining']} amount_paid={sale['amount_paid']} status={sale['status']}")
check("status still pending", sale["status"] == "pending", f"status={sale['status']}")

# Listar pagamentos
r = client.get(f"/payments/{sale_id}", headers=h)
check("list payments count 1", r.status_code == 200 and len(r.json()) == 1, f"count={len(r.json())}")

# Validações de erro
r = client.post("/payments", json={"sale_id": 999999, "amount_paid": "10.00", "payment_date": date.today().isoformat()}, headers=h)
check("payment nonexistent 400", r.status_code == 400, f"status={r.status_code} detail={r.json().get('detail')}")

r = client.post("/payments", json={"sale_id": sale_id, "amount_paid": "0.00", "payment_date": date.today().isoformat()}, headers=h)
check("payment zero 400", r.status_code == 400, f"status={r.status_code} detail={r.json().get('detail')}")

r = client.post("/payments", json={"sale_id": sale_id, "amount_paid": "121.00", "payment_date": date.today().isoformat()}, headers=h)
check("payment > remaining 400", r.status_code == 400, f"status={r.status_code} detail={r.json().get('detail')}")

# Sem token -> 401
r = client.get(f"/payments/{sale_id}")
check("payments no token 401", r.status_code == 401, f"status={r.status_code}")

# Pagamento total de 120 -> venda paga
r = client.post("/payments", json={"sale_id": sale_id, "amount_paid": "120.00", "payment_date": date.today().isoformat()}, headers=h)
check("payment final 120", r.status_code == 201, f"status={r.status_code}")

r = client.get(f"/sales/{sale_id}", headers=h)
sale = r.json()
check("sale paid, remaining 0", sale["status"] == "paid" and sale["remaining"] == "0.00" and sale["amount_paid"] == "200.00",
      f"status={sale['status']} remaining={sale['remaining']} amount_paid={sale['amount_paid']} due_date={sale['due_date']}")
check("due_date cleared", sale["due_date"] is None, f"due_date={sale['due_date']}")

r = client.post("/payments", json={"sale_id": sale_id, "amount_paid": "1.00", "payment_date": date.today().isoformat()}, headers=h)
check("payment on paid 400", r.status_code == 400, f"status={r.status_code} detail={r.json().get('detail')}")

r = client.get(f"/payments/{sale_id}", headers=h)
check("list payments count 2", len(r.json()) == 2, f"count={len(r.json())}")

# --- cleanup em ordem de dependência (payments -> items -> vendas -> clientes -> usuário) ---
from database import SessionLocal
from models.payment import Payment
from models.sale import Sale
from models.sale_item import SaleItem
from models.user import User

db = SessionLocal()
user = db.query(User).filter(User.email == email).first()
if user:
    for c in user.clients:
        for s in c.sales:
            db.query(Payment).filter(Payment.sale_id == s.id).delete(synchronize_session=False)
            db.query(SaleItem).filter(SaleItem.sale_id == s.id).delete(synchronize_session=False)
            db.delete(s)
        db.commit()
    for c in list(user.clients):
        db.delete(c)
    db.commit()
    db.query(User).filter(User.id == user.id).delete(synchronize_session=False)
    db.commit()
db.close()

fails = [n for n, ok in results if not ok]
print("=" * 40)
print(f"{len(results) - len(fails)}/{len(results)} passed")
sys.exit(1 if fails else 0)